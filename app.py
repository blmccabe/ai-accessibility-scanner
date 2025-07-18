import streamlit as st
import os
from utils import get_user_tier, fetch_html, analyze_accessibility, export_to_pdf, export_to_csv, export_to_excel
import stripe

# Custom CSS for design
st.markdown("""
    <style>
    .stButton > button {
        width: 100%;
        background-color: #007bff;
        color: white;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #0056b3;
    }
    .stTextInput > div > div > input {
        background-color: #f8f9fa;
    }
    .reportview-container {
        background-color: #ffffff;
    }
    </style>
    """, unsafe_allow_html=True)

# Session state defaults
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'tier' not in st.session_state:
    st.session_state.tier = 'Free'
if 'scan_count' not in st.session_state:
    st.session_state.scan_count = 0
if 'results' not in st.session_state:
    st.session_state.results = None
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# Dark mode toggle
if st.sidebar.checkbox("Dark Mode", value=st.session_state.dark_mode, help="Switch to dark theme for better contrast in low light."):
    st.session_state.dark_mode = True
    st.markdown("""
        <style>
        .reportview-container {
            background-color: #121212;
            color: #ffffff;
        }
        .stTextInput > div > div > input {
            background-color: #2c2c2c;
            color: #ffffff;
        }
        .stButton > button {
            background-color: #0056b3;
        }
        .stMarkdown, .stInfo, .stError, .stWarning {
            color: #f0f0f0;
        }
        </style>
        """, unsafe_allow_html=True)
else:
    st.session_state.dark_mode = False

# Logo and intro
with st.container():
    st.image("assets/logo.png", width=80)

st.title("NexAssistAI: AI Accessibility Scanner")
st.markdown("### Scan your site for accessibility issues in seconds.")
st.markdown("_Start by entering your work email and website URL below._")

# Prefill email from URL query
query_params = st.query_params if hasattr(st, "query_params") else st.experimental_get_query_params()
prefill_email = query_params.get("email", [None])[0]
if prefill_email and not st.session_state.get("user_email"):
    if '@' in prefill_email and '.' in prefill_email[prefill_email.index('@'):]:
        st.session_state.user_email = prefill_email
        st.session_state.tier = get_user_tier(prefill_email)

email = st.text_input("Work Email", placeholder="you@company.com")
if email:
    if '@' in email and '.' in email[email.index('@'):] and len(email) >= 10:
        st.session_state.user_email = email
        st.session_state.tier = get_user_tier(email)
        st.info(f"Your tier: {st.session_state.tier}")
    else:
        st.error("Invalid email format. Use e.g., name@example.com (at least 10 characters).")
        st.session_state.user_email = None
        st.session_state.tier = 'Free'

st.markdown("""
Welcome! This tool scans any website for accessibility issues using WCAG 2.1/2.2 standards.  
Start by entering a URL — Free users get 1 scan/day. Upgrade for more.
""")

# Upgrade sidebar
st.sidebar.title("Upgrade Options")

def create_checkout_button(label, price_env_var):
    if st.sidebar.button(label):
        if not st.session_state.user_email:
            st.sidebar.error("Enter a valid email in the main area first!")
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
            st.sidebar.error(f"Error starting payment: {str(e)}")

create_checkout_button("Upgrade to Pro ($9/mo)", "STRIPE_PRO_PRICE_ID")
create_checkout_button("Upgrade to Agency ($49/mo)", "STRIPE_AGENCY_PRICE_ID")

# Scan logic
url = st.text_input("Website URL (e.g., https://example.com)", help="Enter a website URL to scan for accessibility issues.")

if st.button("Scan Site") and st.session_state.user_email:
    with st.expander("📘 First time using this? Click here for help."):
        st.markdown("""
        **How it works:**

        1. Enter your **work email** to check your tier.
        2. Paste a **website URL** and click **Scan Site**.
        3. See **AI-powered accessibility issues**, potential fixes, and a score.
        4. Download reports in PDF, CSV, Excel (Pro/Agency only).

        ⚠️ **Free users** get 1 scan/day — upgrade in the sidebar to unlock full access.
        """)

    if st.session_state.tier == 'Free' and st.session_state.scan_count >= 1:
        st.error("Free limit reached. Upgrade in sidebar!")
        if st.session_state.results:
            results = st.session_state.results
            st.subheader(f"Score: {results.get('score', 'N/A')}")
            st.info(results["disclaimer"])

            if st.session_state.tier != 'Free':
                st.subheader("AI Summary")
                st.write(results.get('summary', 'No summary available.'))

            for issue in results.get('issues', []):
                st.markdown(f"**{issue['criterion']} ({issue['severity']})**: {issue['description']}")
                st.write(f"Fix: {issue['fix']}")
                if st.session_state.tier in ['Pro', 'Agency']:
                    st.write("Code Fix:")
                    st.code(issue.get('code_fix', 'N/A'), language='html')

            if st.session_state.tier in ['Pro', 'Agency']:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.download_button("Download PDF", export_to_pdf(results), file_name="scan_report.pdf", mime="application/pdf")
                with col2:
                    st.download_button("Download CSV", export_to_csv(results), file_name="scan_report.csv", mime="text/csv")
                with col3:
                    st.download_button("Download Excel", export_to_excel(results), file_name="scan_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.stop()

    st.session_state.scan_count += 1 if st.session_state.tier == 'Free' else 0

    with st.spinner("Scanning..."):
        html = fetch_html(url)
        if "Error" in html:
            st.error(html)
        else:
            results = analyze_accessibility(html)
            st.session_state.results = results
            if "error" in results:
                st.error(results["error"])
            else:
                st.subheader(f"Score: {results.get('score', 'N/A')}")
                st.info(results["disclaimer"])

                if st.session_state.tier != 'Free':
                    st.subheader("AI Summary")
                    st.write(results.get('summary', 'No summary available.'))

                for issue in results.get('issues', []):
                    st.markdown(f"**{issue['criterion']} ({issue['severity']})**: {issue['description']}")
                    st.write(f"Fix: {issue['fix']}")
                    if st.session_state.tier in ['Pro', 'Agency']:
                        st.write("Code Fix:")
                        st.code(issue.get('code_fix', 'N/A'), language='html')

                if st.session_state.tier in ['Pro', 'Agency']:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.download_button("Download PDF", export_to_pdf(results), file_name="scan_report.pdf", mime="application/pdf")
                    with col2:
                        st.download_button("Download CSV", export_to_csv(results), file_name="scan_report.csv", mime="text/csv")
                    with col3:
                        st.download_button("Download Excel", export_to_excel(results), file_name="scan_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.caption("Free: 1 scan/day. Pro: Unlimited + exports + code fixes. Agency: Multi-domain + white-label. Enterprise: Custom.")
