# Building from GitHub Repository

This guide covers deploying Dovos by building directly from your GitHub repository instead of using local files.

## Files

- **`Dockerfile.git`** - Dockerfile that clones from GitHub
- **`docker-compose.git.yml`** - Docker Compose config using Dockerfile.git
- **`Dockerfile`** - Standard Dockerfile using local files (for development)
- **`docker-compose.yml`** - Standard Docker Compose (for development)

## When to Use Each Approach

### Use `Dockerfile` (Local Copy) 👨‍💻
**Best for:**
- Local development
- Testing uncommitted changes
- Fast iteration
- Offline work

### Use `Dockerfile.git` (GitHub Clone) 🚀
**Best for:**
- Production deployments
- CI/CD pipelines
- Deploying to servers without code
- Ensuring exact version from repo
- Team deployments

## Quick Start - Build from GitHub

### 1. Basic Usage (Main Branch)

```bash
# Build and start with main branch
docker compose -f docker-compose.git.yml up -d

# View logs
docker compose -f docker-compose.git.yml logs -f
```

### 2. Build from Specific Branch

```bash
# Set branch in .env file
echo "GIT_BRANCH=dockerize-application" >> .env

# Build and start
docker compose -f docker-compose.git.yml up -d --build
```

### 3. Build from Different Repository

```bash
# Set custom repo
export GITHUB_REPO=https://github.com/yourfork/dovos.git
export GIT_BRANCH=feature-branch

# Build and start
docker compose -f docker-compose.git.yml up -d --build
```

## Advanced Usage

### Build Only (No Start)

```bash
# Build image from specific branch
docker compose -f docker-compose.git.yml build \
  --build-arg BRANCH=dockerize-application

# Build with different repo
docker compose -f docker-compose.git.yml build \
  --build-arg GITHUB_REPO=https://github.com/youruser/dovos.git \
  --build-arg BRANCH=main
```

### Using Docker Build Directly

```bash
# Build image with custom tag
docker build -f Dockerfile.git \
  --build-arg BRANCH=main \
  -t dovos-rag:latest .

# Build from specific commit
docker build -f Dockerfile.git \
  --build-arg BRANCH=abc1234567 \
  -t dovos-rag:abc1234 .

# Build from PR branch
docker build -f Dockerfile.git \
  --build-arg BRANCH=pull/123/head \
  -t dovos-rag:pr123 .
```

## Environment Variables

Set these in your `.env` file:

```env
# Git repository configuration
GITHUB_REPO=https://github.com/markrichman/dovos.git
GIT_BRANCH=main

# PostgreSQL configuration (same as before)
POSTGRES_USER=dovos
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=dovos

# Application configuration
OPENWEBUI_URL=http://your-openwebui:3000
OPENWEBUI_API_KEY=your-api-key
SECRET_KEY=your-secret-key
```

## CI/CD Pipeline Example

### GitHub Actions

```yaml
name: Deploy to Production

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository info only
        uses: actions/checkout@v4
        with:
          sparse-checkout: |
            docker-compose.git.yml
            Dockerfile.git
      
      - name: Set up Docker
        uses: docker/setup-buildx-action@v3
      
      - name: Build and push
        run: |
          docker build -f Dockerfile.git \
            --build-arg BRANCH=${{ github.ref_name }} \
            -t dovos-rag:${{ github.sha }} \
            .
      
      - name: Deploy to server
        run: |
          # Your deployment commands here
          ssh user@server "docker pull dovos-rag:${{ github.sha }}"
          ssh user@server "cd /app && docker compose -f docker-compose.git.yml up -d"
```

## Production Deployment Workflow

### 1. On Your Server (First Time)

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Create app directory
mkdir -p /opt/dovos
cd /opt/dovos

# Download docker-compose.git.yml only (no need for full repo)
curl -O https://raw.githubusercontent.com/markrichman/dovos/main/docker-compose.git.yml

# Create .env file
cat > .env << 'EOF'
GIT_BRANCH=main
POSTGRES_USER=dovos
POSTGRES_PASSWORD=super-secure-password
POSTGRES_DB=dovos
OPENWEBUI_URL=http://your-openwebui:3000
OPENWEBUI_API_KEY=your-api-key
SECRET_KEY=your-secret-key
EOF

# Start services (will build from GitHub)
docker compose -f docker-compose.git.yml up -d
```

### 2. Update to Latest Code

```bash
# Pull latest and rebuild
docker compose -f docker-compose.git.yml pull
docker compose -f docker-compose.git.yml up -d --build

# Or force rebuild from GitHub
docker compose -f docker-compose.git.yml build --no-cache
docker compose -f docker-compose.git.yml up -d
```

### 3. Deploy Specific Version

```bash
# Update .env with specific branch/tag
echo "GIT_BRANCH=v1.2.3" > .env

# Rebuild and deploy
docker compose -f docker-compose.git.yml up -d --build
```

## Comparison

| Feature | Dockerfile (Local) | Dockerfile.git (GitHub) |
|---------|-------------------|------------------------|
| Build Speed | ⚡ Fast | 🐌 Slower (git clone) |
| Network Required | ❌ No | ✅ Yes |
| Uncommitted Changes | ✅ Yes | ❌ No |
| Reproducibility | ⚠️ Depends on local state | ✅ Exact version |
| CI/CD Friendly | ⚠️ Need code checkout | ✅ Just needs Dockerfile |
| Production Ready | ✅ Yes | ✅ Yes |
| Secrets Handling | ⚠️ Uses .dockerignore | ✅ Never sees local files |

## Private Repositories

If your repository is private, you'll need to provide credentials:

### Option 1: SSH Key

```dockerfile
# In Dockerfile.git, add:
RUN mkdir -p ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
COPY id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa

# Then use SSH URL
ARG GITHUB_REPO=git@github.com:markrichman/dovos.git
```

### Option 2: Personal Access Token

```bash
# Build with token in URL
docker build -f Dockerfile.git \
  --build-arg GITHUB_REPO=https://username:ghp_token@github.com/user/repo.git \
  -t dovos-rag .
```

### Option 3: Build Secrets (Recommended)

```dockerfile
# In Dockerfile.git
RUN --mount=type=secret,id=github_token \
    git clone --branch ${BRANCH} \
    https://$(cat /run/secrets/github_token)@github.com/user/repo.git .
```

```bash
# Build with secret
echo "ghp_your_token" | docker build -f Dockerfile.git \
  --secret id=github_token,src=- \
  -t dovos-rag .
```

## Troubleshooting

### Build fails with "repository not found"

- Check repository URL is correct
- Verify branch exists
- For private repos, ensure credentials are provided

### Build is very slow

- Git clone can be slower than COPY
- Use `--depth 1` (already in Dockerfile.git) to speed up
- Consider caching the git layer

### Want to see what code was built

```bash
# Check commit hash in running container
docker compose -f docker-compose.git.yml exec dovos-rag git log -1

# Or if git isn't in final image, check during build
docker build -f Dockerfile.git --progress=plain . 2>&1 | grep "Cloning into"
```

## Best Practices

1. **Use tags for production**: Deploy from git tags (e.g., `v1.0.0`) not `main`
2. **Pin dependencies**: Use specific versions in `requirements.txt`
3. **Multi-stage is cleaner**: Dockerfile.git uses multi-stage to avoid including git in final image
4. **Don't include secrets**: GitHub repo should never contain secrets; always use environment variables
5. **Test before deploying**: Always test the git-based build before using in production

## Rolling Back

```bash
# Deploy previous version
echo "GIT_BRANCH=v1.0.0" > .env
docker compose -f docker-compose.git.yml up -d --build

# Or use commit hash
echo "GIT_BRANCH=abc123def" > .env
docker compose -f docker-compose.git.yml up -d --build
```

## Switching Between Methods

### From Local to GitHub

```bash
# Stop current stack
docker compose down

# Start with GitHub version
docker compose -f docker-compose.git.yml up -d
```

### From GitHub to Local

```bash
# Stop GitHub-based stack
docker compose -f docker-compose.git.yml down

# Start with local version
docker compose up -d
```

Both use the same volumes, so your data persists!

## Resources

- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Build Arguments](https://docs.docker.com/build/guide/build-args/)
- [Docker Compose Build](https://docs.docker.com/compose/compose-file/build/)
