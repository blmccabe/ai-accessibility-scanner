# utils.py (Added import time for time.sleep, increased Playwright timeout, other fixes)
import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
import stripe
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
import csv
import io
import pandas as pd
from io import BytesIO
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import logging
import json
import re
import html
import backoff
import time  # Fixed: added import time for time.sleep

logging.basicConfig(level=logging.INFO)
load_dotenv()

def get_user_tier(email):
    """Check Stripe subscription tier with retry."""
    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def _get_user_tier(email):
        try:
            customers = stripe.Customer.search(query=f'email:"{email}"')
            if customers.data:
                customer = customers.data[0]
                subs = stripe.Subscription.list(customer=customer.id)
                if subs.data and subs.data[0].status == 'active':
                    price_id = subs.data[0].plan.id
                    if price_id == os.getenv("STRIPE_PRO_PRICE_ID"):
                        return 'Pro'
                    elif price_id == os.getenv("STRIPE_AGENCY_PRICE_ID"):
                        return 'Agency'
            return 'Free'
        except Exception as e:
            logging.error(f"[Stripe Error] {e}")
            raise
    try:
        return _get_user_tier(email)
    except Exception:
        logging.error("Unable to verify subscription.")
        return 'Free'

def normalize_url(url):
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        url = 'https://' + url
        parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("Invalid URL: No domain specified")
    return url

def block_heavy_resources(route):
    if route.request.resource_type in ["image", "media", "font", "stylesheet", "other"]:
        route.abort()
    else:
        route.continue_()

def fetch_page_content(target_url):
    target_url = normalize_url(target_url)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.route("**/*", block_heavy_resources)
            page = context.new_page()
            page.goto(target_url, timeout=60000, wait_until='domcontentloaded')  # Increased timeout to 60s to fix timeout
            content = page.content()
            context.close()
            browser.close()
            return {"success": True, "html": content}
    except Exception as e:
        logging.warning(f"[Playwright Error] {e}")
        try:
            response = requests.get(target_url, timeout=10, headers={"User-Agent": "NexAssistAI/1.0"})
            response.raise_for_status()
            return {"success": True, "html": response.text}
        except Exception as fallback_e:
            logging.error(f"[Requests Error] {fallback_e}")
            return {
                "success": False,
                "error": f"Failed to fetch {target_url}. Check URL validity or try again later.",
                "score": 0,
                "summary": "Unable to scan due to fetch error."
            }

def analyze_accessibility(html_content, abbreviated=True):
    """Use AI to scan HTML for WCAG issues with chunking and JSON mode."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    chunks = [html_content[i:i+3000] for i in range(0, len(html_content), 3000)]
    if abbreviated:
        chunks = chunks[:2]  # Limit for preview/Free
    else:
        chunks = chunks  # Full (no limit)
    chunks = chunks[:2]  # Limit to 2 chunks to avoid rate limits
    results = []
    for chunk in chunks:
        safe_html_snippet = html.escape(chunk).replace('{', '').replace('}', '')
        prompt = f"""
Analyze this HTML for WCAG 2.1/2.2 accessibility issues. Focus on:
- Perceivable: Missing alt text on images, color contrast (estimate if possible), text alternatives.
- Operable: Keyboard navigation traps, ARIA roles/labels for interactive elements.
- Understandable: Headings structure, form labels, error messages.
- Robust: HTML validity, no deprecated elements.

Respond only with valid JSON in this exact structure: {{
  "issues": [
    {{
      "criterion": "WCAG ref",
      "description": "Issue detail",
      "severity": "Low/Med/High",
      "fix": "Suggestion",
      "code_fix": "Example HTML code snippet to fix the issue (or 'N/A' if not applicable)"
    }}
  ],
  "score": 0-100 estimate,
  "disclaimer": "This is AI-generated; not a full manual audit. Consult WCAG experts.",
  "summary": "Brief AI summary of key issues for Pro users."
}}

HTML: {safe_html_snippet}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content.strip()
            results.append(json.loads(result_text))
            time.sleep(1)  # Added: time.sleep(1) for rate limits
        except Exception as e:
            logging.error(f"[OpenAI Error] {e}")
            return {"error": "AI response could not be parsed. Try again.", "disclaimer": f"Parsing failed. Reason: {str(e)}"}
    merged = {"issues": [], "score": 0, "disclaimer": results[0]["disclaimer"], "summary": ""}
    for r in results:
        merged["issues"].extend(r.get("issues", []))
        merged["score"] += int(r.get("score", 0)) / len(results)
        merged["summary"] += r.get("summary", "") + "\n"
    return merged

def export_to_pdf(results):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(30, 750, f"Score: {results.get('score', 'N/A')}")
    pdf.drawString(30, 730, f"Scan Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    y = 700
    for line in results.get('summary', 'No summary available.').split('\n'):
        pdf.drawString(30, y, line[:80])
        y -= 20
    for issue in results.get('issues', []):
        pdf.drawString(30, y, f"{issue['criterion']} ({issue['severity']}): {issue['description'][:80]}")
        y -= 20
        pdf.drawString(30, y, f"Fix: {issue['fix'][:80]}")
        y -= 20
    pdf.save()
    buffer.seek(0)
    return buffer

def export_to_csv(results):
    csv_output = io.StringIO()
    writer = csv.writer(csv_output, quoting=csv.QUOTE_ALL)
    writer.writerow(['Criterion', 'Severity', 'Description', 'Fix', 'Code Fix'])
    for issue in results.get('issues', []):
        writer.writerow([
            issue.get('criterion', ''),
            issue.get('severity', ''),
            issue.get('description', ''),
            issue.get('fix', ''),
            issue.get('code_fix', '')
        ])
    return BytesIO(csv_output.getvalue().encode("utf-8"))

def export_to_excel(results):
    df = pd.DataFrame(results.get('issues', []))
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Scan Report')
    output.seek(0)
    return output