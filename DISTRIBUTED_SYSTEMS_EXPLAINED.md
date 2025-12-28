# Distributed Systems: Correlation IDs vs. Idempotency

## Quick Answer

**Correlation ID:** Used for **tracing/debugging** requests across services
**Redis Lock:** Used for **preventing duplicate processing** across multiple pods

They solve DIFFERENT problems and you need BOTH!

---

## 1. What is a Correlation ID?

A **correlation ID** is a unique identifier (UUID) that follows a single request through its entire journey across multiple services.

### Purpose: Distributed Tracing & Debugging

**Problem:** When you have multiple services (API, Celery, S3, Database), how do you trace a single user request?

**Example: User uploads DICOM file**

```
User clicks "Upload" button
    ↓
Browser generates correlation ID: abc-123
    ↓
POST /api/studies/456/upload/
    Headers: X-Correlation-ID: abc-123
    ↓
Django API receives request
    Middleware extracts correlation_id = "abc-123"
    Logs: [abc-123] Received upload request from user_id=789
    ↓
Django triggers Celery task
    process_dicom_images_async.delay(study_id=456, correlation_id="abc-123")
    ↓
Celery Worker picks up task
    set_correlation_id("abc-123")
    Logs: [abc-123] Starting DICOM processing, task_id=xyz-789
    ↓
Upload to S3
    Logs: [abc-123] Uploading to S3: study_456_image_001.dcm
    ↓
S3 upload fails with timeout
    Logs: [abc-123] S3 upload failed: timeout after 30s
    ↓
Celery retries (automatic)
    Logs: [abc-123] Retrying upload (attempt 1/3)
    ↓
S3 upload succeeds on retry
    Logs: [abc-123] S3 upload successful
    ↓
Save to Database
    AuditLog: {correlation_id: "abc-123", action: "process", ...}
    Logs: [abc-123] Study 456 processing completed
```

### Debugging with Correlation ID

**User reports:** "My upload is stuck!"

**Without Correlation ID:**
```bash
# You have to guess which request is theirs
grep "study_id=456" /var/log/django.log
# Returns 1000s of results from different users 😱
```

**With Correlation ID:**
```bash
# User gives you correlation ID from error message in UI
grep "abc-123" /var/log/django.log /var/log/celery.log /var/log/s3.log

# Results (end-to-end trace):
[2025-12-28 10:15:23] [abc-123] API: POST /api/studies/456/upload/ user_id=789
[2025-12-28 10:15:25] [abc-123] Celery: Starting DICOM processing
[2025-12-28 10:15:45] [abc-123] S3: Upload failed - timeout
[2025-12-28 10:15:46] [abc-123] Celery: Retrying upload (attempt 1/3)
[2025-12-28 10:16:15] [abc-123] S3: Upload successful ✅

# You can tell the user: "Your upload succeeded after retry. It's complete!"
```

### Correlation ID Flow in Your Code

**Frontend (`frontend/lib/api/client.ts:28-36`):**
```typescript
// Request interceptor - adds correlation ID to every request
this.client.interceptors.request.use((config) => {
  // Generate or retrieve correlation ID from sessionStorage
  let correlationId = this.getCorrelationId();
  if (!correlationId) {
    correlationId = this.generateCorrelationId(); // UUID v4
    this.setCorrelationId(correlationId);
  }

  // Send to backend
  config.headers['X-Correlation-ID'] = correlationId;
  return config;
});
```

**Backend (`firstproject/correlation_middleware.py:32-37`):**
```python
class CorrelationIdMiddleware:
    def __call__(self, request):
        # Extract correlation ID from request header
        correlation_id = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())

        # Store in thread-local context
        set_correlation_id(correlation_id)

        # Process request
        response = self.get_response(request)

        # Return correlation ID in response header
        response['X-Correlation-ID'] = correlation_id
        return response
```

**Celery Task (`medical_imaging/tasks.py:65-73`):**
```python
def process_dicom_images_async(self, study_id, file_data_list, user_id=None, correlation_id=None):
    # Set correlation ID for this task context
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    # Now all logs include correlation ID
    logger.info(
        f"Starting DICOM processing for study {study_id}",
        extra={'correlation_id': correlation_id, 'task_id': task_id}
    )

    # Store in audit log for compliance
    AuditLog.objects.create(
        action='process',
        resource_id=study_id,
        details={'correlation_id': correlation_id}  # ← Searchable in DB
    )
```

---

## 2. Idempotency & Distributed Locks

**Correlation ID does NOT prevent duplicate processing!**

### The Problem: Multiple Pods

```
Kubernetes Deployment with 3 pods:

┌──────────┐  ┌──────────┐  ┌──────────┐
│  Pod A   │  │  Pod B   │  │  Pod C   │
│ Django   │  │ Django   │  │ Django   │
└──────────┘  └──────────┘  └──────────┘
      ↓             ↓             ↓
┌─────────────────────────────────────┐
│        Load Balancer                │
└─────────────────────────────────────┘
                  ↓
          User double-clicks "Upload"
                  ↓
    Request 1 → Pod A (correlation_id: abc-123)
    Request 2 → Pod B (correlation_id: def-456)  ← Different correlation ID!
                  ↓
        🚨 BOTH pods trigger Celery tasks 🚨
                  ↓
         Same study processed TWICE!
```

**Problem:** Each request gets a different correlation ID, so tracing works, but you process the same data twice!

### Solution: Redis-Based Distributed Lock

**Central Redis** (shared by all pods):

```
Redis Server (Single Instance)
       ↑
       │ (all pods connect to same Redis)
       ├─────────────┬─────────────┐
       │             │             │
   Pod A         Pod B         Pod C
```

**How it works:**

```python
# medical_imaging/tasks.py:76-85
lock_key = f"dicom-processing-{study_id}"

# Try to acquire lock (Redis SET NX - "Set if Not eXists")
if not cache.add(lock_key, task_id, LOCK_TIMEOUT):
    # Lock already exists - someone else is processing this study
    existing_lock = cache.get(lock_key)
    logger.warning(
        f"Study {study_id} already being processed by task {existing_lock}. Skipping."
    )
    return {'status': 'skipped', 'reason': 'already_processing'}

# Lock acquired - we can process
try:
    # ... process DICOM images ...
finally:
    # Release lock
    cache.delete(lock_key)
```

### Scenario: User Double-Clicks Upload

```
Time: 10:15:23.000
User double-clicks "Upload" button
    ↓
Request 1 (correlation_id: abc-123) → Pod A
Request 2 (correlation_id: def-456) → Pod B
    ↓
Both arrive at same time!

─────────────────────────────────────────────────────────

Pod A Timeline:
10:15:23.100 - Task triggered: process_dicom_images_async(study_id=456, correlation_id="abc-123")
10:15:23.101 - Try to acquire lock: cache.add("dicom-processing-456", "task-abc", 600)
10:15:23.102 - ✅ Lock acquired! (Redis SET succeeded)
10:15:23.103 - [abc-123] Starting DICOM processing...
10:15:45.000 - [abc-123] Processing complete
10:15:45.001 - Release lock: cache.delete("dicom-processing-456")

─────────────────────────────────────────────────────────

Pod B Timeline:
10:15:23.105 - Task triggered: process_dicom_images_async(study_id=456, correlation_id="def-456")
10:15:23.106 - Try to acquire lock: cache.add("dicom-processing-456", "task-def", 600)
10:15:23.107 - ❌ Lock already exists! (Redis SET failed - key exists)
10:15:23.108 - Check who owns lock: cache.get("dicom-processing-456") → "task-abc"
10:15:23.109 - [def-456] WARNING: Study 456 already being processed by task-abc. Skipping.
10:15:23.110 - Return: {'status': 'skipped', 'reason': 'already_processing'}

─────────────────────────────────────────────────────────

Result:
✅ Pod A processes the study (correlation_id: abc-123)
✅ Pod B skips processing (correlation_id: def-456)
✅ No duplicate processing!
✅ Both requests are traceable by their correlation IDs
```

---

## 3. Do You Need Central Redis?

**YES! You MUST have a central Redis for distributed systems.**

### Why Each Pod Can't Have Its Own Redis

```
❌ WRONG: Each pod has its own Redis

Pod A Redis: {"dicom-processing-456": "task-abc"}
Pod B Redis: {"dicom-processing-456": "task-def"}  ← Different Redis!
Pod C Redis: (empty)

Problem: Pod B doesn't know Pod A is processing study 456!
Result: Both process the same study 🚨
```

```
✅ CORRECT: All pods share central Redis

            Central Redis
    {"dicom-processing-456": "task-abc"}
                 ↑
        ┌────────┼────────┐
        │        │        │
    Pod A    Pod B    Pod C

Pod A: Acquired lock ✅
Pod B: Lock exists, skip ✅
Pod C: Lock exists, skip ✅

Result: Only Pod A processes study 456 ✅
```

### Redis Architecture in Production

**Development (docker-compose.yml):**
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  django:
    # All Django pods connect to same Redis
    environment:
      REDIS_URL: redis://redis:6379/0
```

**Production (Kubernetes):**
```yaml
# Redis Deployment (1 replica or Redis Cluster)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1  # Single Redis instance
  template:
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
---
# Redis Service (stable endpoint)
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
  - port: 6379
---
# Django Deployment (3 replicas)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-api
spec:
  replicas: 3  # Multiple pods
  template:
    spec:
      containers:
      - name: django
        env:
        - name: REDIS_URL
          value: redis://redis:6379/0  # ← All pods use same Redis
```

**AWS Production:**
```
ElastiCache Redis (Managed)
        ↓
  redis.abc123.cache.amazonaws.com:6379
        ↑
    ┌───┴───┬───────┬───────┐
    │       │       │       │
  Pod 1   Pod 2   Pod 3   Pod 4
```

---

## 4. Two-Level Idempotency Protection

Your code has **TWO layers** of duplicate prevention:

### Layer 1: Redis Lock (Fast, Distributed)

```python
# medical_imaging/tasks.py:76-85
lock_key = f"dicom-processing-{study_id}"

if not cache.add(lock_key, task_id, LOCK_TIMEOUT):
    # Another task already processing this study
    return {'status': 'skipped', 'reason': 'already_processing'}
```

**Purpose:**
- Prevents multiple Celery workers from processing same study
- Works across all pods (shared Redis)
- Fast check (no database query)
- Lock expires after 600 seconds (LOCK_TIMEOUT)

**Race condition window:** Tiny (milliseconds)

### Layer 2: Database Pessimistic Lock (Slower, Guarantees Consistency)

```python
# medical_imaging/tasks.py:107-116
with transaction.atomic():
    # SELECT ... FOR UPDATE (database-level lock)
    study = ImagingStudy.objects.select_for_update().get(id=study_id)

    # Check if already completed (idempotency)
    if study.status == 'completed':
        logger.info(f"Study {study_id} already completed. Skipping.")
        return {'status': 'already_completed'}

    # Mark as in progress
    study.status = 'in_progress'
    study.save()
```

**Purpose:**
- Guarantees no duplicate processing even if Redis fails
- Database-level row lock (PostgreSQL/MySQL)
- Slower but 100% reliable

**Why both?**
- Redis: Fast path (99.9% of cases)
- Database: Safety net (Redis failure, lock expiration, retry after 10 minutes)

---

## 5. Correlation ID vs. Idempotency Lock

| Feature | Correlation ID | Redis Lock |
|---------|----------------|------------|
| **Purpose** | Tracing/debugging | Prevent duplicates |
| **Scope** | Single request journey | Single resource (study) |
| **Uniqueness** | Every request gets unique ID | Same study = same lock key |
| **Storage** | SessionStorage (frontend), Context (backend) | Redis (distributed) |
| **Lifetime** | Entire request lifecycle | Processing duration |
| **Shared across pods?** | ❌ No (different correlation IDs) | ✅ Yes (same Redis) |
| **Use case** | "Where did my request fail?" | "Don't process study twice" |

### Example: Double-Click Scenario

```
User double-clicks "Upload" button

Request 1:
  Correlation ID: abc-123  ← Unique to this request
  Lock Key: dicom-processing-456  ← Same study
  Result: Processes study ✅

Request 2:
  Correlation ID: def-456  ← Different correlation ID!
  Lock Key: dicom-processing-456  ← Same lock key!
  Result: Skipped (lock exists) ✅

Summary:
- Different correlation IDs = Two separate traces ✅
- Same lock key = Only one processes ✅
```

---

## 6. Real-World Interview Scenario

**Interviewer:** "Your app is deployed on Kubernetes with 5 pods. User uploads a DICOM study. Walk me through what happens."

**Your Answer:**

**Step 1: Request arrives**
```
User clicks "Upload"
  → Frontend generates correlation ID: abc-123
  → POST /api/studies/456/upload/
  → Load balancer routes to Pod 3
```

**Step 2: Django API (Pod 3)**
```
Middleware:
  - Extracts correlation_id = "abc-123"
  - Sets in thread-local context
  - Logs: [abc-123] POST /api/studies/456/upload/ user_id=789

View:
  - Triggers Celery task
  - Passes correlation_id to worker
  - Returns 202 Accepted
```

**Step 3: Celery Worker**
```
Worker picks up task:
  - Task ID: xyz-789
  - Correlation ID: abc-123
  - Study ID: 456

Idempotency Check (Redis):
  - Lock key: "dicom-processing-456"
  - cache.add("dicom-processing-456", "xyz-789", 600)
  - Result: ✅ Lock acquired

Database Check (PostgreSQL):
  - SELECT ... FOR UPDATE WHERE id = 456
  - study.status = 'pending'
  - Set study.status = 'in_progress'

Processing:
  - [abc-123] Parsing DICOM files...
  - [abc-123] Uploading to S3...
  - [abc-123] Creating thumbnails...
  - [abc-123] Saving to database...

Completion:
  - Set study.status = 'completed'
  - Set study.processing_version = 'v1.2.0'
  - Release Redis lock
  - Create audit log with correlation_id
```

**Step 4: User refreshes page**
```
Second request (different correlation ID: def-456):
  - Load balancer routes to Pod 1 (different pod!)
  - Pod 1 tries to acquire lock
  - Redis: Lock "dicom-processing-456" already exists
  - [def-456] Study already processing, skip
  - Returns: {'status': 'skipped'}
```

**Interviewer:** "What if Redis goes down?"

**Your Answer:**

"We have a two-level idempotency check:

1. **Redis check (fast):** If Redis is down, this check is skipped
2. **Database lock (reliable):** `SELECT ... FOR UPDATE` guarantees only one worker can lock the row

Even if Redis fails, the database lock prevents duplicate processing. Redis is an optimization for speed, not a single point of failure."

**Interviewer:** "How do you debug if the upload fails?"

**Your Answer:**

"User reports the issue, I ask them to check browser console for correlation ID (shown in error message).

Then I grep all logs:
```bash
grep "abc-123" /var/log/django.log /var/log/celery.log
```

This shows the entire request journey across all services, making it easy to find where it failed."

---

## Summary

### Correlation ID
- **What:** Unique identifier (UUID) for a request
- **Why:** Trace requests across services for debugging
- **Where:** Frontend, Django, Celery, Audit logs
- **Shared across pods?** No (different correlation IDs per request)

### Redis Lock
- **What:** Distributed lock with key = `dicom-processing-{study_id}`
- **Why:** Prevent duplicate processing across multiple pods/workers
- **Where:** Central Redis shared by all pods
- **Shared across pods?** Yes (same Redis, same lock key)

### Do you need central Redis?
**YES!** All pods must connect to the same Redis for distributed locks to work.

### They solve different problems:
- **Correlation ID:** "Where did my request go?" (tracing)
- **Redis Lock:** "Don't process this study twice" (idempotency)

You need **BOTH** for a production-ready distributed system!
