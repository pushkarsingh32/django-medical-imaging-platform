# Celery Setup for Medical Imaging Platform

This document explains the Celery setup for asynchronous DICOM image processing.

## Overview

We use Celery with Redis as a message broker to handle DICOM image processing asynchronously. This allows the API to return immediately when users upload images, while background workers process the files.

## Architecture

```
User Upload → Django API (HTTP 202) → Redis Queue → Celery Worker → Database
                    ↓                                      ↓
              Returns task_id                    Updates TaskStatus
                    ↓                                      ↓
            User polls /tasks/{id}/  ←────────────────────┘
```

## Prerequisites

- Redis server running (default: localhost:6379)
- Python dependencies installed (see requirements.txt)

## Installation

### 1. Install Dependencies

```bash
pip install celery redis
```

### 2. Configure Redis

Set environment variables in `.env`:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
CELERY_BROKER_DB=1
CELERY_RESULT_DB=2
```

### 3. Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## Running Celery

### Start Redis Server

```bash
# macOS (via Homebrew)
brew services start redis

# Linux
sudo systemctl start redis

# Windows (via WSL or Docker)
docker run -d -p 6379:6379 redis
```

### Start Celery Worker

In the project root directory (where manage.py is located):

```bash
# Development
celery -A firstproject worker --loglevel=info

# Production (with concurrency)
celery -A firstproject worker --loglevel=info --concurrency=4

# With auto-reload for development
watchmedo auto-restart -d . -p '*.py' -- celery -A firstproject worker --loglevel=info
```

### Start Celery Beat (Optional - for periodic tasks)

```bash
celery -A firstproject beat --loglevel=info
```

## Configuration

### Celery Settings (`firstproject/celery.py`)

- **Broker**: Redis database 1 (task queue)
- **Result Backend**: Redis database 2 (task results)
- **Serialization**: JSON only (secure)
- **Timezone**: UTC
- **Task Time Limits**:
  - Hard limit: 30 minutes
  - Soft limit: 25 minutes
- **Worker Settings**:
  - Prefetch: 1 task at a time
  - Max tasks per worker child: 1000 (then restart)

## Usage

### 1. Upload Images (Async)

**Endpoint**: `POST /api/medical/studies/{id}/upload_images/`

**Request**:
```bash
curl -X POST http://localhost:8000/api/medical/studies/1/upload_images/ \
  -F "images=@image1.dcm" \
  -F "images=@image2.dcm"
```

**Response** (HTTP 202):
```json
{
  "message": "Processing 2 image(s) in background",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "total_files": 2,
  "status": "processing"
}
```

### 2. Check Task Status

**Endpoint**: `GET /api/medical/tasks/{task_id}/`

**Request**:
```bash
curl http://localhost:8000/api/medical/tasks/a1b2c3d4-e5f6-7890-abcd-1234567890ef/
```

**Response**:
```json
{
  "id": 1,
  "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ef",
  "task_name": "DICOM Image Processing",
  "status": "processing",
  "created_at": "2025-12-27T10:30:00Z",
  "updated_at": "2025-12-27T10:30:15Z",
  "total_items": 2,
  "processed_items": 1,
  "failed_items": 0,
  "progress_percentage": 50,
  "result": null,
  "error_message": "",
  "study": 1,
  "user": 1
}
```

### 3. Poll for Completion

Frontend should poll the task status endpoint every 2-3 seconds until:
- `status` becomes `"completed"` or `"failed"`
- `progress_percentage` reaches 100

## Task Statuses

| Status | Description |
|--------|-------------|
| `pending` | Task created but not yet picked up by worker |
| `processing` | Worker is actively processing the task |
| `completed` | All images processed successfully |
| `failed` | Task encountered errors |

## Monitoring

### Django Admin

Visit `/admin/medical_imaging/taskstatus/` to view all tasks:
- Task ID and name
- Current status
- Progress percentage
- Created/updated timestamps
- Associated study and user

### Celery Flower (Optional)

Install and run Flower for real-time monitoring:

```bash
pip install flower
celery -A firstproject flower
```

Visit `http://localhost:5555` for web-based monitoring.

## Error Handling

### Task Retries

Tasks automatically retry up to 3 times on failure with exponential backoff.

### Error Messages

Failed tasks store error details in:
- `TaskStatus.error_message` - Human-readable error
- `TaskStatus.result` - Detailed error breakdown

### Common Issues

1. **Redis Connection Refused**
   ```
   Error: [Errno 61] Connection refused
   Solution: Ensure Redis is running on specified host/port
   ```

2. **Task Never Starts**
   ```
   Status stays "pending"
   Solution: Ensure Celery worker is running
   ```

3. **Worker Crashes**
   ```
   Check logs for memory issues or task timeout
   Solution: Adjust concurrency or time limits
   ```

## Production Deployment

### Supervisor (Linux)

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A firstproject worker --loglevel=info --concurrency=4
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log
```

### Systemd (Linux)

Create `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/celery -A firstproject worker --loglevel=info --concurrency=4
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker

```dockerfile
# Celery Worker
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["celery", "-A", "firstproject", "worker", "--loglevel=info", "--concurrency=4"]
```

## Performance Tuning

### Concurrency

- **CPU-bound tasks**: Set concurrency to CPU cores
- **I/O-bound tasks**: Set concurrency to 2-4x CPU cores
- **DICOM processing**: Start with 2-4 workers

### Prefetch Multiplier

- **Default**: 4 (worker fetches 4 tasks ahead)
- **Our setting**: 1 (fetch one at a time)
- **Reason**: DICOM files are large; prevents memory overload

### Task Time Limits

- **Hard limit**: 30 minutes (task is killed)
- **Soft limit**: 25 minutes (SoftTimeLimitExceeded exception)
- **Adjust** based on your largest DICOM file sizes

## Testing

### Unit Tests

```python
from medical_imaging.tasks import process_dicom_images_async

# Test task execution
result = process_dicom_images_async.delay(study_id=1, file_data_list=[...])
assert result.status == 'SUCCESS'
```

### Integration Tests

```python
# Test full upload flow
response = client.post('/api/medical/studies/1/upload_images/', {
    'images': [file1, file2]
})
assert response.status_code == 202
assert 'task_id' in response.data

# Poll for completion
task_id = response.data['task_id']
status = client.get(f'/api/medical/tasks/{task_id}/')
assert status.data['status'] in ['processing', 'completed']
```

## Security Considerations

1. **Serialization**: Only JSON allowed (prevents pickle exploits)
2. **Task Arguments**: Validate all inputs before processing
3. **File Upload**: Files read into memory, validated before task dispatch
4. **Authentication**: Task status endpoint accessible to task creator only (implement in production)
5. **Rate Limiting**: Add rate limits to upload endpoint to prevent abuse

## Troubleshooting

### Enable Debug Logging

```python
# settings.py
CELERY_WORKER_LOG_LEVEL = 'DEBUG'
```

### Inspect Active Tasks

```bash
celery -A firstproject inspect active
```

### Purge All Tasks

```bash
celery -A firstproject purge
```

### Monitor Redis

```bash
redis-cli
> SELECT 1  # Broker DB
> KEYS *
> SELECT 2  # Result DB
> KEYS *
```

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Django-Celery Integration](https://docs.celeryproject.org/en/stable/django/)
- [Redis Documentation](https://redis.io/documentation)
