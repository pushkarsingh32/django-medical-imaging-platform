#!/bin/bash

# Start development environment with Django + Celery + Redis
# Usage: ./start_dev.sh

echo "Starting Medical Imaging Platform Development Environment..."
echo "============================================================"

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Starting Redis server..."
    redis-server --daemonize yes
    sleep 2
fi

echo "✓ Redis is running"

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A firstproject worker --loglevel=info --detach --logfile=logs/celery.log --pidfile=logs/celery.pid

echo "✓ Celery worker started (logs: logs/celery.log)"

# Start Django development server
echo "Starting Django development server..."
echo "============================================================"
python3 manage.py runserver

# Cleanup on exit
trap "echo 'Stopping services...'; celery -A firstproject control shutdown; redis-cli shutdown" EXIT
