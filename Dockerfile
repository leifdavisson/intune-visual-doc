# ==============================================================================
# Dockerfile for intune-visual-doc (GNU AGPLv3)
# ==============================================================================
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    INTUNEDOC_OUTPUT_DIR=/app/deliverables \
    INTUNEDOC_AUTH_DIR=/app/.auth

# Install system dependencies for Playwright Chromium & fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications first for layer caching
COPY pyproject.toml /app/

# Install python dependencies and playwright browser binaries
RUN pip install --upgrade pip setuptools wheel && \
    pip install . && \
    playwright install --with-deps chromium

# Copy repository source files
COPY . /app/

# Reinstall package in editable mode
RUN pip install -e .

# Create non-root runtime user and secure working directories
RUN groupadd -g 1000 intunedoc && \
    useradd -u 1000 -g intunedoc -m -s /bin/bash intunedoc && \
    mkdir -p /app/deliverables /app/.auth /ms-playwright && \
    chown -R intunedoc:intunedoc /app /ms-playwright && \
    chmod 0700 /app/.auth

USER intunedoc

ENTRYPOINT ["intunedoc"]
CMD ["--help"]
