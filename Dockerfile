FROM python:3.11-slim

# Install OS dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates curl unzip fonts-liberation libnss3 libxss1 libasound2 \
    libatk-bridge2.0-0 libgtk-3-0 libgbm1 libxshmfence1 libxcomposite1 \
    libxrandr2 libxdamage1 libpango-1.0-0 libx11-xcb1 libx11-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browser binaries
RUN playwright install --with-deps

# Copy app code
COPY . .

# Streamlit port
EXPOSE 8501

# Start the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
