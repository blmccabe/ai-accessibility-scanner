# NexAssist AI – Accessibility Scanner 🚀

NexAssist AI is a privacy-conscious, AI-powered web accessibility scanner built to help teams identify and resolve WCAG issues quickly. Designed for developers, agencies, and enterprises focused on compliance, usability, and scale.

---

## 🔍 Features

- **AI-powered WCAG analysis** of any public website
- **Clean UI** with onboarding and onboarding steps
- **One-click scan** via work email + domain
- **Tiered access** (Free, Pro, Agency, Enterprise)
- **PDF, CSV, Excel export** of reports (Pro+)
- **Accessibility simulation** via personas (e.g., color blindness, dyslexia)
- **Stripe integration** for subscription management
- **Streamlit deployment**, powered by OpenAI & Grok

---

## 🧱 Project Structure

```bash
ai-accessibility-scanner/
│
├── app.py                 # Main Streamlit app
├── ui.py                  # UI components
├── utils.py               # Core logic and helpers
├── .env.example           # Template for environment variables (safe to share)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Optional Docker setup
├── render.yaml            # Deployment config for Render
│
├── simulator/             # Accessibility simulation logic
│   ├── simulator.py
│   └── personas.json
│
├── assets/                # Logo, icons, etc.
├── .gitignore             # Files to exclude from Git
├── LICENSE
└── README.md


⚙️ Local Setup
Follow these steps to run the app locally.

1. Clone the repo
bash
Copy
Edit
git clone https://github.com/YOUR_USERNAME/ai-accessibility-scanner.git
cd ai-accessibility-scanner
2. Create a virtual environment and activate it
bash
Copy
Edit
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
3. Install dependencies
bash
Copy
Edit
pip install -r requirements.txt
4. Create your .env file
bash
Copy
Edit
cp .env.example .env
Edit .env and add your API keys:

env
Copy
Edit
OPENAI_API_KEY=sk-...
STRIPE_PUB_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_AGENCY_PRICE_ID=price_...
LOCAL_DOMAIN=http://localhost:8501
PROD_DOMAIN=https://nexassistai.com
5. Run the app
bash
Copy
Edit
streamlit run app.py
🚀 Deployment
NexAssist AI is deployed via Render.

You can deploy your own instance by:

Linking your GitHub repo to Render

Setting your environment variables from .env

Using render.yaml for deployment settings

If you're not using Render, you can also deploy via Docker, Streamlit Community Cloud, or your own server.

💰 Pricing Tiers
Tier	Features
Free	1 scan/day
Pro	Unlimited scans, PDF/CSV exports, code fixes
Agency	Multi-domain support, white-labeled reports
Enterprise	Custom scan workflows, API access

Prices and tiers configured via Stripe

📜 License
This project is licensed under the MIT License.
See LICENSE for full details.

🙋‍♂️ Contributing
This is an early-stage proprietary SaaS project.

Contributions are limited for now — please open an issue or email us to report bugs or request features.

Coming soon:

CONTRIBUTING.md

Branching conventions

Testing instructions

🧠 Inspiration
Built by accessibility advocates to simplify WCAG compliance and empower teams to build more inclusive web experiences.

🔒 Security & IP
This repo is private by default

.env is excluded via .gitignore

Sensitive config is never exposed

Any AI logic, personas, and code-fix mechanisms are proprietary

👥 Team
Made by NexAssist AI LLC
Contact: hello@nexassistai.com

yaml
Copy
Edit

---

### ✅ Next Steps

1. **Open the README**:
```bash
cd ~/ai-accessibility-scanner
code README.md
Paste the content above, replacing anything currently there.

Save it, then run:

bash
Copy
Edit
git add README.md
git commit -m "Add full production README"
git push origin main