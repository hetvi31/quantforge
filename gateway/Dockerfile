FROM python:3.11-slim

WORKDIR /app

# Install network tools for debugging and pip certs
RUN apt-get update && apt-get install -y netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy python app source
COPY . .

# Ensure app is importable
ENV PYTHONPATH=/app

EXPOSE 8000

# Start app using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
