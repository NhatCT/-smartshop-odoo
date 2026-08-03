FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir odoo-mcp

# Copy project files
COPY . .

# Expose FastAPI Port
EXPOSE 8000

# Start script running FastAPI Web Gateway + Telegram Bot Listener
CMD ["python", "app_entrypoint.py"]
