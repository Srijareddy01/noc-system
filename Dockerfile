FROM python:3.11-slim

# Install system dependencies for WeasyPrint + eventlet
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libcairo2 \
    pango1.0-tools \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose Render port
ENV PORT=10000

# Run with gunicorn + eventlet (for SocketIO)
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:10000", "app:app"]
