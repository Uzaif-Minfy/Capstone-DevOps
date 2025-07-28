FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY s3_discovery.py .

# Create targets directory
RUN mkdir -p /opt/monitoring/targets

# Expose metrics port
EXPOSE 8082

# Run discovery service
CMD ["python", "s3_discovery.py"]
