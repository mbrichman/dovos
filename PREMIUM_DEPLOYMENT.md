# Premium Feature Deployment Guide

This guide is for Dovos Pro and Enterprise license holders who want to enable premium importers (ChatGPT and DOCX).

## Prerequisites

- Valid Dovos Pro or Enterprise license key
- Docker and Docker Compose installed
- Access to premium importer files (`chatgpt.py`, `docx.py`, `docx_parser.py`)

## Deployment Options

### Option 1: Copy Files into Running Container (Quick Test)

This method is useful for testing but files will be lost when the container is recreated.

```bash
# 1. Start the container stack
docker compose -f docker-compose.ghcr.yml up -d

# 2. Set your license key in .env
echo "DOVOS_LICENSE_KEY=DOVOS-PRO-your-key-here" >> .env

# 3. Copy premium importers into the running container
docker cp chatgpt.py dovos-rag-api:/app/db/importers/
docker cp docx.py dovos-rag-api:/app/db/importers/
docker cp docx_parser.py dovos-rag-api:/app/utils/

# 4. Restart the container to reload importers
docker compose -f docker-compose.ghcr.yml restart dovos-rag

# 5. Verify premium features are enabled
docker compose -f docker-compose.ghcr.yml logs dovos-rag | grep -i "chatgpt\|docx"
```

### Option 2: Build Custom Image (Persistent)

This method creates a custom Docker image with premium features built in.

```bash
# 1. Clone the repository
git clone https://github.com/mbrichman/dovos.git
cd dovos

# 2. Copy premium importers into the source tree
cp /path/to/premium/chatgpt.py db/importers/
cp /path/to/premium/docx.py db/importers/
cp /path/to/premium/docx_parser.py utils/

# 3. Create .env with your license key
cat > .env << EOF
POSTGRES_USER=dovos
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=dovos
SECRET_KEY=your-secret-key
DOVOS_LICENSE_KEY=DOVOS-PRO-your-key-here
EOF

# 4. Build and start the stack
docker compose build
docker compose up -d

# 5. Run migrations
docker compose exec dovos-rag alembic upgrade head

# 6. Access the application
open http://localhost:5001
```

### Option 3: Custom Dockerfile (Advanced)

Create a custom Dockerfile that extends the public image:

```dockerfile
FROM ghcr.io/mbrichman/dovos:main

# Copy premium importers
COPY chatgpt.py /app/db/importers/
COPY docx.py /app/db/importers/
COPY docx_parser.py /app/utils/

# Set license key (or use environment variable at runtime)
# ENV DOVOS_LICENSE_KEY=DOVOS-PRO-your-key-here
```

Build and run:

```bash
docker build -t dovos-premium .
docker compose -f docker-compose.ghcr.yml up -d
# Edit docker-compose.ghcr.yml to use 'dovos-premium' instead of 'ghcr.io/mbrichman/dovos:main'
```

## Verifying Premium Features

After deployment, verify that premium features are enabled:

1. **Check license status via API:**
   ```bash
   curl http://localhost:5001/api/license/status
   ```

2. **Try importing a ChatGPT file:**
   - Go to http://localhost:5001
   - Click "Upload" 
   - Select a ChatGPT export JSON file
   - You should see successful import (not license error)

3. **Check container logs:**
   ```bash
   docker compose -f docker-compose.ghcr.yml logs dovos-rag
   ```
   Look for messages about discovered importers.

## Troubleshooting

### "ChatGPT requires a Pro license" error

**Problem:** License is not being recognized.

**Solutions:**
1. Verify `DOVOS_LICENSE_KEY` is set in `.env` or environment
2. Restart the container: `docker compose -f docker-compose.ghcr.yml restart dovos-rag`
3. Check license format: Must be `DOVOS-PRO-xxxxx` or `DOVOS-ENT-xxxxx`

### "ChatGPT import not available" error

**Problem:** Importer file is not present or not loaded.

**Solutions:**
1. Verify files are in container:
   ```bash
   docker exec dovos-rag-api ls -la /app/db/importers/
   ```
2. Check for `chatgpt.py` (not `chatgpt_stub.py`)
3. Restart container to reload importers

### Files disappear after container restart

**Problem:** Using Option 1 (copy into running container).

**Solution:** Use Option 2 (build custom image) for persistent deployment.

## License Management

### Updating License Key

To change or update your license key:

```bash
# Update .env file
echo "DOVOS_LICENSE_KEY=DOVOS-PRO-new-key" > .env

# Restart container
docker compose -f docker-compose.ghcr.yml restart dovos-rag
```

### Multiple Environments

For different environments (dev, staging, prod), use separate `.env` files:

```bash
# Development
DOVOS_LICENSE_KEY=DOVOS-PRO-dev-key

# Production  
DOVOS_LICENSE_KEY=DOVOS-ENT-prod-key
```

## Security Notes

- **Never commit** license keys to version control
- **Never publish** Docker images with embedded license keys to public registries
- Use environment variables or secrets management for license keys in production
- Store premium importer files securely (not in public repositories)

## Support

For license or deployment issues:
- Email: [your-support-email]
- Documentation: https://github.com/mbrichman/dovos
- Issues: https://github.com/mbrichman/dovos/issues
