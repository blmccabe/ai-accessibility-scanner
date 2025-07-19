import os
import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
from dotenv import load_dotenv
import stripe
from fpdf import FPDF
from datetime import datetime
import csv
import io
import pandas as pd  # For Excel
from io import BytesIO

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
    except Exception:
        return 'Free'

from playwright.sync_api import sync_playwright

def fetch_html(url):
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        return f"Error fetching URL with Playwright: {e}"


def analyze_accessibility(html_content):
    """Use AI to scan HTML for WCAG issues with code fixes."""
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

    HTML: {html_content[:4000]}
    """
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        result_text = response.choices[0].message.content.strip()
        import json
        try:
            return json.loads(result_text)
        except Exception:
            return {
                "error": "AI response could not be parsed. Try again.",
                "raw": result_text,
                "disclaimer": "Analysis failed. This may be due to malformed AI output."
            }
    except Exception as e:
        return {"error": str(e), "disclaimer": "Analysis failed."}

def export_to_pdf(results):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Score: {results.get('score', 'N/A')}", ln=1)
    pdf.cell(200, 10, txt=f"Scan Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=1)
    for issue in results.get('issues', []):
        pdf.multi_cell(0, 10, txt=f"{issue['criterion']} ({issue['severity']}): {issue['description']}")
        pdf.multi_cell(0, 10, txt=f"Fix: {issue['fix']}")
        pdf.multi_cell(0, 10, txt=f"Code Fix: {issue['code_fix']}")
        pdf.ln(2)

    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return BytesIO(pdf_bytes)

def export_to_csv(results):
    csv_output = io.StringIO()
    writer = csv.writer(csv_output, quoting=csv.QUOTE_ALL)
    writer.writerow(['Criterion', 'Severity', 'Description', 'Fix', 'Code Fix'])
    for issue in results.get('issues', []):
        writer.writerow([issue['criterion'], issue['severity'], issue['description'], issue['fix'], issue['code_fix']])
    return BytesIO(csv_output.getvalue().encode("utf-8"))

def export_to_excel(results):
    df = pd.DataFrame(results.get('issues', []))
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Scan Report')
    output.seek(0)
    return output
