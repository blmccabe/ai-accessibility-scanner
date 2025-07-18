import streamlit as st
import os
from utils import get_user_tier, fetch_html, analyze_accessibility, export_to_pdf, export_to_csv, export_to_excel
import stripe

# User session
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'tier' not in st.session_state:
    st.session_state.tier = 'Free'
if 'scan_count' not in st.session_state:
    st.session_state.scan_count = 0
if 'results' not in st.session_state:
    st.session_state.results = None

# UI
st.title("AI Accessibility Scanner: WCAG Compliance for Small Sites")

email = st.text_input("Email to login/check tier")
if email:
    if '@' in email and '.' in email[email.index('@'):] and len(email) >= 10:
        st.session_state.user_email = email
        st.session_state.tier = get_user_tier(email)
        st.info(f"Your tier: {st.session_state.tier}")
    else:
        st.error("Invalid email format. Use e.g., name@example.com (at least 10 characters).")
        st.session_state.user_email = None
        st.session_state.tier = 'Free'

# Always show upgrade options in sidebar with tooltips
st.sidebar.title("Upgrade Options")
if st.sidebar.button("Upgrade to Pro ($9/mo)", help="Unlimited scans + AI summary + exports"):
    if not st.session_state.user_email:
        st.sidebar.error("Enter a valid email in the main area first!")
    else:
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': os.getenv("STRIPE_PRO_PRICE_ID"), 'quantity': 1}],
                mode='subscription',
                success_url=os.getenv("DOMAIN", "http://localhost:8501") + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=os.getenv("DOMAIN", "http://localhost:8501"),
                customer_email=st.session_state.user_email
            )
            st.sidebar.success("Redirecting to payment...")
            st.markdown(f"""
                <script>
                window.location.href = '{session.url}';
                </script>
                """, unsafe_allow_html=True)
            st.markdown(f"[Click if not redirected]({session.url})", unsafe_allow_html=True)
        except Exception as e:
            st.sidebar.error(f"Error starting payment: {str(e)}. Check if STRIPE_PRO_PRICE_ID, STRIPE_SECRET_KEY, and DOMAIN are set in .env.")

if st.sidebar.button("Upgrade to Agency ($49/mo)", help="Multi-domain + white-label + team features"):
    if not st.session_state.user_email:
        st.sidebar.error("Enter a valid email in the main area first!")
    else:
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{'price': os.getenv("STRIPE_AGENCY_PRICE_ID"), 'quantity': 1}],
                mode='subscription',
                success_url=os.getenv("DOMAIN", "http://localhost:8501") + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=os.getenv("DOMAIN", "http://localhost:8501"),
                customer_email=st.session_state.user_email
            )
            st.sidebar.success("Redirecting to payment...")
            st.markdown(f"""
                <script>
                window.location.href = '{session.url}';
                </script>
                """, unsafe_allow_html=True)
            st.markdown(f"[Click if not redirected]({session.url})", unsafe_allow_html=True)
        except Exception as e:
            st.sidebar.error(f"Error starting payment: {str(e)}. Check if STRIPE_AGENCY_PRICE_ID, STRIPE_SECRET_KEY, and DOMAIN are set in .env.")

if st.session_state.tier == 'Free':
    st.warning("1 scan/day. Upgrade for more.")
    if st.session_state.scan_count >= 1:
        st.error("Free limit reached. Upgrade in sidebar!")
        # Show previous results if any
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
                    pdf_output = export_to_pdf(results)
                    st.download_button("Download PDF", pdf_output, file_name="scan_report.pdf", mime="application/pdf", key="pdf_download")
                with col2:
                    csv_value = export_to_csv(results)
                    st.download_button("Download CSV", csv_value, file_name="scan_report.csv", mime="text/csv", key="csv_download")
                with col3:
                    excel_value = export_to_excel(results)
                    st.download_button("Download Excel", excel_value, file_name="scan_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_download")
        st.stop()

url = st.text_input("Website URL (e.g., https://example.com)")
if st.button("Scan Site") and st.session_state.user_email:
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
                        pdf_output = export_to_pdf(results)
                        st.download_button("Download PDF", pdf_output, file_name="scan_report.pdf", mime="application/pdf", key="pdf_download")
                    with col2:
                        csv_value = export_to_csv(results)
                        st.download_button("Download CSV", csv_value, file_name="scan_report.csv", mime="text/csv", key="csv_download")
                    with col3:
                        excel_value = export_to_excel(results)
                        st.download_button("Download Excel", excel_value, file_name="scan_report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="excel_download")

st.caption("Free: 1 scan/day. Pro: Unlimited + exports + code fixes. Agency: Multi-domain + white-label. Enterprise: Custom.")