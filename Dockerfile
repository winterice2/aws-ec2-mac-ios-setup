# =============================================================================
# 🐳 BABLOBOT ECOSYSTEM DOCKERFILE
# =============================================================================
# Оптимизированный образ для торгового бота
#
# Features:
# - Python 3.11 slim
# - Async support (aiohttp, websockets)
# - Gemini SDK
# - BingX API integration
#
# =============================================================================

FROM python:3.11-slim

# Metadata
LABEL maintainer="AI Architect for Bablobot"
LABEL version="2.0.0"
LABEL description="Autonomous Trading Ecosystem with AI Brain"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/user_data/logs/ecosystem_feedback/{errors,unsolved,needs,decisions} \
    /app/user_data/logs/daily_analysis \
    /app/user_data/logs/archive \
    /app/user_data/data/{spot_flow,btc_watcher,volume,lag_data} \
    /app/config

# Default command
CMD ["python", "-m", "scripts.bablobot.position_manager"]
