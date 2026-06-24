# ── Stage 1: dependency build ─────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# System libs required by Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libx11-6 libx11-xcb1 libxcb1 fonts-liberation \
    wget ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install Playwright browser (Chromium only — keeps image lean)
RUN playwright install chromium

# Copy project source
COPY . .

# Output volume — persists DB, PDFs, and logs between runs
VOLUME ["/app/output", "/app/mlruns"]

# Secrets are injected via env at runtime (never baked into the image)
ENV GROQ_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV MLFLOW_TRACKING_URI="file:///app/mlruns"

ENTRYPOINT ["python", "main.py"]
CMD ["--discover"]
