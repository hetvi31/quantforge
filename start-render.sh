#!/bin/bash

echo "[Startup] Starting local Redis server..."
redis-server --protected-mode no --daemonize yes

# Wait for Redis to start up
until redis-cli ping | grep -q PONG; do
  echo "[Startup] Waiting for Redis..."
  sleep 1
done
echo "[Startup] Redis is ready."

echo "[Startup] Starting C++ Matching Engine..."
quantforge_matching_engine &

echo "[Startup] Starting C++ Feed Handler..."
quantforge_feed_handler &

echo "[Startup] Starting Market Simulator..."
python scripts/market_simulator.py localhost &

echo "[Startup] Starting AI Research Service..."
export GATEWAY_URL=http://localhost:8000
cd /app/ai_research && uvicorn app:app --host 0.0.0.0 --port 8001 &

echo "[Startup] Starting FastAPI Gateway..."
cd /app/gateway && exec uvicorn app.main:app --host 0.0.0.0 --port 8000
