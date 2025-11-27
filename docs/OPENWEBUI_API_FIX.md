# OpenWebUI API Key Authentication Fix

## Problem
After updating OpenWebUI, you're getting the error:
```
Use of API key is not enabled in the environment
```

This is a 403 Forbidden error that occurs when trying to export conversations to OpenWebUI.

## Root Cause
OpenWebUI has added a security feature that requires API key authentication to be explicitly enabled via an environment variable. By default, it's now disabled.

## Solution

You need to enable API key authentication in your OpenWebUI instance by setting the `ENABLE_API_KEY` environment variable.

### Option 1: Docker/Docker Compose (Recommended)

If you're running OpenWebUI via Docker or Docker Compose, add this environment variable:

```yaml
# docker-compose.yml
services:
  open-webui:
    environment:
      - ENABLE_API_KEY=true
      # ... other environment variables
```

Or if using `docker run`:

```bash
docker run -d \
  -e ENABLE_API_KEY=true \
  -e WEBUI_SECRET_KEY=your-secret-key \
  # ... other options
  ghcr.io/open-webui/open-webui:main
```

### Option 2: Direct Installation

If you installed OpenWebUI directly (not via Docker), set the environment variable before starting:

```bash
export ENABLE_API_KEY=true
# Start OpenWebUI
```

Or add it to your `.env` file in the OpenWebUI directory:

```
ENABLE_API_KEY=true
```

### Option 3: System Environment Variable

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export ENABLE_API_KEY=true
```

## After Making Changes

1. **Restart OpenWebUI** completely:
   ```bash
   # For Docker
   docker compose restart open-webui
   # or
   docker restart <container-name>
   ```

2. **Verify the fix** using the diagnostic script:
   ```bash
   python scripts/diagnose_openwebui_export.py
   ```

3. **Test the export** from Dovos UI by trying to export a conversation.

## Additional Security Considerations

### Regenerate Your API Key (Optional but Recommended)

After enabling API keys, you may want to regenerate your API key in OpenWebUI:

1. Log into OpenWebUI web interface
2. Go to Settings → Account → API Keys
3. Delete the old key
4. Create a new API key
5. Update the key in Dovos config:

```python
# config/__init__.py
OPENWEBUI_API_KEY = "your-new-api-key-here"
```

Or use environment variables (better for security):

```bash
# .env file
OPENWEBUI_API_KEY=your-new-api-key-here
```

And update config to read from env:

```python
# config/__init__.py
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")
```

### Restrict API Key Permissions

In OpenWebUI, you can limit what the API key can do:
- Read-only access
- Create chats
- Delete chats
- etc.

Make sure your API key has at least "Create chats" permission.

## OpenWebUI Environment Variables Reference

Here are other useful OpenWebUI environment variables:

```bash
# Required for API keys
ENABLE_API_KEY=true

# Optional: Set a strong secret key for token signing
WEBUI_SECRET_KEY=your-very-long-random-secret-key

# Optional: Enable additional security
ENABLE_LOGIN_FORM=true
ENABLE_SIGNUP=false
```

## Troubleshooting

### Still getting 403 after enabling?

1. **Check OpenWebUI logs**:
   ```bash
   # For Docker
   docker logs <openwebui-container-name>
   ```

2. **Verify the setting took effect**:
   Run the diagnostic script which will test various endpoints and show detailed error messages.

3. **Check API key validity**:
   - Go to OpenWebUI Settings → Account → API Keys
   - Verify your API key exists and is active
   - Check it has the necessary permissions

4. **Try a different endpoint**:
   OpenWebUI might have changed the API endpoint. The diagnostic script tests multiple endpoints.

### Connection test passes but export fails?

This means:
- ✓ Network connectivity is good
- ✓ API key is valid for reading
- ✗ API key lacks permission to create/import chats

**Fix**: In OpenWebUI, edit your API key permissions to allow chat creation.

## References

- [OpenWebUI Environment Variables Documentation](https://docs.openwebui.com/getting-started/env-configuration)
- [OpenWebUI API Documentation](https://docs.openwebui.com/api/)
- OpenWebUI GitHub Issues: Search for "ENABLE_API_KEY" for related discussions
