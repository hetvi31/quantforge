FROM python:3.11-slim

WORKDIR /app

# curl is used by the compose healthcheck; build-essential for any wheels.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app

# Drop privileges.
RUN useradd -m quant && chown -R quant /app
USER quant

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
