# Dockerfile (Updated Python version, added curl for healthcheck, no-cache pip)
FROM python:3.12-slim

# Install OS dependencies for Playwright and curl for healthcheck
RUN apt-get update && apt-get install -y \
    curl libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libxcomposite1 libxrandr2 libxdamage1 libpango-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Install Playwright Chromium dependencies (Debian 13–compatible)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-unifont \
        fonts-dejavu-core \
        fonts-freefont-ttf \
        libnss3 libnspr4 libxss1 libasound2 libatk1.0-0 \
        libatk-bridge2.0-0 libgtk-3-0 libdrm2 libxdamage1 \
        libxrandr2 libgbm1 libxcomposite1 libxkbcommon0 libpango-1.0-0 \
        libpangoft2-1.0-0 libpangocairo-1.0-0 libcups2 && \
    rm -rf /var/lib/apt/lists/* && \
    playwright install chromium


# Copy app code
COPY app.py .
COPY utils.py .
COPY ui.py .
COPY simulator/ simulator/
COPY assets/ assets/

# Environment variables
ENV ENV=prod
ENV PYTHONUNBUFFERED=1

# Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=3s CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]