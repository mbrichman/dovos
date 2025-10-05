# OpenWebUI Export Feature

This feature allows you to export conversations from DovOS directly to your OpenWebUI instance.

## Configuration

The OpenWebUI connection settings are stored in `config.py`:

```python
# OpenWebUI Configuration
OPENWEBUI_URL = "http://100.116.198.80:4000"
OPENWEBUI_API_KEY = "sk-44016316021243d0b0a00ba36aa0c22e"
```

### Changing OpenWebUI Server

To point to a different OpenWebUI server:

1. Open `config.py`
2. Update `OPENWEBUI_URL` to your server's URL
3. Update `OPENWEBUI_API_KEY` with your API key
4. Restart the Flask app

### Getting Your API Key

To get your OpenWebUI API key:

1. Log into your OpenWebUI instance
2. Go to Settings > Account
3. Navigate to the API Keys section
4. Create a new API key or copy an existing one

## Usage

1. Navigate to any conversation in DovOS
2. Click the "Export to OpenWebUI" button (green button next to "Export as Markdown")
3. Wait for the export to complete
4. Check your OpenWebUI instance - the conversation should now appear in your chat history

## How It Works

The export process:

1. Retrieves the conversation from the ChromaDB database
2. Parses the conversation messages (supports ChatGPT and Claude formats)
3. Converts the conversation to OpenWebUI's expected JSON format using the `claude_to_openwebui_converter.py` script
4. Sends the converted conversation to OpenWebUI via its import API endpoint
5. Displays success or error messages

## Supported Formats

- ChatGPT conversations
- Claude conversations
- Generic AI conversations (with **You said** and **AI said** markers)

## Troubleshooting

### Connection Errors

If you see "Failed to connect to OpenWebUI":
- Verify the OpenWebUI server is running
- Check that the URL in `config.py` is correct
- Ensure your network can reach the OpenWebUI server
- Check firewall settings

### API Errors

If you see "OpenWebUI API error":
- Verify your API key is valid
- Check OpenWebUI logs for more details
- Ensure the API endpoint `/api/v1/chats/import` is available

### Conversion Errors

If you see "Conversion failed":
- The conversation format may not be recognized
- Check the conversation source metadata
- Review the `claude_to_openwebui_converter.py` script for format compatibility

## API Endpoint

The export functionality is available via:

```
POST /export_to_openwebui/<conversation_id>
```

Response format:
```json
{
  "success": true,
  "message": "Conversation exported to OpenWebUI successfully"
}
```

Or on error:
```json
{
  "success": false,
  "error": "Error description",
  "detail": "Additional error details"
}
```
