# ui.py (No changes needed, but included for completeness)
import streamlit as st
import os

def render_logo_and_header():
    col1, col2 = st.columns([1, 3])
    with col1:
        if os.path.exists("assets/logo.png"):
            st.image("assets/logo.png", width=60)
        else:
            st.markdown("**NexAssistAI**")
    with col2:
        st.markdown("## NexAssistAI")
        st.caption("AI-powered WCAG accessibility scanner")

def render_plan_message(tier):
    if tier == "Free":
        st.info("👤 Free: 1 scan/day. Upgrade for more.")
    elif tier == "Pro":
        st.success("🚀 Pro User: Unlimited scans, PDF/CSV exports, and code fixes.")
    elif tier == "Agency":
        st.success("🏢 Agency Tier: Multi-domain support and white-labeled reports.")

def render_email_url_form():
    st.markdown("### Get Started")
    st.markdown("Enter your **work email** and the **website URL** you want to scan.")
    with st.form("scan_form", clear_on_submit=False):
        email = st.text_input("📧 Work Email", key="email_input", help="Enter your work email", placeholder="name@example.com", value=st.session_state.get("user_email", ""))
        url = st.text_input("🌐 Website URL (e.g., https://example.com)", key="url_input", help="Enter the website URL to scan", placeholder="https://example.com")
        submitted = st.form_submit_button("🔍 Scan Site")
    return email, url, submitted

def render_help_link():
    help_url = os.getenv("HELP_URL", "https://www.w3.org/WAI/standards-guidelines/wcag/")
    st.markdown(f"📘 [First time using this? Click here for help.]({help_url})")

def render_results(results):
    st.subheader("AI Summary", divider="grey")
    st.write(results.get("summary", "No summary provided."))
    st.metric("Score", results.get("score", "N/A"))
    st.caption(results.get("disclaimer", "AI-generated; not a full manual audit."))
    issues = results.get("issues", [])
    if not issues:
        st.warning("No accessibility issues found or analysis failed.")
    else:
        tabs = st.tabs(["Perceivable", "Operable", "Understandable", "Robust"])
        categories = {"Perceivable": [], "Operable": [], "Understandable": [], "Robust": []}
        for issue in issues:
            # Categorize based on WCAG criterion (e.g., 1.x = Perceivable)
            if issue.get('criterion', '').startswith('1'):
                categories["Perceivable"].append(issue)
            elif issue.get('criterion', '').startswith('2'):
                categories["Operable"].append(issue)
            elif issue.get('criterion', '').startswith('3'):
                categories["Understandable"].append(issue)
            elif issue.get('criterion', '').startswith('4'):
                categories["Robust"].append(issue)
        for i, category in enumerate(categories):
            with tabs[i]:
                for issue in categories[category]:
                    with st.expander(f"{issue.get('criterion', 'Unknown')} ({issue.get('severity', 'N/A')})", expanded=False):
                        st.markdown(f"**Issue:** {issue.get('description', 'No description')}")
                        st.markdown(f"**Fix:** {issue.get('fix', 'No fix provided')}")
                        code_fix = issue.get('code_fix', 'N/A')
                        if code_fix and code_fix != "N/A":
                            st.code(code_fix, language='html')
                            escaped_code = code_fix.replace('`', '\\`')
                            copy_button = f"""
                            <button onclick="navigator.clipboard.writeText(`{escaped_code}`)">Copy Code</button>
                            """
                            st.markdown(copy_button, unsafe_allow_html=True)

def render_export_buttons(results):
    st.subheader("📤 Export Report")
    if not all(key in results for key in ["pdf", "csv", "excel"]):
        st.error("Export files not available. Try scanning again.")
        return
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.download_button("Download PDF", results["pdf"], file_name="scan_report.pdf", mime="application/pdf")
    with col2:
        st.download_button("Download CSV", results["csv"], file_name="scan_report.csv", mime="text/csv")
    with col3:
        st.download_button("Download Excel", results["excel"], file_name="scan_report.xlsx", mime="application/vnd.ms-excel")