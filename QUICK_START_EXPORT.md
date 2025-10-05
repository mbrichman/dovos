# Quick Start: Export to OpenWebUI

## 1. Verify Configuration

Check that your OpenWebUI settings are correct in `config.py`:

```python
OPENWEBUI_URL = "http://100.116.198.80:4000"
OPENWEBUI_API_KEY = "sk-44016316021243d0b0a00ba36aa0c22e"
```

## 2. Test Connection (Optional but Recommended)

```bash
cd /Users/markrichman/projects/dovos
source venv/bin/activate
python test_openwebui_connection.py
```

This will verify:
- ✓ Your OpenWebUI server is reachable
- ✓ Your API key is valid
- ✓ The import endpoint is available

## 3. Start Your Flask App

```bash
cd /Users/markrichman/projects/dovos
source venv/bin/activate
python app.py
```

Or however you normally start your Flask app.

## 4. Use the Export Feature

1. Navigate to any conversation in your browser
2. Look for the green "Export to OpenWebUI" button
3. Click it
4. Wait for the "Exported!" message
5. Check your OpenWebUI instance - the conversation should appear!

## Troubleshooting

### Button Not Appearing?
- Make sure you're viewing a conversation (not the list view)
- Hard refresh your browser (Cmd+Shift+R or Ctrl+Shift+R)

### Export Fails?
- Run the test script to check connectivity
- Check browser console (F12) for JavaScript errors
- Verify API key hasn't expired
- Check OpenWebUI server logs

### Still Having Issues?
See the full troubleshooting guide in `OPENWEBUI_EXPORT.md`

## What Gets Exported?

- Conversation title
- All messages (user and assistant)
- Timestamps
- Metadata

The conversation will appear in OpenWebUI exactly as if you had the chat there originally!
