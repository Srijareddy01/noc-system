#!/bin/bash
# Start the Flask app with Gunicorn inside Docker

# Set working directory (optional)
cd /app

# Use the port provided by Render
PORT=${PORT:-10000}
exec gunicorn app:app --bind 0.0.0.0:$PORT