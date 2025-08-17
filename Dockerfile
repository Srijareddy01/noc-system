# Use Python base image
FROM python:3.10-slim

# Install system dependencies for WeasyPrint + eventlet
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 10000

# Run with gunicorn + eventlet worker
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:10000", "app:app"]
