#!/bin/bash

# Startup script for DovOS with RAG integration

echo "Starting DovOS services..."

# Start the main Flask app (if not already running)
if ! pgrep -f "python.*app.py" > /dev/null; then
    echo "Starting main DovOS app..."
    python app.py &
    MAIN_PID=$!
    echo "Main app started with PID $MAIN_PID"
else
    echo "Main DovOS app already running"
fi

# Start the RAG service
if ! pgrep -f "python.*rag_service.py" > /dev/null; then
    echo "Starting RAG service..."
    python rag_service.py &
    RAG_PID=$!
    echo "RAG service started with PID $RAG_PID"
else
    echo "RAG service already running"
fi

echo ""
echo "Services started successfully!"
echo ""
echo "Main DovOS app: http://localhost:5001"
echo "RAG service: http://localhost:8000"
echo ""
echo "To stop services, run: pkill -f 'python.*app.py' && pkill -f 'python.*rag_service.py'"
