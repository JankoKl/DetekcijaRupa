# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13.5
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System dependencies required by OpenCV, PyTorch/Ultralytics and video processing
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Runtime writable directories
RUN mkdir -p /app/data /app/.output \
    && chmod -R 777 /app/data /app/.output

# Create non-root user
RUN adduser --disabled-password --gecos "" --uid 10001 appuser

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Run as non-root
USER appuser

CMD ["/app/entrypoint.sh"]