#!/bin/bash
set -e

echo "==== Dovos Docker Entrypoint ===="

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

until python -c "from db.database import test_connection; exit(0 if test_connection() else 1)" 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "ERROR: PostgreSQL did not become ready in time"
        exit 1
    fi
    echo "Waiting for PostgreSQL... (attempt $attempt/$max_attempts)"
    sleep 2
done

echo "✓ PostgreSQL is ready!"

# Run Alembic migrations
echo "Running database migrations..."
if alembic upgrade head; then
    echo "✓ Migrations completed successfully"
else
    echo "ERROR: Migrations failed"
    exit 1
fi

# Start the application
echo "Starting application..."
exec "$@"
