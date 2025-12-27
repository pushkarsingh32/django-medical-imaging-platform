#!/bin/bash

# Start all services in tmux session
# Usage: ./start_tmux.sh

SESSION_NAME="medical_imaging"

# Check if session exists
tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    echo "Creating new tmux session: $SESSION_NAME"

    # Create new session with Django server
    tmux new-session -d -s $SESSION_NAME -n django
    tmux send-keys -t $SESSION_NAME:django "cd $(pwd) && source venv/bin/activate 2>/dev/null || true && python manage.py runserver" C-m

    # Create window for Celery worker
    tmux new-window -t $SESSION_NAME -n celery
    tmux send-keys -t $SESSION_NAME:celery "cd $(pwd) && source venv/bin/activate 2>/dev/null || true && celery -A firstproject worker --loglevel=info" C-m

    # Create window for Redis (if needed)
    tmux new-window -t $SESSION_NAME -n redis
    tmux send-keys -t $SESSION_NAME:redis "redis-server" C-m

    # Create window for logs/monitoring
    tmux new-window -t $SESSION_NAME -n logs
    tmux send-keys -t $SESSION_NAME:logs "cd $(pwd)" C-m

    echo "✓ Tmux session created!"
    echo ""
    echo "Windows created:"
    echo "  0: django  - Django development server"
    echo "  1: celery  - Celery worker"
    echo "  2: redis   - Redis server"
    echo "  3: logs    - Monitoring/logs"
    echo ""
    echo "Attach to session with: tmux attach -t $SESSION_NAME"
    echo "Switch windows: Ctrl+b then 0/1/2/3"
    echo "Detach session: Ctrl+b then d"
    echo "Kill session: tmux kill-session -t $SESSION_NAME"
else
    echo "Session $SESSION_NAME already exists"
    echo "Attach with: tmux attach -t $SESSION_NAME"
fi

# Attach to session
tmux attach -t $SESSION_NAME
