FROM python:3.11-slim

WORKDIR /app

# Install dependency files
COPY requirements.txt .

# Install dependencies (re-use gateway dependencies format)
RUN pip install --no-cache-dir fastapi uvicorn requests loguru google-generativeai openai

# Copy source code
COPY . .

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
