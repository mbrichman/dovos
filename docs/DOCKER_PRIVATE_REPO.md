# Building from Private GitHub Repository

This guide covers building Docker images from a **private** GitHub repository using SSH keys.

## Files

- **`Dockerfile.git.ssh`** - Dockerfile that clones from private GitHub using SSH
- **`docker-compose.git.ssh.yml`** - Docker Compose for private repo builds
- **`Dockerfile.git`** - Standard Dockerfile for public repos (HTTPS)

## Prerequisites

### 1. SSH Key Setup

Make sure you have an SSH key set up with GitHub:

```bash
# Check if you have SSH keys
ls -la ~/.ssh

# You should see files like:
# id_ed25519 or id_rsa (private key)
# id_ed25519.pub or id_rsa.pub (public key)

# If you don't have keys, create one:
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add key to ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519  # or id_rsa

# Copy public key to clipboard
cat ~/.ssh/id_ed25519.pub | pbcopy  # macOS
# Then add it to GitHub: Settings → SSH and GPG keys → New SSH key
```

### 2. Test GitHub SSH Connection

```bash
# Verify you can connect to GitHub via SSH
ssh -T git@github.com

# Should see: "Hi username! You've successfully authenticated..."
```

### 3. Enable Docker BuildKit

```bash
# BuildKit is required for SSH secrets
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Or add to ~/.zshrc or ~/.bashrc:
echo 'export DOCKER_BUILDKIT=1' >> ~/.zshrc
echo 'export COMPOSE_DOCKER_CLI_BUILD=1' >> ~/.zshrc
```

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```bash
# 1. Set repository in .env
cat >> .env << 'EOF'
GITHUB_REPO=git@github.com:markrichman/dovos.git
GIT_BRANCH=main
EOF

# 2. Build with SSH key
DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 \
  docker compose -f docker-compose.git.ssh.yml build

# 3. Start services
docker compose -f docker-compose.git.ssh.yml up -d
```

### Option 2: Using Docker Build Directly

```bash
# Build using default SSH key (from ssh-agent)
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default \
  --build-arg BRANCH=main \
  -t dovos-rag .

# Or specify a specific SSH key
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default=$HOME/.ssh/id_ed25519 \
  --build-arg GITHUB_REPO=git@github.com:markrichman/dovos.git \
  --build-arg BRANCH=main \
  -t dovos-rag .
```

## How It Works

### Security Features

1. **SSH Key Never Copied to Image**
   - Uses `--mount=type=ssh` which temporarily mounts SSH socket
   - SSH key is only available during git clone
   - Final image contains NO credentials

2. **Multi-Stage Build**
   - Stage 1: Clones code using SSH (includes git)
   - Stage 2: Copies only code, not git or SSH files
   - Final image is clean and secure

3. **SSH Agent Forwarding**
   - Uses your local ssh-agent
   - No need to copy private keys into build context

### The Dockerfile.git.ssh Process

```dockerfile
# Stage 1 (git stage):
# 1. Install openssh-client
# 2. Add GitHub to known_hosts
# 3. Clone using SSH with mounted key: --mount=type=ssh
# 4. SSH key available only during RUN, then unmounted

# Stage 2 (final image):
# 1. Copy code from stage 1
# 2. SSH key is NOT in this stage
# 3. Secure, clean final image
```

## Environment Variables

Update your `.env` file:

```env
# Use SSH URL for private repo
GITHUB_REPO=git@github.com:markrichman/dovos.git
GIT_BRANCH=main

# PostgreSQL (same as before)
POSTGRES_USER=dovos
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=dovos

# Application
OPENWEBUI_URL=http://your-openwebui:3000
OPENWEBUI_API_KEY=your-api-key
SECRET_KEY=your-secret-key
```

## Advanced Usage

### Build from Specific Branch

```bash
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default \
  --build-arg BRANCH=feature-branch \
  -t dovos-rag:feature .
```

### Build from Specific Commit

```bash
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default \
  --build-arg BRANCH=abc1234567 \
  -t dovos-rag:abc1234 .
```

### Using Different SSH Key

```bash
# Use a specific key file
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default=$HOME/.ssh/github_deploy_key \
  -t dovos-rag .

# Or use a different ssh-agent socket
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default=unix:///path/to/ssh-agent.sock \
  -t dovos-rag .
```

## CI/CD with Private Repos

### GitHub Actions

```yaml
name: Build and Deploy

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Set up SSH
        uses: webfactory/ssh-agent@v0.8.0
        with:
          ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Build image
        run: |
          DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
            --ssh default=$SSH_AUTH_SOCK \
            --build-arg BRANCH=${{ github.ref_name }} \
            -t dovos-rag:${{ github.sha }} .
      
      - name: Deploy
        run: |
          # Your deployment steps here
```

**Setup:**
1. Go to GitHub repo → Settings → Secrets → Actions
2. Add new secret `SSH_PRIVATE_KEY`
3. Paste your private key content

### Self-Hosted Runner

If using a self-hosted runner with ssh-agent already running:

```yaml
- name: Build with existing SSH agent
  run: |
    DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
      --ssh default \
      -t dovos-rag .
```

## Troubleshooting

### Error: "failed to solve: invalid empty ssh agent socket"

**Solution:** Make sure BuildKit is enabled and ssh-agent is running:
```bash
export DOCKER_BUILDKIT=1
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

### Error: "Permission denied (publickey)"

**Solution:** Check SSH key is added to GitHub:
```bash
# Test connection
ssh -T git@github.com

# If fails, add key to GitHub
cat ~/.ssh/id_ed25519.pub
# Copy and add to: https://github.com/settings/keys
```

### Error: "Host key verification failed"

**Solution:** Add GitHub to known_hosts:
```bash
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

### Want to see which key is being used?

```bash
# Verbose SSH output during build
DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh \
  --ssh default \
  --progress=plain \
  --no-cache \
  -t dovos-rag . 2>&1 | grep -i ssh
```

### Error: "no such host"

**Solution:** Make sure you're using SSH URL format:
```bash
# Correct (SSH)
git@github.com:markrichman/dovos.git

# Wrong (HTTPS) - won't work with SSH keys
https://github.com/markrichman/dovos.git
```

## Comparison: Public vs Private Repo

| Feature | Public Repo (Dockerfile.git) | Private Repo (Dockerfile.git.ssh) |
|---------|------------------------------|-----------------------------------|
| Protocol | HTTPS | SSH |
| Repo URL | `https://github.com/user/repo.git` | `git@github.com:user/repo.git` |
| Authentication | None | SSH key |
| BuildKit Required | No | Yes |
| ssh-agent Required | No | Yes |
| Build Command | `docker build -f Dockerfile.git` | `DOCKER_BUILDKIT=1 docker build -f Dockerfile.git.ssh --ssh default` |
| Security | Public code only | Works with private repos |

## Best Practices

1. **Use Deploy Keys for CI/CD**
   - Create read-only deploy keys for automated builds
   - GitHub repo → Settings → Deploy keys → Add deploy key

2. **Don't Commit Private Keys**
   - Never add private keys to repo
   - Use secrets management (GitHub Secrets, env vars, etc.)

3. **Use ssh-agent**
   - Don't pass private keys directly
   - Let ssh-agent handle key management

4. **Rotate Keys Regularly**
   - Generate new deploy keys periodically
   - Remove old/unused keys from GitHub

5. **Minimal Permissions**
   - Deploy keys should be read-only
   - Use separate keys for different purposes

## Production Deployment

### On Remote Server

```bash
# 1. Add your SSH key to the server
ssh-copy-id user@server

# 2. On server, set up SSH key for GitHub
ssh user@server
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub
# Add this key to GitHub as deploy key

# 3. Clone deployment files
git clone git@github.com:markrichman/dovos.git /opt/dovos

# 4. Build and deploy
cd /opt/dovos
DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 \
  docker compose -f docker-compose.git.ssh.yml up -d --build
```

### Automated Updates

```bash
# Create update script
cat > /opt/dovos/update.sh << 'EOF'
#!/bin/bash
cd /opt/dovos
DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 \
  docker compose -f docker-compose.git.ssh.yml pull
DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 \
  docker compose -f docker-compose.git.ssh.yml up -d --build
EOF

chmod +x /opt/dovos/update.sh

# Add to cron for automated updates (optional)
# crontab -e
# 0 2 * * * /opt/dovos/update.sh >> /var/log/dovos-update.log 2>&1
```

## Security Checklist

- [ ] SSH key added to GitHub
- [ ] SSH key is protected (600 permissions)
- [ ] Using deploy keys for automated builds (read-only)
- [ ] Private keys never committed to repo
- [ ] BuildKit enabled for secure mounts
- [ ] ssh-agent running and key loaded
- [ ] Final Docker image doesn't contain SSH keys (verify with `docker history`)

## Resources

- [Docker BuildKit SSH Forwarding](https://docs.docker.com/build/building/secrets/#ssh)
- [GitHub SSH Keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitHub Deploy Keys](https://docs.github.com/en/developers/overview/managing-deploy-keys)
