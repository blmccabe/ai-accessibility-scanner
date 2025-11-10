# utils.py
import os
import html
from io import BytesIO
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
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import logging
import json
import re
import backoff
import time
import streamlit as st

logging.basicConfig(level=logging.INFO)
load_dotenv()

def get_user_tier(email=None, customer_id=None):
    """
    Resolve user tier via Stripe. Prefer customer_id when available (most accurate),
    fall back to searching by email.
    Treat active or trialing subscriptions as paid.
    Includes full compatibility for both old and new Stripe API styles.
    """
    PRICE_ID_TO_TIER = {
        os.getenv("STRIPE_PRO_PRICE_ID"): "Pro",
        os.getenv("STRIPE_AGENCY_PRICE_ID"): "Agency",
    }

    # Log what price IDs are actually loaded from env (for easy troubleshooting)
    logging.info(f"[Stripe Debug] Loaded price map: {PRICE_ID_TO_TIER}")

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def _fetch(customer_id=None, email=None):
        try:
            # Step 1: Get or resolve customer ID
            if customer_id:
                cust_id = customer_id
            else:
                customers = stripe.Customer.search(query=f'email:"{email}"', limit=1)
                if not hasattr(customers, "data") or not customers.data:
                    logging.info(f"[Stripe Debug] No customer found for {email}")
                    return "Free"
                cust_id = customers.data[0].id

            # Step 2: Retrieve subscriptions
            subs = stripe.Subscription.list(
                customer=cust_id,
                status="all",
                expand=["data.items.data.price"]
            )

            logging.info(f"[Stripe Debug] Customer ID: {cust_id}")
            logging.info(f"[Stripe Debug] Sub count: {len(subs.data) if hasattr(subs, 'data') else 'no data'}")

            if not hasattr(subs, "data") or not subs.data:
                return "Free"

            # Step 3: Choose the first active or trialing subscription
            prioritized = sorted(
                subs.data,
                key=lambda s: 0 if getattr(s, "status", None) in ("active", "trialing") else 1
            )
            sub = prioritized[0]

            status = getattr(sub, "status", None)
            logging.info(f"[Stripe Debug] Selected Sub status={status}")

            if status not in ("active", "trialing"):
                return "Free"

            # Step 4: Access price ID safely (covers both new and legacy API shapes)
            price_id = None
            if hasattr(sub, "items") and hasattr(sub.items, "data") and sub.items.data:
                first_item = sub.items.data[0]
                price_obj = getattr(first_item, "price", None)
                price_id = getattr(price_obj, "id", None)

            # 🔁 Fallback if no price found under items
            if not price_id:
                plan_obj = getattr(sub, "plan", None)
                price_id = getattr(plan_obj, "id", None)

            logging.info(f"[Stripe Debug] Price ID found: {price_id}")

            if not price_id:
                return "Free"

            # Step 5: Map to tier
            tier = PRICE_ID_TO_TIER.get(price_id, "Free")
            logging.info(f"[Stripe Debug] Tier resolved as: {tier}")
            return tier

        except Exception as e:
            logging.error(f"[Stripe Error] {e}")
            raise

    # Step 6: Execute with retry logic
    try:
        return _fetch(customer_id=customer_id, email=email)
    except Exception:
        logging.error("Unable to verify subscription.")
        return "Free"

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
            page.goto(target_url, timeout=60000, wait_until='domcontentloaded')
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

def split_html_safely(html_content, chunk_size=3000):
    """Split HTML content at safe boundaries to avoid breaking tags."""
    chunks = []
    current = ""
    tag_count = 0
    for char in html_content:
        current += char
        if char == '<':
            tag_count += 1
        elif char == '>':
            tag_count -= 1
        if len(current) >= chunk_size and tag_count == 0:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks

@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def analyze_accessibility(html_content, abbreviated=True):
    """Use AI to scan HTML for WCAG issues with chunking and JSON mode."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    chunks = [html_content[i:i+5000] for i in range(0, len(html_content), 5000)]  # Larger chunks for speed
    if abbreviated:
        chunks = chunks[:1]  # Single chunk for preview/Free (faster)
    # No chunk limit for full scans
    results = []
    for i, chunk in enumerate(chunks):
        safe_html_snippet = html.escape(chunk).replace('{', '').replace('}', '')
        prompt = f"""
Analyze the following HTML for WCAG 2.2 accessibility issues. For each issue:
- Specify the WCAG criterion (e.g., 1.1.1).
- Describe the issue clearly.
- Provide a fix suggestion.
- Include a specific code fix (e.g., HTML/CSS/JS snippet) if applicable.
- Assign a category: Perceivable, Operable, Understandable, Robust.

Generate at least 3 issues per category for comprehensive scans, or 1 per category for abbreviated scans.
Include a confidence score (0-100) for each issue based on likelihood of correctness.
Return results in structured JSON format:
{{
  "issues": [
    {{
      "criterion": "string",
      "description": "string",
      "severity": "Low/Med/High",
      "fix": "string",
      "code_fix": "string",
      "category": "Perceivable/Operable/Understandable/Robust",
      "confidence": integer
    }}
  ],
  "score": 0-100,
  "disclaimer": "AI-powered scan aligned with WCAG 2.2; not a full manual audit. Consult experts.",
  "summary": "string (200 chars max)"
}}

HTML: {safe_html_snippet}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,  # Increased for more issues
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content.strip()
            results.append(json.loads(result_text))
            time.sleep(0.5)  # Reduced for speed
        except Exception as e:
            logging.error(f"[OpenAI Error] {e}")
            return {"error": f"AI response failed: {str(e)}", "disclaimer": "Scan failed."}
    # Validate HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    missing_alt = len([img for img in soup.find_all('img') if not img.get('alt')])
    if missing_alt > 0:
        results[0]["issues"].append({
            "criterion": "1.1.1",
            "description": f"Found {missing_alt} images without alt text.",
            "severity": "High",
            "fix": "Add descriptive alt text to all images.",
            "code_fix": '<img src="example.jpg" alt="Description of image">',
            "category": "Perceivable",
            "confidence": 95
        })
    merged = {"issues": [], "score": 0, "disclaimer": results[0]["disclaimer"], "summary": ""}
    for r in results:
        for issue in r.get("issues", []):
            issue['category'] = issue.get('category', 'Unknown')  # Fallback
            merged["issues"].append(issue)
        merged["score"] += int(r.get("score", 0)) / len(results)
        merged["summary"] += r.get("summary", "") + "\n"
    return merged

def export_to_pdf(results):
    if "error" in results:
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setFont("Helvetica", 12)
        pdf.drawString(30, 770, "Error: Unable to generate report.")
        pdf.drawString(30, 750, results["error"])
        pdf.save()
        buffer.seek(0)
        return buffer

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont("Helvetica", 12)
    tier = st.session_state.get('tier', 'Free')
    if tier != 'Agency':
        pdf.drawString(30, 770, "NexAssistAI Report")
    pdf.drawString(30, 750, f"Score: {results.get('score', 'N/A')}")
    pdf.drawString(30, 730, f"Scan Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    y = 700
    for line in results.get('summary', 'No summary available.').split('\n'):
        if y < 50:  # Add page break if needed
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y = 770
        pdf.drawString(30, y, line[:80])
        y -= 20
    for issue in results.get('issues', []):
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 12)
            y = 770
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
    writer.writerow(['Criterion', 'Severity', 'Description', 'Fix', 'Code Fix', 'Category'])
    for issue in results.get('issues', []):
        writer.writerow([
            issue.get('criterion', ''),
            issue.get('severity', ''),
            issue.get('description', ''),
            issue.get('fix', ''),
            issue.get('code_fix', ''),
            issue.get('category', 'Unknown')
        ])
    return BytesIO(csv_output.getvalue().encode("utf-8"))

def export_to_excel(results):
    df = pd.DataFrame(results.get('issues', []))
    if df.empty:
        df = pd.DataFrame(columns=['criterion', 'severity', 'description', 'fix', 'code_fix', 'category'])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Scan Report')
    output.seek(0)
    return output

def create_checkout_button(label, price_env_var, is_sidebar=False):
    """Create a Stripe checkout button."""
    if is_sidebar:
        if st.sidebar.button(label):
            run_checkout_session(price_env_var)
    else:
        run_checkout_session(price_env_var)

def run_checkout_session(price_env_var):
    """Run the Stripe checkout session."""
    if not st.session_state.user_email:
        st.error("⚠️ Please enter a valid email first.")
        return
    with st.spinner("Generating secure checkout session..."):
        try:
            domain = os.getenv("PROD_DOMAIN") if os.getenv("ENV", "local") == "prod" else os.getenv("LOCAL_DOMAIN", "https://nexassist.ai")
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': os.getenv(price_env_var), 'quantity': 1}],
                mode='subscription',
                success_url=f"{domain}?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=domain,
                customer_email=st.session_state.user_email
            )
            st.markdown(f'<meta http-equiv="refresh" content="0; url={session.url}" />', unsafe_allow_html=True)
        except Exception as e:
            st.error(f"❌ Error creating Stripe session: {str(e)}")