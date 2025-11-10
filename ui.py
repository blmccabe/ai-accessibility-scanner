# ui.py (Added unique keys for export buttons, ARIA for tabs via custom labels, tooltips if needed)
import streamlit as st
import os
import logging
import random
import time

def render_logo_and_header():
    # Top banner area with fixed left-aligned logo and right-aligned title
    banner = st.container()
    with banner:
        c1, c2 = st.columns([0.22, 0.78], gap="small")
        with c1:
            if os.path.exists("assets/logo.png"):
                # Keep the logo small and left-anchored
                st.image("assets/logo.png", width=110)
            else:
                st.markdown("### **NexAssistAI**")
        with c2:
            st.markdown("## NexAssistAI")
            st.caption("AI-powered WCAG accessibility scanner (WCAG 2.2)")

def render_plan_message(tier):
    if tier == "Free":
        st.info("👤 Free: 1 scan/day. Upgrade for more.")
    elif tier == "Pro":
        st.success("🚀 Pro User: Unlimited scans, PDF/CSV exports, and code fixes.")
        if st.button("Upgrade to Agency for Multi-Domain Support ($49/mo)", key="pro_to_agency"):
            st.session_state["upgrade_trigger"] = "STRIPE_AGENCY_PRICE_ID"
            st.rerun()
    elif tier == "Agency":
        st.success("🏢 Agency Tier: Multi-domain support and white-labeled reports.")
    elif tier == "Enterprise":
        st.success("🏢 Enterprise Tier: Custom scan workflows and APIs.")

def render_email_url_form():
    st.markdown("### Get Started")
    st.markdown("Enter your **work email** and the **website URL** you want to scan.")

    default_email = st.session_state.get("user_email", "") or st.session_state.get("email", "")
    default_url = st.session_state.get("url", "")

    with st.form("email_url_form", clear_on_submit=False):
        email = st.text_input(
            "📧 Work Email",
            value=default_email,
            key="email_input",
            placeholder="name@company.com",
            help="Use the same email you use for billing so we can match your plan."
        )
        url = st.text_input(
            "🌐 Website URL (e.g., https://example.com)",
            value=default_url,
            key="url_input",
            placeholder="https://example.com",
            help="Include https:// if possible. We’ll normalize it either way."
        )

        # Full scan checkbox ONLY lives here (for paid tiers it’s useful, for Free it’s ignored)
        st.checkbox(
            "Full scan (slower but complete)",
            value=st.session_state.get("full_scan", False),
            key="full_scan",
            help="Uncheck for quicker preview"
        )

        submitted = st.form_submit_button("🔍 Scan Site")

    # Update email/url state for consistency (do NOT set full_scan here)
    if email:
        st.session_state["user_email"] = email
        st.session_state["email"] = email
    if url:
        st.session_state["url"] = url

    return email, url, submitted

def render_help_link():
    help_url = os.getenv("HELP_URL", "https://www.w3.org/WAI/standards-guidelines/wcag/")
    st.markdown(f"📘 [First time using this? Click here for help.]({help_url})")

def render_results(results):
    logging.info(f"Debug: Entering render_results with results keys: {list(results.keys()) if results else 'None'}")
    if results is None or not isinstance(results, dict):
        st.warning("No scan results available. Try running a scan again.")
        logging.info("render_results: No results or invalid results format")
        return
    st.subheader("AI Summary", divider="grey")
    summary = results.get("summary", "No summary provided.")
    st.write(summary if summary else "No summary available.")
    score = results.get("score", "N/A")
    st.metric("Score", score if score != 0 else "N/A")
    st.caption(results.get("disclaimer", "AI-generated; not a full manual audit."))
    issues = results.get("issues", [])
    logging.info(f"Debug: Issues count in render_results: {len(issues)}")
    if not issues:
        st.warning("No accessibility issues found or analysis failed.")
        logging.info("render_results: No issues found")
    else:
        tabs = st.tabs(["Perceivable", "Operable", "Understandable", "Robust"])
        categories = {"Perceivable": [], "Operable": [], "Understandable": [], "Robust": []}
        for issue in issues:
            category = issue.get('category', 'Unknown')
            if category in categories:
                categories[category].append(issue)
            elif issue.get('criterion', '').startswith('1'):
                categories["Perceivable"].append(issue)
            elif issue.get('criterion', '').startswith('2'):
                categories["Operable"].append(issue)
            elif issue.get('criterion', '').startswith('3'):
                categories["Understandable"].append(issue)
            elif issue.get('criterion', '').startswith('4'):
                categories["Robust"].append(issue)
        for i, category in enumerate(categories):
            with tabs[i]:
                if not categories[category]:
                    st.info(f"No {category} issues detected.")
                for issue in categories[category]:
                    with st.expander(f"{issue.get('criterion', 'Unknown')} ({issue.get('severity', 'N/A')})", expanded=False):
                        st.markdown(f"**Issue:** {issue.get('description', 'No description')}")
                        st.markdown(f"**Fix:** {issue.get('fix', 'No fix provided')}")
                        st.markdown(f"**Confidence:** {issue.get('confidence', 'N/A')}")
                        code_fix = issue.get('code_fix', 'N/A')
                        if code_fix and code_fix != "N/A":
                            if st.session_state.tier in ['Pro', 'Agency']:
                                st.code(code_fix, language='html')
                                escaped_code = code_fix.replace('`', '\\`')
                                copy_button = f"""
                                <button onclick="navigator.clipboard.writeText(`{escaped_code}`)" aria-label="Copy code snippet to clipboard" role="button">Copy Code</button>
                                """
                                st.markdown(copy_button, unsafe_allow_html=True)
                            else:
                                st.info("Code fixes available in Pro/Agency tiers. Upgrade to see.")
                        else:
                            st.warning("No code fix generated for this issue.")
def render_export_buttons(results):
    logging.info(f"render_export_buttons: results_keys={list(results.keys()) if results else None}, tier={st.session_state.get('tier', 'Unknown')}")
    if not results or not all(key in results for key in ["pdf", "csv", "excel"]):
        st.error("Export files not available. Try scanning again.")
        logging.info("render_export_buttons: Missing results or export keys")
        return
    if st.session_state.tier not in ['Pro', 'Agency', 'Enterprise']:
        st.warning("Exports available in Pro tiers. Upgrade to unlock.")
        logging.info("render_export_buttons: User not in Pro/Agency/Enterprise tier")
        return
    st.subheader("📤 Export Report")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.download_button("Download PDF", results["pdf"], file_name="scan_report.pdf", mime="application/pdf", key="download_pdf"):
            logging.info("PDF download triggered")
    with col2:
        if st.download_button("Download CSV", results["csv"], file_name="scan_report.csv", mime="text/csv", key="download_csv"):
            logging.info("CSV download triggered")
    with col3:
        if st.download_button("Download Excel", results["excel"], file_name="scan_report.xlsx", mime="application/vnd.ms-excel", key="download_excel"):
            logging.info("Excel download triggered")