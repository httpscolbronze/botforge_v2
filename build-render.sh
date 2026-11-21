#!/usr/bin/env bash
set -e

echo "=== Building BotForge_v2 for Render ==="

# 1. Install backend dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt

# 2. Build frontend
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

# 3. Mount/copy frontend build into backend static directory so FastAPI serves it
echo "Copying frontend build to backend static assets..."
rm -rf backend/static
mkdir -p backend/static
cp -r frontend/dist/* backend/static/

echo "=== Build complete ==="
