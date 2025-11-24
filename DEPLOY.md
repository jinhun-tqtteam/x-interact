# Deployment Instructions

## Prerequisites
- An Ubuntu Server
- `git` installed
- `docker` and `docker-compose` installed

## One-time Setup on Server

1.  **Install Docker & Git** (if not already installed):
    ```bash
    # Update and install essentials
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y git curl

    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh

    # Add current user to docker group (so you don't need sudo for docker)
    sudo usermod -aG docker $USER
    newgrp docker
    ```

2.  **Clone Your Repository**:
    ```bash
    git clone <YOUR_REPO_URL>
    cd x-interact
    ```

3.  **Setup Configuration**:
    - Create your `.env` file:
      ```bash
      cp .env.example .env
      nano .env
      # Paste your environment variables and save (Ctrl+O, Enter, Ctrl+X)
      ```
    - Create/Edit `accounts.json`:
      ```bash
      nano accounts.json
      # Paste your accounts config
      ```

4.  **Start the Application**:
    ```bash
    sh deploy.sh
    ```

## How to Update
When you have pushed new code to the repository, simply run this command on the server:

```bash
sh deploy.sh
```

This enhanced script will:
1.  **Pre-deployment checks**: Verify `.env`, `accounts.json`, Docker availability
2.  **Backup state files**: Auto-backup `tracker_state.json` (keeps last 5)
3.  **Pull latest code** from repository
4.  **Rebuild Docker image** with latest changes
5.  **Gracefully restart** container
6.  **Post-deployment verification**: Check container health and logs
7.  **Show deployment summary** with useful commands

## Features

### 🏥 Health Checks
The container now includes automated health checks:
- Runs every 30 seconds
- Verifies Python runtime is functional
- Automatic restart if health check fails 3 times
- View health status: `docker inspect x-interact-tracker`

### 📝 Log Rotation
Automatic log management to prevent disk space issues:
- Max log file size: 10MB
- Keeps last 3 log files
- Old logs automatically rotated

### 💾 Automatic Backups
State files are automatically backed up during deployment:
- Stored in `backups/` directory
- Timestamped backups
- Keeps last 5 backups automatically

## Useful Commands

- **View Logs**: `docker compose logs -f`
- **View Last N Lines**: `docker compose logs --tail=50`
- **Stop App**: `docker compose down`
- **Restart App**: `docker compose restart`
- **Check Status**: `docker compose ps`
- **Check Health**: `docker inspect x-interact-tracker | grep -A 5 Health`
- **Enter Container**: `docker exec -it x-interact-tracker /bin/bash`
- **View Resource Usage**: `docker stats x-interact-tracker`
- **Restore Backup**: `cp backups/tracker_state_YYYYMMDD_HHMMSS.json tracker_state.json`
