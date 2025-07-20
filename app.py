from ui import (
    render_header,
    render_email_url_form,
    render_help_link,
    render_plan_message,
    render_results,
    render_export_buttons
)
import streamlit as st
import os
from utils import get_user_tier, fetch_page_content, analyze_accessibility, export_to_pdf, export_to_csv, export_to_excel
import stripe
from PIL import Image

from simulator.simulator import load_personas, simulate_experience

# --- Custom CSS ---
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
if st.sidebar.checkbox("Dark Mode", value=st.session_state.dark_mode, help="Switch to dark theme for low light environments"):
    st.session_state.dark_mode = True
    st.markdown("""
        <style>
        .reportview-container { background-color: #121212; color: #ffffff; }
        .stTextInput > div > div > input { background-color: #2c2c2c; color: #ffffff; }
        .stButton > button { background-color: #0056b3; }
        .stMarkdown, .stInfo, .stError, .stWarning { color: #f0f0f0; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.session_state.dark_mode = False

# --- Query param prefill ---
query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
prefill_email = query_params.get("email", [None])[0]
if prefill_email and not st.session_state.user_email:
    if '@' in prefill_email and '.' in prefill_email[prefill_email.index('@'):]:
        st.session_state.user_email = prefill_email
        st.session_state.tier = get_user_tier(prefill_email)

# --- Logo + header ---
logo = Image.open("assets/logo.png")
st.image(logo, width=120)
render_header()
render_help_link()

# --- Email + URL Form ---
email, url = render_email_url_form()

# --- Validate and set user info ---
if email:
    if '@' in email and '.' in email[email.index('@'):] and len(email) >= 10:
        st.session_state.user_email = email
        st.session_state.tier = get_user_tier(email)
    else:
        st.error("Invalid email. Use format: name@example.com (min 10 characters).")
        st.session_state.user_email = None
        st.session_state.tier = 'Free'

render_plan_message(st.session_state.tier)

# --- Stripe upgrade buttons ---
st.sidebar.title("Upgrade Options")
def create_checkout_button(label, price_env_var):
    if st.sidebar.button(label):
        if not st.session_state.user_email:
            st.sidebar.error("Enter a valid email first.")
            return
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': os.getenv(price_env_var), 'quantity': 1}],
                mode='subscription',
                success_url=os.getenv("DOMAIN", "http://localhost:8501") + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=os.getenv("DOMAIN", "http://localhost:8501"),
                customer_email=st.session_state.user_email
            )
            st.sidebar.success("Redirecting to payment...")
            st.markdown(f"<script>window.location.href = '{session.url}';</script>", unsafe_allow_html=True)
            st.markdown(f"[Click if not redirected]({session.url})", unsafe_allow_html=True)
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")

create_checkout_button("Upgrade to Pro ($9/mo)", "STRIPE_PRO_PRICE_ID")
create_checkout_button("Upgrade to Agency ($49/mo)", "STRIPE_AGENCY_PRICE_ID")

# --- Help section ---
with st.expander("📘 First time here? Click for help"):
    st.markdown("""
    **How it works:**
    1. Enter your **work email** to unlock your tier.
    2. Paste a **website URL** and click **Scan Site**.
    3. View **AI-generated issues, summaries, scores, and reports**.
    4. Upgrade for unlimited scans + AI summaries + code fixes + PDF/CSV/Excel export.
    """)

# --- SCAN logic ---
if st.button("Scan Site") and st.session_state.user_email:
    if st.session_state.tier == 'Free' and st.session_state.scan_count >= 1:
        st.error("Free scan limit reached. Upgrade for more.")
        st.stop()

    st.session_state.scan_count += 1 if st.session_state.tier == 'Free' else 0

    with st.spinner("Scanning..."):
        result = fetch_page_content(url)

        if not result["success"]:
            st.error(result.get("error", "Unknown error while fetching page."))
            st.stop()

        html = result["html"]
        results = analyze_accessibility(html)
        st.session_state["results"] = results
        st.session_state["results"]["html"] = html  # Save HTML for persona simulation

        if "error" in results:
            st.error(results["error"])
        else:
            results["pdf"] = export_to_pdf(results)
            results["csv"] = export_to_csv(results)
            results["excel"] = export_to_excel(results)
            render_results(results)

            if st.session_state.tier in ['Pro', 'Agency']:
                render_export_buttons(results)

# --- Persona Simulation Section ---
if st.session_state.get("results") and st.session_state["results"].get("html"):
    personas = load_personas()
    selected_key = st.selectbox(
        "👤 Simulate Accessibility Experience",
        options=list(personas.keys()),
        format_func=lambda key: personas[key]["label"]
    )

    simulation = simulate_experience(st.session_state["results"]["html"], selected_key)

    if isinstance(simulation, dict) and simulation.get("error"):
        st.error(f"Simulator Error: {simulation['error']}")
    else:
        st.subheader(f"🔍 Accessibility Persona Simulation — {personas[selected_key]['label']}")
        st.markdown(simulation)

# --- Footer ---
st.caption("Free: 1 scan/day. Pro: Unlimited + exports + code fixes. Agency: Multi-domain + white-label. Enterprise: Custom.")
