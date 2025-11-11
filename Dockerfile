# ========================
# Dockerfile — NexAssistAI Production
# ========================
FROM python:3.12-slim

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install OS + Playwright deps + curl
RUN apt-get update && apt-get install -y \
    curl fonts-unifont fonts-dejavu-core fonts-freefont-ttf \
    libnss3 libnspr4 libxss1 libasound2 libatk1.0-0 libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libxdamage1 libxrandr2 libgbm1 libxcomposite1 \
    libxkbcommon0 libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcups2 \
 && rm -rf /var/lib/apt/lists/* \
 && python -m playwright install chromium

# Workdir
WORKDIR /app

# Copy dependency list and install
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY app.py .
COPY utils.py .
COPY ui.py .
COPY simulator/ simulator/
COPY assets/ assets/
COPY .env .env  # optional, safe locally

# Environment variables
ENV ENV=prod
ENV PYTHONUNBUFFERED=1
ENV PORT=8501

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
