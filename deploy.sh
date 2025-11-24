#!/bin/bash

# Stop script on error
set -e

echo "🚀 Starting deployment for x-interact..."
echo "================================================"

# ============================================
# PRE-DEPLOYMENT CHECKS
# ============================================
echo ""
echo "🔍 Running pre-deployment checks..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo "   Please create .env from .env.example"
    exit 1
fi
echo "   ✅ .env file found"

# Check if accounts.json exists
if [ ! -f accounts.json ]; then
    echo "❌ ERROR: accounts.json not found!"
    echo "   Please create accounts.json from accounts.json.example"
    exit 1
fi
echo "   ✅ accounts.json found"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker is not installed or not in PATH"
    exit 1
fi
echo "   ✅ Docker is available"

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo "❌ ERROR: Docker Compose is not available"
    exit 1
fi
echo "   ✅ Docker Compose is available"

# Check Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ ERROR: Docker daemon is not running"
    exit 1
fi
echo "   ✅ Docker daemon is running"

# ============================================
# BACKUP STATE FILES
# ============================================
echo ""
echo "💾 Creating backup of state files..."

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Backup tracker_state.json if it exists
if [ -f tracker_state.json ]; then
    cp tracker_state.json "$BACKUP_DIR/tracker_state_$TIMESTAMP.json"
    echo "   ✅ Backed up tracker_state.json"
else
    echo "   ℹ️  No tracker_state.json to backup (first run?)"
fi

# Keep only last 5 backups
echo "   🧹 Cleaning old backups (keeping last 5)..."
ls -t "$BACKUP_DIR"/tracker_state_*.json 2>/dev/null | tail -n +6 | xargs -r rm --
echo "   ✅ Backup complete"

# ============================================
# PULL LATEST CODE
# ============================================
echo ""
echo "📥 Pulling latest code from repository..."
if git pull; then
    echo "   ✅ Code updated successfully"
else
    echo "⚠️  WARNING: Git pull failed or no changes"
fi

# Show current commit
CURRENT_COMMIT=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --pretty=%s)
echo "   Current commit: $CURRENT_COMMIT - $COMMIT_MSG"

# ============================================
# REBUILD AND RESTART CONTAINERS
# ============================================
echo ""
echo "🔄 Rebuilding and restarting containers..."
echo "   This may take a few minutes..."

# Build with no cache for clean build (comment out --no-cache for faster builds)
docker compose build
echo "   ✅ Build complete"

# Stop existing containers gracefully
echo "   Stopping existing containers..."
docker compose down
echo "   ✅ Containers stopped"

# Start containers in detached mode
echo "   Starting new containers..."
docker compose up -d
echo "   ✅ Containers started"

# ============================================
# POST-DEPLOYMENT VERIFICATION
# ============================================
echo ""
echo "✅ Verifying deployment..."

# Wait a bit for container to initialize
echo "   ⏳ Waiting 5 seconds for container to initialize..."
sleep 5

# Check container status
CONTAINER_STATUS=$(docker compose ps --format json | grep -oP '"State":"\K[^"]+' || echo "unknown")
echo "   Container status: $CONTAINER_STATUS"

if [ "$CONTAINER_STATUS" != "running" ]; then
    echo "   ⚠️  WARNING: Container is not running!"
    echo "   Check logs below for errors:"
    docker compose logs --tail=50
    exit 1
fi

# Check container health (if health check is available)
echo "   Checking container health..."
sleep 10  # Wait for first health check

HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' x-interact-tracker 2>/dev/null || echo "none")
if [ "$HEALTH_STATUS" = "healthy" ]; then
    echo "   ✅ Container is healthy"
elif [ "$HEALTH_STATUS" = "none" ]; then
    echo "   ℹ️  Health check not available or not yet completed"
else
    echo "   ⚠️  Health status: $HEALTH_STATUS"
fi

# Show container info
echo ""
echo "📊 Container information:"
docker compose ps

# ============================================
# SHOW RECENT LOGS
# ============================================
echo ""
echo "📝 Recent logs (last 30 lines):"
echo "================================================"
docker compose logs --tail=30

echo ""
echo "================================================"
echo "✅ Deployment complete!"
echo "================================================"
echo ""
echo "📌 Useful commands:"
echo "   View live logs:    docker compose logs -f"
echo "   Stop application:  docker compose down"
echo "   Restart:           docker compose restart"
echo "   Check status:      docker compose ps"
echo "   View health:       docker inspect x-interact-tracker"
echo ""
echo "💡 To view live logs, press Ctrl+C and run:"
echo "   docker compose logs -f"
echo ""
