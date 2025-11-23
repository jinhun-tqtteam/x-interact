#!/bin/bash

# Stop script on error
set -e

echo "🚀 Starting deployment..."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull

# Rebuild and restart containers
echo "🔄 Rebuilding and restarting containers..."
docker compose up -d --build

# Show logs
echo "✅ Deployment complete! Tailing logs (Ctrl+C to exit)..."
docker compose logs -f
