FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Install MCP-specific dependencies
RUN pip install --no-cache-dir -r dovos_mcp/requirements.txt

# Create logs directory
RUN mkdir -p logs

# Expose MCP HTTP port
EXPOSE 8001

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health', timeout=5)"

# Run the MCP HTTP server
CMD ["python", "-m", "uvicorn", "dovos_mcp.http_server:app", "--host", "0.0.0.0", "--port", "8001"]
