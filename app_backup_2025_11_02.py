# app.py (Fixed auto-scan post-upgrade)
import io
import streamlit as st
import os
import sqlite3
from datetime import datetime
import re
import time
import pickle
from utils import get_user_tier, fetch_page_content, analyze_accessibility, export_to_pdf, export_to_csv, export_to_excel, normalize_url, create_checkout_button, run_checkout_session
import stripe
from simulator.simulator import load_personas, simulate_experience, demo_simulation
from ui import render_logo_and_header, render_email_url_form, render_help_link, render_plan_message, render_results, render_export_buttons
import logging
from gtts import gTTS
import tempfile
import requests
from playwright.sync_api import sync_playwright

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
        background-color: #315b7c;
        color: white;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #234670;
    }
    .reportview-container {
        background-color: #ffffff;
    }
    .stSelectbox > div > div > select {
        background-color: #f8f9fa;
    }
    .upgrade-button {
        background-color: #315b7c;
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 16px;
        display: block;
        margin-bottom: 10px;
        text-align: center;
    }
    .upgrade-button:hover {
        background-color: #234670;
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
    'html': None,
    'dark_mode': False,
    'menu_index': 0,
    'scan_cache': {}  # Cache for scan results
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# Initialize SQLite database
conn = sqlite3.connect("scans.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS scans (email TEXT, count INTEGER, date TEXT)")
conn.commit()
conn.close()

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
        .stSelectbox > div > div > select { background-color: #2c2c2c; color: #ffffff; }
        </style>
    """, unsafe_allow_html=True)
else:
    st.session_state.dark_mode = False
    st.markdown("<style> .reportview-container { background-color: #ffffff; } </style>", unsafe_allow_html=True)

# --- Query Parameter Handling ---
def load_results_from_db(email):
    """Load scan results from SQLite."""
    conn = sqlite3.connect("scans.db")
    cursor = conn.cursor()
    cursor.execute("SELECT results FROM results WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return pickle.loads(result[0])
    return None
session_id = st.query_params.get("session_id")
session_id = session_id[0] if isinstance(session_id, list) and session_id else session_id if isinstance(session_id, str) else None

if session_id:
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        email = checkout_session.get("customer_email") or checkout_session.get("customer_details", {}).get("email")
        
        if email and re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email):
            st.session_state.user_email = email
            st.session_state.email = email  # Ensure form pre-fills email
            st.session_state.tier = get_user_tier(email)

            # Retry tier fetch if still Free
            if st.session_state.tier == 'Free':
                time.sleep(2)
                st.session_state.tier = get_user_tier(email)
                logging.info("🔁 Retried tier fetch after delay.")

            logging.info(f"✅ Tier after upgrade: {st.session_state.tier}")

            # Load previous results from SQLite
            saved_results = load_results_from_db(email)
            if saved_results:
                st.session_state["results"] = saved_results
                st.session_state["url"] = saved_results.get("url", "")
                st.session_state["html"] = saved_results.get("html", "")
                logging.info(f"Restored results for email={email}, url={st.session_state['url']}")
            else:
                st.session_state["menu_index"] = 0  # Show "Get Started" if no results
            st.session_state["email_input"] = email
            st.session_state["trigger_scan_after_upgrade"] = st.session_state.tier in ["Pro", "Agency", "Enterprise"] and st.session_state.get("url")
            st.session_state["upgrade_success"] = True
            st.query_params.clear()
            logging.info(f"Post-redirect state: email={st.session_state.get('email')}, url={st.session_state.get('url')}, tier={st.session_state.tier}, menu_index={st.session_state.menu_index}")
            
    except Exception as e:
        st.error(f"❌ Error retrieving Stripe session: {str(e)}")

# --- Display Upgrade Success Message ---
if st.session_state.get("upgrade_success"):
    st.success("Subscription successful! Your plan has been updated. Enjoy unlimited scans.")
    st.session_state.pop("upgrade_success", None)  # Clear flag after display

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
    cursor.execute("CREATE TABLE IF NOT EXISTS scans (email TEXT, count INTEGER, date TEXT)")
    cursor.execute("INSERT OR REPLACE INTO scans (email, count, date) VALUES (?, COALESCE((SELECT count + 1 FROM scans WHERE email = ? AND date = ?), 1), ?)",
                  (email, email, datetime.utcnow().date().isoformat(), datetime.utcnow().date().isoformat()))
    conn.commit()
    conn.close()

def save_results_to_db(email, results):
    """Save scan results to SQLite."""
    conn = sqlite3.connect("scans.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS results (email TEXT PRIMARY KEY, results BLOB)")
    serialized_results = pickle.dumps(results)
    cursor.execute("INSERT OR REPLACE INTO results (email, results) VALUES (?, ?)", (email, serialized_results))
    conn.commit()
    conn.close()

# --- Sidebar Menu for Navigation ---
def update_menu(*args, **kwargs):
    st.session_state["menu_index"] = menu_options.index(st.session_state["menu"])
    logging.info(f"Menu updated to: {st.session_state['menu']}")
    # Clear results display when switching menus
    if st.session_state.get("menu_index") not in [1]:  # 1 is "Scan Results" index
        st.session_state["results"] = None

st.sidebar.title("Navigation")
menu_options = ["🔍 Get Started", "📊 Scan Results", "👤 Persona Simulation"]
if st.session_state.tier in ['Pro', 'Agency', 'Enterprise']:
    menu_options.append("📤 Exports")
menu = st.sidebar.selectbox(
    "Go to",
    menu_options,
    index=st.session_state.get("menu_index", 0),
    key="menu",
    label_visibility="visible",
    help="Navigate to different sections of your scan results",
    on_change=update_menu,
    args=("aria-label", "Main navigation menu")
)
st.session_state["menu_index"] = menu_options.index(menu)

# --- Sticky Upgrade Buttons in Sidebar ---
st.sidebar.markdown("---")
st.sidebar.markdown("### Upgrade Your Plan")
if st.sidebar.button("Refresh Tier", key="refresh_tier_button"):
    if st.session_state.user_email:
        st.session_state.tier = get_user_tier(st.session_state.user_email)
        st.session_state["upgrade_success"] = True  # Trigger success message
if st.session_state.tier not in ['Pro', 'Agency', 'Enterprise']:
    if st.session_state.get("user_email"):
        create_checkout_button("🔓 Unlock Pro ($9/mo)", "STRIPE_PRO_PRICE_ID", is_sidebar=True)
        create_checkout_button("🏢 Agency Access ($49/mo)", "STRIPE_AGENCY_PRICE_ID", is_sidebar=True)
    else:
        st.sidebar.warning("🔒 Enter your email above to unlock upgrade options.")

# Only run once on first load — otherwise don't reset scan state
if "submitted" not in st.session_state:
    st.session_state["submitted"] = False

if menu == "🔍 Get Started":
    # Ensure email and url persist from session state
    if "email" not in st.session_state:
        st.session_state["email"] = ""
    if "url" not in st.session_state:
        st.session_state["url"] = ""

    email, url, submitted = render_email_url_form()
    logging.info(f"Form submitted: email={email}, url={url}, submitted={submitted}")
    if submitted:
        if url:  # Require only URL for free users
            st.session_state["email"] = email if email else "anonymous@freeuser.com"
            st.session_state["user_email"] = st.session_state["email"]
            st.session_state["url"] = url
            st.session_state["submitted"] = True
            logging.info(f"Starting scan with email={st.session_state['email']}, url={st.session_state['url']}")
            st.session_state["menu_index"] = 1  # Switch to "Scan Results"
        else:
            st.error("Please provide a website URL.")

    # --- Logo + header ---
    render_logo_and_header()

    # --- Get Started Form ---
    st.info("👋 New here? Enter your info below to run a full scan and see results in seconds.")

    # --- Plan Message ---
    render_plan_message(st.session_state.tier)

    # --- Help Link and Expander ---
    render_help_link()
    with st.expander("📘 First time here? Click for help", expanded=False):
        st.markdown("""
        **How it works:**
        1. Enter your **work email** to unlock your tier.
        2. Paste a **website URL** and click **Scan Site**.
        3. View **AI-generated issues, summaries, scores, and reports**.
        4. Upgrade for unlimited scans + AI summaries + code fixes + PDF/CSV/Excel export.
        """)

    # --- Validate and set user info ---
    def validate_email():
        if 'email_input' in st.session_state and not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', st.session_state.email_input):
            st.error("Invalid email format. Use name@example.com.")
        else:
            st.session_state.user_email = st.session_state.email_input
            st.session_state.tier = get_user_tier(st.session_state.user_email)

    if st.session_state.get("email_input"):
        validate_email()

if st.session_state.get("trigger_scan_after_upgrade") and st.session_state.tier in ["Pro", "Agency", "Enterprise"]:
    email = st.session_state.get("email", "anonymous@freeuser.com")
    url = st.session_state.get("url", "")
    cache_key = f"{email}_{url}_False"
    if st.session_state.get("results") and st.session_state["results"].get("url"):
        logging.info(f"Using existing results for {cache_key}")
        st.session_state["menu_index"] = 1  # Switch to "Scan Results"
        st.session_state["trigger_scan_after_upgrade"] = False
        st.success("Auto-scan results loaded from cache!")
    elif url:
        logging.info(f"⚡ Auto-scan triggered: tier={st.session_state.tier}, email={email}, url={url}")
        if cache_key in st.session_state.scan_cache:
            st.session_state["results"] = st.session_state.scan_cache[cache_key]
            logging.info(f"📦 Cache hit for auto-scan: {cache_key}")
            st.session_state["html"] = st.session_state["results"]["html"]
            st.session_state["menu_index"] = 1
            st.session_state["trigger_scan_after_upgrade"] = False
            st.success("Auto-scan results loaded from cache!")
        else:
            with st.spinner("Running auto-scan..."):
                increment_scan_count(email)
                try:
                    normalized_url = normalize_url(url.strip())
                    result = fetch_page_content(normalized_url)
                    if result["success"]:
                        html = result["html"]
                        st.session_state["html"] = html
                        results = analyze_accessibility(html, abbreviated=True)
                        results["html"] = html
                        results["url"] = normalized_url
                        results["pdf"] = export_to_pdf(results)
                        results["csv"] = export_to_csv(results)
                        results["excel"] = export_to_excel(results)
                        st.session_state.scan_cache[cache_key] = results
                        st.session_state["results"] = results
                        save_results_to_db(email, results)
                        logging.info(f"📦 Auto-scan results cached: {cache_key}")
                        st.success("Auto-scan complete!")
                    else:
                        st.error(result.get("error", "Failed to fetch URL during auto-scan."))
                        st.session_state["trigger_scan_after_upgrade"] = False
                except Exception as e:
                    st.error(f"Auto-scan failed: {str(e)}. Please try scanning manually.")
                    st.session_state["trigger_scan_after_upgrade"] = False
    else:
        st.warning("No previous URL found. Please enter a URL to scan.")
        st.session_state["trigger_scan_after_upgrade"] = False

# Consolidated scan logic (runs if submitted and URL exists)
if st.session_state.get("submitted") and st.session_state.get("url"):
    email = st.session_state.get("user_email", "")
    url = st.session_state.get("url", "")
    tier = get_user_tier(email)
    st.session_state.tier = tier
    logging.info(f"🧪 Scan initiated: tier={tier}, email={email}, url={url}")

    # Limit check
    if tier == 'Free' and check_scan_limit(email) >= 1:
        st.error("Free scan limit reached. Upgrade for more.")
        if st.button("Retry", key="retry_limit"):
            st.stop()

    # Checkbox for full scan
    full_scan = st.checkbox(
        "Full scan (slower but complete)",
        value=False,
        help="Uncheck for quicker preview"
    ) if tier in ['Pro', 'Agency', 'Enterprise'] else False

# === SAFETY: Ensure these are always defined before cache_key ===
email = st.session_state.get("user_email", st.session_state.get("email", "anonymous@freeuser.com"))
url = st.session_state.get("url", "")
full_scan = st.session_state.get("full_scan", False)

    # Caching
cache_key = f"{email}_{url}_{full_scan}"

if cache_key in st.session_state.scan_cache:
    results = st.session_state.scan_cache[cache_key]
    logging.info(
        f"📦 Cache hit: {cache_key}, "
        f"results_keys={list(results.keys())}, "
        f"issues_count={len(results.get('issues', []))}"
    )
    st.session_state["results"] = results
    st.session_state["html"] = results["html"]
    st.session_state["menu_index"] = menu_options.index("📊 Scan Results")
    st.session_state["submitted"] = False
    st.success("Scan results loaded from cache!")

else:
    with st.spinner("Scanning..."):
        increment_scan_count(email)
        try:
            normalized_url = normalize_url(url.strip())
            logging.info(f"🔗 Normalized URL: {normalized_url}")

            result = fetch_page_content(normalized_url)
            if not result["success"]:
                st.error(result.get("error", "Unknown error while fetching page."))
                logging.error(f"[fetch_page_content error] {result.get('error', 'Unknown')}")
                auto_retry = st.checkbox("Auto-retry", value=False, key="auto_retry_fetch")
                if auto_retry:
                    time.sleep(2)
                if st.button("Retry", key="retry_fetch"):
                    st.stop()

            html = result["html"]
            st.session_state["html"] = html
            results = analyze_accessibility(html, abbreviated=not full_scan)
            logging.info(
                f"📊 Analysis results: keys={list(results.keys())}, "
                f"issues_count={len(results.get('issues', []))}, "
                f"summary={results.get('summary', 'No summary')}, "
                f"score={results.get('score', 'N/A')}"
            )
            st.session_state["results"] = results
            st.session_state["results"]["html"] = html
            st.session_state["results"]["url"] = normalized_url

            if "error" in results:
                st.error(results["error"])
                logging.error(f"[Analysis error] {results['error']}")
                if st.button("Retry", key="retry_analysis"):
                    st.stop()

            results["pdf"] = export_to_pdf(results)
            results["csv"] = export_to_csv(results)
            results["excel"] = export_to_excel(results)

            st.session_state.scan_cache[cache_key] = results
            save_results_to_db(email, results)
            st.session_state["menu_index"] = menu_options.index("📊 Scan Results")
            logging.info(f"📦 Results cached: {cache_key}, issues_count={len(results.get('issues', []))}")
            st.session_state["submitted"] = False
            st.success("Scan complete!")

        except Exception as e:
            st.error("❌ That URL is invalid. Try something like https://nasa.gov or nasa.gov.")
            logging.error(f"[normalize_url error] {e}")
            if st.button("Retry", key="retry_url_error"):
                st.stop()
# ================================
# === SAFETY: Ensure variables always exist ===
# ================================

# These make sure email, url, and full_scan are never undefined
email = st.session_state.get("user_email", st.session_state.get("email", "anonymous@freeuser.com"))
url = st.session_state.get("url", "")
full_scan = st.session_state.get("full_scan", False)

# If no URL has been entered yet, keep it blank so normalize_url doesn't fail
if not url:
    url = ""

# Build a consistent cache key for all scans
cache_key = f"{email}::{url}::{full_scan}"

# Optional: helpful log line so you can see it’s working
logging.info(f"[Init Vars] email={email}, url={url}, full_scan={full_scan}")

# ================================
# === RESULTS / SIMULATION / EXPORTS ===
# ================================

# --- Scan Results Page ---
if menu == "📊 Scan Results":
    if st.session_state.get("results"):
        render_results(st.session_state["results"])
        logging.info("Rendering results from session state in Scan Results menu")
    else:
        st.warning("No scan results available. Please run a scan from the Get Started menu.")
        logging.info("No results in session state for Scan Results menu")

# --- Persona Simulation Page ---
elif menu == "👤 Persona Simulation":
    # ✅ Don't clear results anymore
    if st.session_state.get("results") and st.session_state["results"].get("html"):
        if st.session_state.tier in ['Pro', 'Agency', 'Enterprise']:
            if st.checkbox("Run Simulation (paid feature)",
                           help="Simulate how users with disabilities experience the site",
                           key="run_simulation"):
                personas = load_personas()
                selected_key = st.selectbox(
                    "👤 Simulate Accessibility Experience",
                    options=list(personas.keys()),
                    format_func=lambda key: personas[key]["label"],
                    help="Choose a persona to simulate (e.g., blind user)",
                    key="paid_persona_select"
                )
                if selected_key:
                    st.info(personas[selected_key]["description"])
                    with st.spinner("Simulating experience..."):
                        simulation = simulate_experience(st.session_state["results"]["html"], selected_key)
                        if isinstance(simulation, dict) and simulation.get("error"):
                            st.error(f"Simulator Error: {simulation['error']}")
                        else:
                            st.subheader(f"🔍 Accessibility Persona Simulation — {personas[selected_key]['label']}")
                            st.markdown(simulation)

                            # Optional TTS playback
                            plain_text = simulation.replace('#', '').replace('-', '').replace('\n', ' ')[:200]
                            voice_speed = st.slider("Screen Reader Audio Speed", 0.5, 2.0, 1.0, key="paid_tts_speed")
                            if st.button("Play Simulation Audio", key="paid_tts_button"):
                                try:
                                    tts = gTTS(plain_text, slow=(voice_speed < 1.0))
                                    buffer = io.BytesIO()
                                    tts.write_to_fp(buffer)
                                    buffer.seek(0)
                                    st.audio(buffer, format="audio/mp3")
                                except Exception as e:
                                    logging.error(f"TTS Error: {str(e)}")
                                    st.error(f"Audio generation failed: {str(e)}")
        else:
            demo_simulation(st.session_state["results"]["html"])
            if st.button("Upgrade to Pro for Full Simulations ($9/mo)", key="simulation_upgrade_pro_main"):
                create_checkout_button("Upgrade to Pro for Full Simulations ($9/mo)", "STRIPE_PRO_PRICE_ID", is_sidebar=False)
    else:
        st.warning("Run a scan first to enable simulations.")

# --- Exports Page ---
elif menu == "📤 Exports":
    # ✅ Keep results available for export
    if st.session_state.get("results") and st.session_state.tier in ['Pro', 'Agency', 'Enterprise']:
        render_export_buttons(st.session_state["results"])
    else:
        st.warning("Exports available in Pro tiers. Upgrade to unlock.")
        st.markdown(
            """
            <style>
            .upgrade-button {
                background-color: #315b7c;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                display: block;
                margin-bottom: 10px;
                text-align: center;
            }
            .upgrade-button:hover {
                background-color: #234670;
            }
            </style>
            <a href='https://www.nexassistai.com/upgrade' class='upgrade-button' aria-label='Upgrade to Pro for exports'>Upgrade to Pro for Exports ($9/mo)</a>
            """,
            unsafe_allow_html=True
        )
# ================================
# === AUTO-SWITCH & STATE STABILITY ===
# ================================

GET_STARTED_IDX = menu_options.index("🔍 Get Started")
RESULTS_IDX = menu_options.index("📊 Scan Results")

# Only auto-switch to results if the user is currently on "Get Started"
if (
    st.session_state.get("submitted")
    and st.session_state.get("url")
    and st.session_state.get("menu_index", 0) == GET_STARTED_IDX
):
    st.session_state.menu_index = RESULTS_IDX
    menu = menu_options[st.session_state.menu_index]
    # Important: clear submitted so it won’t fire again on the next rerun
    st.session_state["submitted"] = False
    logging.info("Auto-switch: moved to Scan Results after submission (from Get Started only)")

if (
    st.session_state.get("trigger_scan_after_upgrade")
    and st.session_state.get("url")
    and st.session_state.get("menu_index", 0) != RESULTS_IDX
):
    st.session_state.menu_index = RESULTS_IDX
    menu = menu_options[st.session_state.menu_index]
    st.session_state.trigger_scan_after_upgrade = False
    logging.info("Auto-switch: moved to Scan Results after upgrade trigger")

# --- Footer ---
st.caption("Free: 1 scan/day. Pro: Unlimited + exports + code fixes. Agency: Multi-domain + white-label. Enterprise: Custom.")