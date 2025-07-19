import streamlit as st

def render_header():
    st.title("NexAssistAI: AI Accessibility Scanner")
    st.caption("Scan your site for accessibility issues in seconds.")

def render_plan_message(tier):
    if tier == "Free":
        st.info("👤 Free: 1 scan/day. Upgrade for more.")
    elif tier == "Pro":
        st.success("🚀 Pro User: Unlimited scans, PDF/CSV exports, and code fixes.")
    elif tier == "Agency":
        st.success("🏢 Agency Tier: Multi-domain support and white-labeled reports.")
    elif tier == "Enterprise":
        st.success("🏢 Enterprise Tier: Custom scan workflows and APIs.")

def render_email_url_form():
    st.subheader("Start by entering your work email and website URL below.")
    email = st.text_input("Work Email", key="email_input")
    url = st.text_input("Website URL (e.g., https://example.com)", key="url_input")
    return email, url

def render_help_link():
    st.markdown("📘 [First time using this? Click here for help.](https://wcag.com)")

def render_results(results):
    st.subheader("AI Summary")
    st.write(results.get("summary", "No summary provided."))
    st.metric("Score", results.get("score", "N/A"))
    st.caption(results.get("disclaimer", "AI-generated; not a full manual audit."))

    for issue in results.get("issues", []):
        with st.expander(f"{issue['criterion']} ({issue['severity']})"):
            st.markdown(f"**Issue:** {issue['description']}")
            st.markdown(f"**Fix:** {issue['fix']}")
            if issue['code_fix'] and issue['code_fix'] != "N/A":
                st.code(issue['code_fix'], language='html')

def render_export_buttons(results):
    st.subheader("📤 Export Report")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("Download PDF", results["pdf"], file_name="scan_report.pdf", mime="application/pdf")
    with col2:
        st.download_button("Download CSV", results["csv"], file_name="scan_report.csv", mime="text/csv")
    with col3:
        st.download_button("Download Excel", results["excel"], file_name="scan_report.xlsx", mime="application/vnd.ms-excel")
