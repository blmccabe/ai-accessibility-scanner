import os
import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def fetch_html(url):
    """Fetch and parse HTML from URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return str(soup)  # Return full HTML as string for AI
    except Exception as e:
        return f"Error fetching URL: {str(e)}"

def analyze_accessibility(html_content):
    """Use AI to scan HTML for WCAG issues."""
    prompt = f"""
    Analyze this HTML for WCAG 2.1/2.2 accessibility issues. Focus on:
    - Perceivable: Missing alt text on images, color contrast (estimate if possible), text alternatives.
    - Operable: Keyboard navigation traps, ARIA roles/labels for interactive elements.
    - Understandable: Headings structure, form labels, error messages.
    - Robust: HTML validity, no deprecated elements.
    
    Respond only with valid JSON in this exact structure: {{"issues": [{{"criterion": "WCAG ref", "description": "Issue detail", "severity": "Low/Med/High", "fix": "Suggestion"}}], "score": "0-100 estimate", "disclaimer": "This is AI-generated; not a full manual audit. Consult WCAG experts."}}
    
    HTML: {html_content[:4000]}  # Truncate for token limits
    """

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.5,
            response_format={"type": "json_object"}  # Forces JSON output
        )
        result_text = response.choices[0].message.content.strip()
        import json
        return json.loads(result_text)
    except Exception as e:
        return {"error": str(e), "disclaimer": "Analysis failed."}

# Streamlit UI
st.title("AI Accessibility Scanner: WCAG Compliance for Small Sites")
st.markdown("Enter a URL to scan for accessibility issues. Get a report with fixes. Beta—MVP for testing.")

url = st.text_input("Website URL (e.g., https://example.com)")
if st.button("Scan Site"):
    with st.spinner("Fetching and analyzing..."):
        html = fetch_html(url)
        if "Error" in html:
            st.error(html)
        else:
            results = analyze_accessibility(html)
            if "error" in results:
                st.error(results["error"])
            else:
                st.subheader(f"Accessibility Score: {results.get('score', 'N/A')}")
                st.info(results["disclaimer"])
                
                for issue in results.get('issues', []):
                    st.markdown(f"**{issue['criterion']} ({issue['severity']})**: {issue['description']}")
                    st.write(f"Fix: {issue['fix']}")

st.caption("Free tier limited; upgrade for full scans/reports.")