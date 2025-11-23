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

This script will:
1.  Pull the latest code.
2.  Rebuild the Docker image.
3.  Restart the container.

## Useful Commands

- **View Logs**: `docker compose logs -f`
- **Stop App**: `docker compose down`
- **Restart App**: `docker compose restart`
