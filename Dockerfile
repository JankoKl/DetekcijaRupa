# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13.5
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (OpenCV, Ultralytics needs these)
RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create data/output folders before switching user
RUN mkdir -p /app/data /app/.output && chmod -R 777 /app/data /app/.output

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything else
COPY . .

# Optional: copy default .env if needed
# COPY .env .   ← only needed if you want to bake it into the image

# Create a non-root user *after* installing packages (best practice)
RUN adduser --disabled-password --gecos "" --uid 10001 appuser

# Switch to non-root user
USER appuser

# Default command to run the app
CMD ["python", "main.py"]
