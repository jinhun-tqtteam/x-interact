# 🚀 X-Interact Deployment Quick Reference

## 🎯 Common Commands

### Deployment
```bash
# Deploy/Update application
sh deploy.sh

# The script automatically:
# ✅ Validates environment
# ✅ Backs up state files
# ✅ Pulls latest code
# ✅ Rebuilds container
# ✅ Verifies health
```

### Monitoring
```bash
# View live logs
docker compose logs -f

# View last 50 lines
docker compose logs --tail=50

# Check container status
docker compose ps

# Check health status
docker inspect x-interact-tracker | grep -A 5 Health

# Monitor resource usage
docker stats x-interact-tracker
```

### Control
```bash
# Stop application
docker compose down

# Start application
docker compose up -d

# Restart application
docker compose restart

# Rebuild without deploying
docker compose build
```

### Troubleshooting
```bash
# Enter container shell
docker exec -it x-interact-tracker /bin/bash

# View container details
docker inspect x-interact-tracker

# Check Docker logs
docker logs x-interact-tracker

# View all containers
docker ps -a
```

### Backups
```bash
# List backups
ls -lh backups/

# Restore from backup
cp backups/tracker_state_YYYYMMDD_HHMMSS.json tracker_state.json
docker compose restart

# Manual backup
cp tracker_state.json backups/tracker_state_manual_$(date +%Y%m%d_%H%M%S).json
```

## 🏥 Health Check Status

| Status | Meaning | Action |
|--------|---------|--------|
| `healthy` | ✅ Everything OK | None |
| `starting` | ⏳ Container initializing | Wait 10-30 seconds |
| `unhealthy` | ⚠️ Health check failing | Check logs |
| `none` | ℹ️ No health check | Normal for old images |

## 📊 Log Files

| Setting | Value | Explanation |
|---------|-------|-------------|
| Max Size | 10MB | Per log file |
| Max Files | 3 | Total files kept |
| Total Space | ~30MB | Maximum log disk usage |

**Location:** Check with `docker inspect --format="{{.LogPath}}" x-interact-tracker`

## 🔧 Configuration Files

| File | Purpose | Backed Up? |
|------|---------|-----------|
| `.env` | Environment variables | ❌ Manual |
| `accounts.json` | Twitter accounts config | ❌ Manual |
| `tracker_state.json` | Tracker state | ✅ Auto (deploy.sh) |
| `Dockerfile` | Container definition | Version controlled |
| `docker-compose.yml` | Service configuration | Version controlled |

## ⚠️ Important Notes

1. **Never commit sensitive files:**
   - `.env` (contains webhook URLs)
   - `accounts.json` (contains Twitter cookies)
   - `tracker_state.json` (runtime state)

2. **Backups are kept for 5 deployments:**
   - Older backups auto-deleted
   - Manual backups not affected
   - Stored in `backups/` directory

3. **Health checks run every 30 seconds:**
   - 3 consecutive failures = unhealthy
   - Container auto-restarts if unhealthy
   - Wait 10s after start before first check

4. **Log rotation is automatic:**
   - No manual cleanup needed
   - Logs rotate at 10MB
   - Max 3 files = ~30MB total

## 🆘 Emergency Procedures

### Container Won't Start
```bash
# Check logs for errors
docker compose logs --tail=100

# Verify configuration files exist
ls -lh .env accounts.json

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Lost State After Deploy
```bash
# Stop container
docker compose down

# Restore latest backup
cp backups/tracker_state_*.json tracker_state.json | tail -1

# Restart
docker compose up -d
```

### Disk Space Full
```bash
# Check Docker disk usage
docker system df

# Clean up old images/containers
docker system prune -a

# Check log file size
du -h $(docker inspect --format="{{.LogPath}}" x-interact-tracker)
```

### Health Check Always Failing
```bash
# Check container logs
docker logs x-interact-tracker

# Verify tracker.py exists in container
docker exec x-interact-tracker ls -lh /app/tracker.py

# Test Python in container
docker exec x-interact-tracker python --version

# Disable health check temporarily (edit docker-compose.yml)
# Remove or comment out the healthcheck section in Dockerfile
```

## 📞 Quick Debug Checklist

- [ ] `.env` file exists and has correct values?
- [ ] `accounts.json` exists and has valid Twitter cookies?
- [ ] Docker daemon is running? (`docker ps`)
- [ ] Container is running? (`docker compose ps`)
- [ ] Health status is healthy? (`docker inspect`)
- [ ] Logs show errors? (`docker compose logs`)
- [ ] Enough disk space? (`df -h`)
- [ ] Network connectivity OK? (ping external sites)

## 🔗 Related Documentation

- Full deployment guide: `DEPLOY.md`
- Improvements summary: `DEPLOYMENT_IMPROVEMENTS.md`
- Project README: `README.md`

---

**Last Updated:** 2025-11-24  
**Version:** Enhanced with health checks, log rotation, and auto-backups
