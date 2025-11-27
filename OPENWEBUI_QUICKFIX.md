# Quick Fix: OpenWebUI 403 "API key not enabled" Error

## The Problem
```
Error: Use of API key is not enabled in the environment
```

## The Solution (Quick Steps)

### 1. Find your OpenWebUI configuration

**For Docker/Docker Compose:**
```bash
# Find the compose file
ls docker-compose.yml

# Or find the running container
docker ps | grep openwebui
```

### 2. Add the environment variable

**For Docker Compose:** Edit `docker-compose.yml`
```yaml
services:
  open-webui:
    environment:
      - ENABLE_API_KEY=true  # <-- Add this line
```

**For Docker run:** Add `-e ENABLE_API_KEY=true` to your docker run command

### 3. Restart OpenWebUI
```bash
# Docker Compose
docker compose restart open-webui

# Docker
docker restart <container-name>
```

### 4. Test the fix
```bash
cd /Users/markrichman/projects/dovos
python scripts/diagnose_openwebui_export.py
```

## That's It!

The export should now work. The Settings UI connection test passes because it only tests reading (GET), but export requires creating (POST) which needs the `ENABLE_API_KEY=true` setting.

---

**Need more details?** See `docs/OPENWEBUI_API_FIX.md` for comprehensive documentation.
