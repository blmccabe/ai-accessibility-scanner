import os
import requests
from bs4 import BeautifulSoup
import openai
from dotenv import load_dotenv
import stripe
from fpdf import FPDF
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

# Setup logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def get_user_tier(email):
    """Check Stripe sub tier."""
    try:
        customers = stripe.Customer.search(query=f'email:"{email}"')
        if customers.data:
            customer = customers.data[0]
            subs = stripe.Subscription.list(customer=customer.id)
            if subs.data:
                sub = subs.data[0]
                if sub.status == 'active':
                    price_id = sub.plan.id
                    if price_id == os.getenv("STRIPE_PRO_PRICE_ID"):
                        return 'Pro'
                    elif price_id == os.getenv("STRIPE_AGENCY_PRICE_ID"):
                        return 'Agency'
                    return 'Unknown'
        return 'Free'
    except Exception as e:
        logging.error(f"[Stripe Error] {e}")
        return 'Free'

def normalize_url(url):
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        return 'https://' + url
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
            page.goto(target_url, timeout=30000, wait_until='domcontentloaded')
            content = page.content()
            context.close()
            browser.close()
            return {
                "success": True,
                "html": content
            }
    except Exception as e:
        logging.warning(f"[Playwright error] {e}")
        try:
            response = requests.get(target_url, timeout=10)
            response.raise_for_status()
            return {
                "success": True,
                "html": response.text
            }
        except Exception as fallback_e:
            logging.error(f"[Requests fallback error] {fallback_e}")
            return {
                "success": False,
                "error": f"Error fetching URL: {str(fallback_e)}",
                "score": 0,
                "summary": "This site could not be scanned due to a loading issue. Double-check the URL or try a different one."
            }

def analyze_accessibility(html_content):
    """Use AI to scan HTML for WCAG issues with code fixes."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    safe_html_snippet = html_content[:3000]
    safe_html_snippet = html.escape(safe_html_snippet).replace('{', '').replace('}', '').replace('"', "'").replace('\\', '')

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
  "score": "0-100 estimate",
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
            max_tokens=1000
        )
        result_text = response.choices[0].message.content.strip()
        try:
            return json.loads(result_text)
        except Exception:
            match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            else:
                raise ValueError("No JSON object found in response.")
    except Exception as e:
        logging.error(f"[OpenAI Error] {e}")
        return {
            "error": "AI response could not be parsed. Try again.",
            "raw": result_text if 'result_text' in locals() else '',
            "disclaimer": f"Parsing failed. Reason: {str(e)}"
        }

def export_to_pdf(results):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Score: {results.get('score', 'N/A')}", ln=1)
    pdf.cell(200, 10, txt=f"Scan Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=1)
    pdf.multi_cell(0, 10, txt=results.get('summary', 'No summary available.'))
    for issue in results.get('issues', []):
        pdf.multi_cell(0, 10, txt=f"{issue['criterion']} ({issue['severity']}): {issue['description']}")
        pdf.multi_cell(0, 10, txt=f"Fix: {issue['fix']}")
        pdf.multi_cell(0, 10, txt=f"Code Fix: {issue['code_fix']}")
        pdf.ln(2)
    return BytesIO(pdf.output(dest='S').encode('latin1'))

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
