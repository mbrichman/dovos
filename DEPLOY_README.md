# Quick Deployment Guide

This guide shows how to deploy Dovos from the private GitHub repository on any machine.

## Prerequisites

- Docker and Docker Compose installed
- SSH key with GitHub access (personal key or deploy key)

## Option 1: Quick Deploy (Recommended)

Download and run the deployment in one directory:

```bash
# 1. Create deployment directory
mkdir -p ~/dovos-deploy
cd ~/dovos-deploy

# 2. Download deployment files (requires GitHub access)
git clone --depth 1 git@github.com:mbrichman/dovos.git temp
cp temp/build-from-github.sh .
cp temp/Dockerfile.git.ssh .
cp temp/docker-compose.git.ssh.yml .
cp temp/.env.example .env
rm -rf temp

# 3. Edit .env with your settings
nano .env

# 4. Build from GitHub
./build-from-github.sh

# 5. Start services
docker compose -f docker-compose.git.ssh.yml up -d
```

## Option 2: Build with Custom Settings

```bash
# Build from specific branch
BRANCH=develop ./build-from-github.sh

# Build with custom image name
IMAGE_NAME=my-dovos IMAGE_TAG=v1.0 ./build-from-github.sh

# Build from fork
GITHUB_REPO=git@github.com:yourname/dovos.git ./build-from-github.sh
```

## What the Build Script Does

1. **Detects SSH agent** - Works with standard ssh-agent or 1Password
2. **Tests GitHub connection** - Ensures you have repo access
3. **Builds Docker image** - Clones code from GitHub using SSH
4. **Creates image** - Tagged as `dovos-rag:latest` by default

## SSH Key Setup

### For Personal Key

```bash
# Test connection
ssh -T git@github.com

# Should see: "Hi username! You've successfully authenticated..."
```

### For Deploy Key (Servers)

```bash
# Generate deploy key
ssh-keygen -t ed25519 -C "server-deploy-key" -f ~/.ssh/dovos_deploy_key

# Add to GitHub repo: Settings → Deploy keys → Add deploy key
cat ~/.ssh/dovos_deploy_key.pub

# Configure SSH
cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/dovos_deploy_key
    IdentitiesOnly yes
EOF
```

## Troubleshooting

### "No SSH agent found"

**Solution:** Start ssh-agent:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
./build-from-github.sh
```

### "GitHub SSH authentication failed"

**Solution:** Add your SSH key to GitHub:
1. Display public key: `cat ~/.ssh/id_ed25519.pub`
2. Go to https://github.com/settings/keys
3. Click "New SSH key" and paste

### "Permission denied (publickey)"

**Solution:** Check SSH key is loaded:
```bash
ssh-add -l  # List loaded keys
ssh -T git@github.com  # Test connection
```

## After Deployment

```bash
# Check services
docker compose -f docker-compose.git.ssh.yml ps

# View logs
docker compose -f docker-compose.git.ssh.yml logs -f

# Check migrations ran
docker compose -f docker-compose.git.ssh.yml logs dovos-rag | grep -i migration

# Test API
curl http://localhost:5001/api/stats
```

## Environment Variables

Required in `.env`:

```env
# PostgreSQL
POSTGRES_USER=dovos
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=dovos

# Application
OPENWEBUI_URL=http://your-openwebui:3000
OPENWEBUI_API_KEY=your-api-key
SECRET_KEY=your-secret-key
```

## Updates

To update to latest code:

```bash
# Rebuild from latest main
./build-from-github.sh

# Restart services
docker compose -f docker-compose.git.ssh.yml up -d
```

## Files Needed for Deployment

Minimal deployment requires only 4 files:

```
dovos-deploy/
├── build-from-github.sh         # Build script
├── Dockerfile.git.ssh           # Dockerfile for GitHub
├── docker-compose.git.ssh.yml   # Service configuration
└── .env                         # Your settings
```

All other code is cloned from GitHub during build!
