# simulator.py (Added 60K limit, chunking, warning, merge, fallback personas)
import json
import logging
import os
from openai import OpenAI
import streamlit as st
import time  # Added: time.sleep for rate limits

logging.basicConfig(level=logging.INFO)

def load_personas():
    try:
        with open("simulator/personas.json", "r") as f:
            content = f.read().strip()
            if not content:
                raise ValueError("personas.json is empty")
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        logging.warning(f"Error loading personas.json: {str(e)}. Using fallback personas.")  # Added: fallback personas
        return {
            "blind_screen_reader": {
                "label": "Blind user with screen reader",
                "description": "Navigates entirely using keyboard and screen reader software.",
                "prompt": """You are simulating a user who is blind and relies fully on screen reader software to navigate the web. This user cannot see visual layout, images, or content. They use keyboard shortcuts and linear audio output to understand the structure of the page.

Pay special attention to:
- Page title, landmarks, heading structure
- Missing or non-descriptive alt text on images
- Buttons or links without labels
- Dynamic content that may not be announced
- Reading order and tab sequence

Highlight the biggest frustrations and recommend improvements to make this experience smoother for screen reader users."""
            },
            "low_vision_elderly": {
                "label": "Low-vision elderly person",
                "description": "Struggles with contrast, font size, and visual layout.",
                "prompt": """You are simulating an elderly user with low vision and declining visual acuity. This person struggles with small font sizes, low color contrast, dense content, and poor spacing. They may zoom in to read, use a magnifier, or have trouble tracking elements.

Evaluate:
- Text readability (size, contrast, spacing)
- Link and button visibility
- Zoom behavior (does layout break?)
- Visual clarity and clutter

Provide feedback on how readable and usable the page is for someone with reduced visual perception."""
            },
            "motor_impaired_keyboard": {
                "label": "Motor-impaired keyboard-only user",
                "description": "Cannot use a mouse, relies on keyboard for navigation.",
                "prompt": """You are simulating a user with a motor impairment who cannot use a mouse and relies entirely on keyboard navigation. They may use assistive devices like sip-and-puff or single-switch input.

Assess the experience based on:
- Tab order consistency
- Presence of visible focus indicators
- Availability of skip links
- Whether all interactive elements (forms, menus, modals) are accessible by keyboard
- Any keyboard traps or broken tab loops

Report on how frustrating or seamless the experience would be for a keyboard-only user."""
            }
        }

def simulate_experience(html, persona_key, abbreviated=True):
    personas = load_personas()
    if persona_key not in personas:
        return {"error": f"Unknown persona: {persona_key}"}
    persona = personas[persona_key]
    limit = 60000  # 60K limit for simulation
    chunks = [html[i:i+3000] for i in range(0, len(html), 3000)] if len(html) > limit else [html[:limit]]
    if len(html) > limit:
        st.warning(f"HTML content chunked for simulation ({len(chunks)} chunks).")  # Warning for truncation
    if abbreviated:
        chunks = chunks[:10]  # Cap at 10 chunks for quick sim
    if len(chunks) > 10:
        st.warning(f"Large site: Using first 10 chunks for simulation to avoid delays.")  # Warning for cap
    results = []
    progress = st.progress(0, text="Simulating experience...")  # Progress bar
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        for i, chunk in enumerate(chunks):
            if st.session_state.get('sim_cancel', False): break  # Cancel if switch
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": persona['prompt'] + "\n\nOutput in structured Markdown as specified."},
                    {"role": "user", "content": chunk}
                ],
                temperature=0.5,
            )
            result = response.choices[0].message.content
            results.append(result)
            progress.progress((i + 1) / len(chunks))  # Progress update
            time.sleep(1)  # Rate limit sleep
        merged_result = "\n\n".join(results)
        # Summarize merged result to reduce verbosity
        summary_prompt = "Summarize this simulation output: Focus on top 5 issues and fixes."
        summary_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": summary_prompt + "\n\n" + merged_result}],
            temperature=0.5,
            max_tokens=500
        )
        merged_result = summary_response.choices[0].message.content
        return merged_result
    except Exception as e:
        logging.error(f"[Simulation Error] {str(e)}")
        return {"error": "Failed to simulate experience. Please try again or contact support."}