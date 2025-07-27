# app.py (Added URL validation, other fixes unchanged)
import streamlit as st
import os
import sqlite3
from datetime import datetime
import re
from utils import get_user_tier, fetch_page_content, analyze_accessibility, export_to_pdf, export_to_csv, export_to_excel
import stripe
from simulator.simulator import load_personas, simulate_experience
import logging

logging.basicConfig(level=logging.INFO)

# Environment setup
required_envs = ["OPENAI_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PRO_PRICE_ID", "STRIPE_AGENCY_PRICE_ID", "PROD_DOMAIN"]
for env_var in required_envs:
    if not os.getenv(env_var):
        st.error(f"Missing environment variable: {env_var}. Contact support.")
        st.stop()

env = os.getenv("ENV", "local")
domain = os.getenv("PROD_DOMAIN") if env == "prod" else os.getenv("LOCAL_DOMAIN", "https://nexassist.ai")

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# --- Custom CSS (Added media queries for mobile) ---
st.markdown("""
    <style>
    .logo-container {
        display: flex;
        align-items: center;
        justify-content: start;
        margin-bottom: 1rem;
    }
    .logo-container img {
        max-height: 60px;
    }
    .stTextInput > div > div > input {
        background-color: #f8f9fa;
    }
    .stButton > button {
        width: 100%;
        background-color: #007bff;
        color: white;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #0056b3;
    }
    .reportview-container {
        background-color: #ffffff;
    }
    @media (max-width: 600px) {
        .stColumn { width: 100%; margin-bottom: 1rem; }
        .stExpander { width: 100%; }
    }
    </style>
""", unsafe_allow_html=True)

# --- Session state defaults ---
for key, val in {
    'user_email': None,
    'tier': 'Free',
    'scan_count': 0,
    'results': None,
    'dark_mode': False
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- Dark mode toggle ---
if st.sidebar.checkbox("Dark Mode", value=st.session_state.dark_mode, help="Switch to dark theme"):
    st.session_state.dark_mode = True
    st.markdown("""
        <style>
        .reportview-container { background-color: #121212; color: #ffffff; }
        .stTextInput > div > div > input { background-color: #2c2c2c; color: #ffffff; }
        .stButton > button { background-color: #0056b3; }
        .stMarkdown, .stInfo, .stError, .stWarning { color: #f0f0f0; }
        .stExpander { background-color: #1e1e1e; color: #ffffff; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.session_state.dark_mode = False
    st.markdown("<style> .reportview-container { background-color: #ffffff; } </style>", unsafe_allow_html=True)

# --- Query Parameter Handling (Added success message and tier force refresh) ---
session_id = st.query_params.get("session_id")
session_id = session_id[0] if isinstance(session_id, list) and session_id else session_id if isinstance(session_id, str) else None

if session_id and not st.session_state.get("user_email"):
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        email = checkout_session.get("customer_email") or checkout_session.get("customer_details", {}).get("email")
        if email and re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            st.session_state.user_email = email
            st.session_state.tier = get_user_tier(email)
            st.success("Subscription successful! Your plan has been updated.")  # Success message
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ Error retrieving Stripe session: {str(e)}")

# --- Logo + header ---
from ui import render_logo_and_header, render_email_url_form, render_help_link, render_plan_message, render_results, render_export_buttons
render_logo_and_header()
render_help_link()
st.info("👋 New here? Enter your info below to run a full scan and see results in seconds.")

# --- Email + URL Form ---
email, url, submitted = render_email_url_form()

# --- Validate and set user info (Added real-time validation) ---
def validate_email():
    if 'email_input' in st.session_state and not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', st.session_state.email_input):
        st.error("Invalid email format. Use name@example.com.")
    else:
        st.session_state.user_email = st.session_state.email_input
        st.session_state.tier = get_user_tier(st.session_state.user_email)

if email:
    validate_email()

render_plan_message(st.session_state.tier)

# --- Stripe upgrade buttons ---
def create_checkout_button(label, price_env_var):
    if st.sidebar.button(label):
        if not st.session_state.user_email:
            st.sidebar.error("⚠️ Please enter a valid email above first.")
            return
        with st.spinner("Generating secure checkout session..."):
            try:
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
                st.sidebar.error(f"❌ Error creating Stripe session: {str(e)}")

create_checkout_button("Upgrade to Pro ($9/mo)", "STRIPE_PRO_PRICE_ID")
create_checkout_button("Upgrade to Agency ($49/mo)", "STRIPE_AGENCY_PRICE_ID")

# --- Help section ---
with st.expander("📘 First time here? Click for help", expanded=False):
    st.markdown("""
    **How it works:**
    1. Enter your **work email** to unlock your tier.
    2. Paste a **website URL** and click **Scan Site**.
    3. View **AI-generated issues, summaries, scores, and reports**.
    4. Upgrade for unlimited scans + AI summaries + code fixes + PDF/CSV/Excel export.
    """)

# --- SCAN logic ---
def check_scan_limit(email):
    conn = sqlite3.connect("scans.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS scans (email TEXT, count INTEGER, date TEXT)")
    cursor.execute("SELECT count FROM scans WHERE email = ? AND date = ?", (email, datetime.utcnow().date().isoformat()))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def increment_scan_count(email):
    conn = sqlite3.connect("scans.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO scans (email, count, date) VALUES (?, COALESCE((SELECT count + 1 FROM scans WHERE email = ? AND date = ?), 1), ?)",
                  (email, email, datetime.utcnow().date().isoformat(), datetime.utcnow().date().isoformat()))
    conn.commit()
    conn.close()

if submitted and st.session_state.user_email:
    if st.session_state.tier == 'Free' and check_scan_limit(st.session_state.user_email) >= 1:
        st.error("Free scan limit reached. Upgrade for more.")
        st.stop()
    # Added: checkbox for full scan before scan
    full_scan = st.checkbox("Full scan (slower but complete)", value=False, help="Uncheck for quicker preview") if st.session_state.tier in ['Pro', 'Agency'] else False # Added: checkbox for full scan before the scan starts, tooltips
    increment_scan_count(st.session_state.user_email)
    with st.spinner("Scanning..."):
        # Added: check for valid URL before fetch
        if not url.strip():
            st.error("Please enter a valid URL.")
            st.stop()
        result = fetch_page_content(url)
        if not result["success"]:
            st.error(result.get("error", "Unknown error while fetching page."))
            st.stop()
        html = result["html"]
        st.session_state["html"] = html # Cache HTML for re-use
        results = analyze_accessibility(html, abbreviated=not full_scan)
        st.session_state["results"] = results
        st.session_state["results"]["html"] = html
        if "error" in results:
            st.error(results["error"])
            st.stop()
        results["pdf"] = export_to_pdf(results)
        results["csv"] = export_to_csv(results)
        results["excel"] = export_to_excel(results)
        render_results(results)
        if st.session_state.tier in ['Pro', 'Agency']:
            render_export_buttons(results)
# --- Post-Scan Full Toggle (Added: Re-run full if preview was abbreviated) ---
if st.session_state.get("results") and st.session_state.tier in ['Pro', 'Agency']:
    if st.button("Run Full Scan", help="Re-run complete analysis (no chunk limits)"):  # Button for explicit re-trigger
        with st.spinner("Running full scan..."):
            html = st.session_state.get("html")  # Re-use cached HTML
            if html:
                results = analyze_accessibility(html, abbreviated=False)  # Full mode
                st.session_state["results"] = results
                results["pdf"] = export_to_pdf(results)
                results["csv"] = export_to_csv(results)
                results["excel"] = export_to_excel(results)
                render_results(results)
                render_export_buttons(results)
                st.success("Full scan complete!")
            else:
                st.error("No HTML available for full scan. Re-scan the site.")

# --- Persona Simulation Section (Added spinner and help text) ---
if st.session_state.get("results") and st.session_state["results"].get("html"):
    personas = load_personas()
    selected_key = st.selectbox(
        "👤 Simulate Accessibility Experience",
        options=list(personas.keys()),
        format_func=lambda key: personas[key]["label"],
        help="Select a persona to simulate their experience"  # Fixed: static help text to avoid NameError
    )
    if selected_key:
        st.info(personas[selected_key]["description"])  # Added: st.info for dynamic description after selection
        with st.spinner("Simulating experience..."):
            simulation = simulate_experience(st.session_state["results"]["html"], selected_key)
            if isinstance(simulation, dict) and simulation.get("error"):
                st.error(f"Simulator Error: {simulation['error']}")
            else:
                st.subheader(f"🔍 Accessibility Persona Simulation — {personas[selected_key]['label']}")
                st.markdown(simulation)
else:
    st.warning("No HTML content available for simulation. Run a scan first.")

# --- Footer ---
st.caption("Free: 1 scan/day. Pro: Unlimited + exports + code fixes. Agency: Multi-domain + white-label. Enterprise: Custom.")