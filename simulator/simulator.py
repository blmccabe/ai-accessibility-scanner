# simulator/simulator.py

def load_personas():
    return {
        "blind_screen_reader": {
            "label": "Blind User (Screen Reader)",
            "prompt": "Simulate how a blind user using a screen reader would experience this website's HTML. Identify any accessibility issues and explain how they affect navigation and understanding."
        },
        "keyboard_only_user": {
            "label": "Keyboard-Only User",
            "prompt": "Simulate how a keyboard-only user would experience this website. Identify any issues with tab order, focus indicators, and keyboard traps."
        },
        "colorblind_user": {
            "label": "User with Color Blindness",
            "prompt": "Simulate how a user with color blindness would experience this website. Identify potential color contrast or information issues and suggest improvements."
        },
        "low_vision_user": {
            "label": "Low Vision User (Zoomed or Magnified View)",
            "prompt": "Simulate how a low vision user using zoom or magnification would experience this page. Focus on readability, scaling issues, and spacing."
        }
    }

def simulate_experience(html, persona_key):
    from openai import OpenAI
    personas = load_personas()
    if persona_key not in personas:
        return {"error": f"Unknown persona: {persona_key}"}

    persona = personas[persona_key]

    # Truncate HTML for token safety
    if len(html) > 15000:
        print("⚠️ HTML content truncated to 15,000 characters to avoid hitting GPT-4 limits.")
    truncated_html = html[:15000]

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": f"""
{persona['prompt']}

You are an accessibility expert simulating this user’s experience. 
Please return your output in **this exact markdown format**:

### 🔍 Experience Summary for {persona['label']}

**Main Barriers Encountered:**
- ...

**Navigation Issues:**
- ...

**Content Gaps:**
- ...

**Recommendations:**
- ...
"""
                },
                {
                    "role": "user",
                    "content": truncated_html
                }
            ],
            temperature=0.5,
        )
        return response.choices[0].message.content
    except Exception as e:
        return {"error": str(e)}



