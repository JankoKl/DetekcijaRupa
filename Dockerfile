# Use Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (if the app serves HTTP, change as needed)
EXPOSE 5000

# Define default command (update with your entrypoint)
CMD ["python", "main.py"]
