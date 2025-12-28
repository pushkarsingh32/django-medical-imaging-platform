# Medical Imaging Platform - Interview Q&A Guide

**Project:** Django + Next.js Medical Imaging Platform
**Stack:** Django 5.2, DRF, MySQL, Celery, Redis, Next.js 15, React 19, TypeScript, React Query
**Domain:** Healthcare/Radiology DICOM Image Management

---

## Table of Contents
1. [Django Models & Database Design](#django-models--database-design)
2. [SQL Fundamentals](#sql-fundamentals)
3. [REST API Architecture](#rest-api-architecture)
4. [Celery & Async Processing](#celery--async-processing)
5. [DICOM Domain Knowledge](#dicom-domain-knowledge)
6. [Frontend Architecture (React/Next.js)](#frontend-architecture-reactnextjs)
7. [Testing & Quality Assurance](#testing--quality-assurance)
8. [DevOps & Deployment](#devops--deployment)
9. [Security & HIPAA Compliance](#security--hipaa-compliance)
10. [Performance & Optimization](#performance--optimization)

---

## Django Models & Database Design

### Q1: Explain the multi-tenancy architecture in your medical imaging platform. How is data isolation achieved?

**Answer:**

The platform implements **hospital-based multi-tenancy** using Django's ForeignKey relationships. Each hospital has completely isolated data through the following design:

**Code Reference:** `firstproject/medical_imaging/models.py:7-26`

```python
class Hospital(models.Model):
    """
    Represents a hospital/clinic organization.
    Multi Tenancy: Each Hospital has isolated data
    """
    name = models.CharField(max_length=200, unique=True)
    address = models.TextField()
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),          # Fast hospital lookup
            models.Index(fields=['created_at']),    # Recent hospitals query
        ]
```

**Patient Model with Hospital FK:** `models.py:39-43`

```python
hospital = models.ForeignKey(
    Hospital,
    on_delete=models.PROTECT,  # Can't delete hospital if patients exist
    related_name='patients'
)
```

**Key Design Decisions:**

1. **PROTECT on_delete**: Using `on_delete=models.PROTECT` prevents deleting a hospital if patients exist, ensuring data integrity and preventing accidental data loss
2. **Indexed lookups**: Composite index on `['hospital', 'last_name']` (line 60) enables fast patient queries filtered by hospital
3. **Related names**: `related_name='patients'` allows reverse queries: `hospital.patients.all()`
4. **Cascade hierarchy**: Patient → ImagingStudy → DicomImage creates proper cascade deletion

**Data Isolation in Practice:**

In views (`views.py:133-144`), we can filter by hospital:
```python
queryset = Patient.objects.select_related('hospital').all()
# Can add: .filter(hospital=request.user.hospital)
```

This architecture supports **multiple hospitals** on a single database while maintaining complete data separation—critical for HIPAA compliance.

**Why row-level (not schema-based) tenancy?**
- Simpler to manage and deploy
- Works seamlessly with Django ORM
- Allows cross-hospital analytics if needed (with proper authorization)
- Lower infrastructure complexity
- Better for mid-scale applications (10-100 hospitals)

**Trade-offs:**
- Schema-based would provide stronger isolation but adds deployment complexity
- Application-level filtering requires careful query construction
- Must ensure all queries include hospital filter (can use middleware/manager)

---

### Q2: Explain the database indexes you implemented and why they're important for this application.

**Answer:**

I implemented **strategic database indexes** across all models to optimize common query patterns in a medical imaging system. Here's the breakdown:

**Patient Model Indexes** (`models.py:56-65`):

```python
class Meta:
    indexes = [
        models.Index(fields=['medical_record_number']),    # Unique lookup
        models.Index(fields=['hospital', 'last_name']),    # Hospital patient list
        models.Index(fields=['hospital', 'created_at']),   # Recent patients per hospital
        models.Index(fields=['gender']),                    # Gender filtering
        models.Index(fields=['date_of_birth']),            # Age-based queries
        models.Index(fields=['email']),                     # Email lookup for patient portal
    ]
```

**Why these specific indexes?**

1. **`medical_record_number`** - Single-column index for fast patient lookup (most common query)
2. **`['hospital', 'last_name']`** - **Composite index** for paginated patient lists per hospital (supports multi-tenancy queries)
3. **`['hospital', 'created_at']`** - Finds recently added patients per hospital (dashboard queries)
4. **`gender`** - Demographic filtering and statistical reports
5. **`date_of_birth`** - Age-based cohort analysis
6. **`email`** - Patient portal login lookups

**ImagingStudy Model Indexes** (`models.py:111-118`):

```python
indexes = [
    models.Index(fields=['patient', '-study_date']),    # Patient study history (DESC)
    models.Index(fields=['status']),                     # Status filtering
    models.Index(fields=['modality', '-study_date']),    # Modality-based queries
    models.Index(fields=['status', '-study_date']),      # Pending studies, etc.
    models.Index(fields=['-study_date']),               # Recent studies
    models.Index(fields=['body_part']),                  # Body part filtering
]
```

**Key Points:**

- **Descending indexes** (`-study_date`) optimize `ORDER BY study_date DESC` queries (most recent first)
- **Composite indexes** support filtering + sorting in one index lookup
- Supports common workflows: "Show all pending CT scans from last week"

**DicomImage Model Indexes** (`models.py:207-211`):

```python
indexes = [
    models.Index(fields=['study', 'instance_number']),  # Fast image lookup
    models.Index(fields=['-uploaded_at']),               # Recent uploads
    models.Index(fields=['file_size_bytes']),           # Size-based queries
]
```

**AuditLog Model Indexes** (`models.py:287-291`):

```python
indexes = [
    models.Index(fields=['-timestamp']),
    models.Index(fields=['user', '-timestamp']),
    models.Index(fields=['resource_type', 'resource_id']),
]
```

**Performance Impact:**

Without indexes:
```sql
-- Full table scan: O(n)
SELECT * FROM patient WHERE hospital_id = 5 ORDER BY last_name;
-- Scans all patients in database
```

With composite index `['hospital', 'last_name']`:
```sql
-- Index seek: O(log n)
-- Uses B-tree index, returns sorted results directly
```

**Index Trade-offs:**

✅ **Benefits:**
- 10-100x faster queries on large datasets
- Supports efficient pagination
- Enables real-time dashboards

❌ **Costs:**
- Slower INSERT/UPDATE/DELETE (index maintenance)
- Additional disk space (~10-30% of table size)
- Must choose indexes carefully

**Why I didn't index everything:**
- Avoided indexing `clinical_notes` (TEXT field, rarely filtered)
- Skipped low-cardinality fields like `is_dicom` (boolean)
- Focused on actual query patterns from views

**Real-world example:**

Dashboard query (`views.py:677-685`):
```python
stats = {
    'new_patients_this_month': Patient.objects.filter(
        created_at__gte=first_day_of_month
    ).count(),  # Uses ['hospital', 'created_at'] index
}
```

This demonstrates understanding of **database performance** and **query optimization**—critical for healthcare applications handling millions of images.

---

### Q3: Walk me through the relationship between Patient, ImagingStudy, DicomImage, and Diagnosis models. Why did you choose these specific on_delete behaviors?

**Answer:**

The models follow a **hierarchical medical workflow** with carefully chosen cascade behaviors:

**Model Hierarchy:**

```
Hospital (root)
    ↓ (PROTECT)
Patient
    ↓ (CASCADE)
ImagingStudy
    ├─→ (CASCADE) DicomImage
    └─→ (CASCADE, OneToOne) Diagnosis
```

**1. Hospital → Patient** (`models.py:39-43`):

```python
hospital = models.ForeignKey(
    Hospital,
    on_delete=models.PROTECT,  # ⚠️ PROTECT
    related_name='patients'
)
```

**Why PROTECT?**
- **Data safety**: Cannot accidentally delete a hospital with patients
- **Business logic**: Hospitals should never be deleted in healthcare systems
- **Compliance**: HIPAA requires audit trails—deleting hospitals would violate this
- **Forces explicit cleanup**: Must transfer/archive patients first

**Error you'd see:**
```python
ProtectedError: Cannot delete hospital because Patient objects exist
```

**2. Patient → ImagingStudy** (`models.py:94-98`):

```python
patient = models.ForeignKey(
    Patient,
    on_delete=models.CASCADE,  # ⚠️ CASCADE
    related_name='imaging_studies',
)
```

**Why CASCADE?**
- **Logical dependency**: Studies cannot exist without a patient
- **Data integrity**: Orphaned studies would be meaningless
- **HIPAA compliance**: Deleting patient = deleting all PHI (Protected Health Information)
- **Simplifies deletion**: One DELETE command handles entire patient record

**3. ImagingStudy → DicomImage** (`models.py:130-134`):

```python
study = models.ForeignKey(
    ImagingStudy,
    on_delete=models.CASCADE,  # ⚠️ CASCADE
    related_name='images'
)
```

**Why CASCADE?**
- **Physical dependency**: DICOM images belong to a specific study
- **File cleanup**: Deleting study triggers file deletion signals
- **Storage management**: Prevents orphaned files eating disk space
- **Data consistency**: Images without a study context are useless

**4. ImagingStudy → Diagnosis** (`models.py:228-232`):

```python
study = models.OneToOneField(
    ImagingStudy,
    on_delete=models.CASCADE,  # ⚠️ CASCADE
    related_name='diagnosis'
)
```

**Why OneToOneField + CASCADE?**
- **One diagnosis per study**: Business rule enforced at database level
- **Prevents duplicates**: Can't create multiple diagnoses for same study
- **Cascade deletion**: If study deleted, diagnosis should be too
- **Referential integrity**: Diagnosis is meaningless without the study

**5. Diagnosis → User (Radiologist)** (`models.py:233-238`):

```python
radiologist = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,  # ⚠️ SET_NULL
    null=True,
    related_name='diagnoses'
)
```

**Why SET_NULL?**
- **Audit preservation**: Keep diagnosis even if radiologist account deleted
- **Historical records**: Medical records must persist even if staff leaves
- **Compliance**: Can't delete historical medical data
- **Allows null**: `null=True` permits SET_NULL behavior

**Deletion Flow Example:**

```python
# Delete a patient
patient = Patient.objects.get(id=1)
patient.delete()

# What happens (automatically):
# 1. All ImagingStudy records CASCADE deleted
# 2. All DicomImage records CASCADE deleted (file signals triggered)
# 3. All Diagnosis records CASCADE deleted
# 4. AuditLog entries remain (SET_NULL on user FK)
```

**Alternative on_delete Options NOT Used:**

- **DO_NOTHING**: Would create orphaned records (bad for data integrity)
- **SET_DEFAULT**: No sensible default for medical entities
- **SET()**: No use case for dynamic value assignment

**Why this matters:**
- Demonstrates understanding of **database constraints**
- Shows **domain knowledge** (healthcare workflows)
- Indicates awareness of **data lifecycle management**
- Reflects **compliance considerations** (HIPAA)

**unique_together Constraint** (`models.py:206`):

```python
unique_together = ['study', 'instance_number']
```

Prevents duplicate DICOM instances within a study—enforces business rule at DB level.

---

### Q4: Explain the @property decorators you used in models (full_name, progress_percentage, file_size_mb). Why use properties instead of regular model fields?

**Answer:**

I use **@property decorators** for **computed/derived values** that don't need database storage. This follows the **DRY principle** and optimizes storage.

**1. Patient.full_name Property** (`models.py:70-72`):

```python
@property
def full_name(self):
    return f"{self.first_name} {self.last_name}"
```

**Why property instead of CharField?**

✅ **Computed value**: Always accurate—if name changes, `full_name` updates automatically
✅ **No redundancy**: Don't store what can be calculated
✅ **Storage savings**: No extra column needed
✅ **Clean API**: Access as `patient.full_name` (looks like a field)

❌ **Alternative (bad)**:
```python
# Would need to update full_name every time first_name/last_name changes
full_name = models.CharField(max_length=200)  # Prone to stale data!
```

**Used in serializers** (`serializers.py:34`):
```python
fields = ['full_name', ...]
read_only_fields = ['full_name', ...]  # Can't be written, only read
```

**2. TaskStatus.progress_percentage Property** (`models.py:386-390`):

```python
@property
def progress_percentage(self):
    """Calculate progress percentage"""
    if self.total_items == 0:
        return 0
    return int((self.processed_items / self.total_items) * 100)
```

**Why this is a property:**

✅ **Dynamic calculation**: Always reflects current `processed_items` / `total_items`
✅ **Prevents data staleness**: No risk of percentage being out of sync
✅ **Business logic**: Encapsulates calculation logic in one place
✅ **Div-by-zero safety**: Handles edge case (0 total items)

**Frontend usage:**
```typescript
// Real-time progress bar
const progress = taskStatus.progress_percentage;  // Always current
<ProgressBar value={progress} />
```

**3. PatientReport.file_size_mb Property** (`models.py:453-458`):

```python
@property
def file_size_mb(self):
    """Get file size in MB"""
    size_mb = self.file_size / (1024 * 1024)
    if size_mb < 0.01:  # Less than 0.01 MB, show in KB
        return f"{round(self.file_size / 1024, 1)} KB"
    return f"{round(size_mb, 2)} MB"
```

**Why property + custom logic:**

✅ **Human-readable format**: Converts bytes → "2.5 MB" or "850.3 KB"
✅ **Presentation logic**: Should NOT be in database (formatting, not data)
✅ **Automatic unit selection**: Switches between KB and MB intelligently
✅ **Reusable**: Can use in API, admin, templates

**Used in API response:**
```json
{
  "file_size": 2621440,           // Raw bytes (stored in DB)
  "file_size_mb": "2.50 MB"       // Formatted (computed property)
}
```

**4. PatientReport.file_url Property** (`models.py:446-450`):

```python
@property
def file_url(self):
    """Get public URL for the PDF file"""
    if self.pdf_file:
        return self.pdf_file.url
    return None
```

**Why property:**

✅ **URL generation**: Django's storage backend builds URL dynamically (S3, local, etc.)
✅ **Environment-aware**: URL changes based on storage configuration (dev vs prod)
✅ **Safe access**: Returns None if file doesn't exist (no exceptions)

**Properties vs. Methods:**

**Use @property when:**
- Value is computed from existing fields
- No parameters needed
- Reads like an attribute (`patient.age` not `patient.get_age()`)
- Cheap to calculate

**Use regular method when:**
- Need parameters (`get_studies(status='pending')`)
- Expensive operation (database query)
- Performs an action (not just returning data)

**Performance Consideration:**

Properties are calculated **every time** they're accessed:

```python
# ❌ Inefficient
for patient in patients:
    print(patient.full_name)  # Calls property 1000 times
```

```python
# ✅ Better - use annotation
from django.db.models import Value, CharField
from django.db.models.functions import Concat

patients = Patient.objects.annotate(
    full_name_computed=Concat('first_name', Value(' '), 'last_name')
)
```

**When serializing** (`serializers.py:244`):
```python
file_size_mb = serializers.ReadOnlyField()  # Automatically calls property
```

This demonstrates understanding of:
- **Data modeling** (normalized vs. computed)
- **Django ORM** features (properties, annotations)
- **Performance** trade-offs
- **Clean code** principles (DRY, encapsulation)

---

### Q5: You're storing DICOM metadata in a JSONField. Why use JSON instead of separate columns? What are the trade-offs?

**Answer:**

The **DicomImage model** uses a `JSONField` to store complete DICOM metadata (`models.py:193-197`):

```python
# Full DICOM metadata (JSON storage for all tags)
dicom_metadata = models.JSONField(
    default=dict,
    blank=True,
    help_text='Complete DICOM metadata as JSON'
)
```

**Why JSONField for DICOM metadata?**

✅ **Flexibility**: DICOM standard has 4000+ possible tags—can't create columns for all
✅ **Variable structure**: Different modalities (CT/MRI/X-Ray) have different metadata
✅ **Future-proof**: New DICOM tags don't require migrations
✅ **Complete preservation**: Store entire dataset for compliance/audit
✅ **Nested data**: DICOM has hierarchical structures (sequences) that JSON handles well

**What I DO store as columns** (commonly queried fields):

```python
# Spatial Information
slice_thickness = models.DecimalField(...)       # (0018,0050)
pixel_spacing = models.CharField(...)            # (0028,0030)
slice_location = models.FloatField(...)          # (0020,1041)

# Image Properties
rows = models.IntegerField(...)                  # (0028,0010)
columns = models.IntegerField(...)               # (0028,0011)

# Display Parameters
window_center = models.CharField(...)            # (0028,1050)
window_width = models.CharField(...)             # (0028,1051)

# Equipment Info
manufacturer = models.CharField(...)             # (0008,0070)
manufacturer_model = models.CharField(...)       # (0008,1090)

# DICOM Unique Identifiers
sop_instance_uid = models.CharField(...)         # (0008,0018)
```

**Strategy: Hybrid Approach**

**Frequently queried fields** → Dedicated columns with indexes
**Full metadata** → JSONField for completeness

**Example from dicom_service.py** (`tasks.py:96-127`):

```python
# Parse DICOM and extract specific fields
dicom_dataset, metadata = DicomParsingService.parse_dicom_file(file_obj)

image_data.update({
    # Dedicated columns (can query/filter)
    'slice_thickness': metadata['spatial']['slice_thickness'],
    'rows': metadata['image']['rows'],
    'manufacturer': metadata['equipment']['manufacturer'],

    # Full metadata JSON (for reference/compliance)
    'dicom_metadata': metadata,  # Everything
})
```

**Trade-offs Analysis:**

| Aspect | JSONField | Dedicated Columns |
|--------|-----------|-------------------|
| **Query Performance** | ❌ Slower (requires JSON functions) | ✅ Fast (indexed) |
| **Flexibility** | ✅ No migrations for new fields | ❌ Requires ALTER TABLE |
| **Type Safety** | ❌ Runtime validation only | ✅ Database-level constraints |
| **Storage** | ~Equal | ~Equal |
| **Indexing** | ⚠️ Partial (GIN indexes, MySQL 5.7+) | ✅ Standard B-tree |
| **Aggregations** | ❌ Complex/limited | ✅ Simple (SUM, AVG, etc.) |

**Querying JSONField** (MySQL/PostgreSQL):

```python
# PostgreSQL JSONField queries
DicomImage.objects.filter(
    dicom_metadata__patient_age__gte=65  # JSON path notation
)

# MySQL 5.7+ JSON functions
DicomImage.objects.filter(
    dicom_metadata__spatial__slice_thickness__gt=5.0
)
```

**Why not NoSQL (MongoDB) for DICOM?**

- Still need **relational data** (Patient → Study → Image hierarchy)
- Django ORM benefits (migrations, admin, serializers)
- ACID transactions critical for medical data
- JSONField gives "best of both worlds"

**Real-world use case:**

```python
# API returns both structured + raw metadata
{
  "id": 123,
  "instance_number": 1,
  "slice_thickness": 5.0,          // Dedicated column (fast filtering)
  "manufacturer": "GE Medical",     // Dedicated column
  "dicom_metadata": {               // Full JSON (reference)
    "patient_age": "045Y",
    "acquisition_datetime": "20240115123045",
    "protocol_name": "Brain Routine",
    // ... 100+ more tags
  }
}
```

**When I'd use pure JSON (no columns):**

- Audit logs (`AuditLog.details` field, line 283)
- Task results (`TaskStatus.result` field, line 354)
- Configuration/preferences (unstructured, rarely queried)

**When I'd use pure columns (no JSON):**

- Highly structured data (Patient demographics)
- Frequent filtering/sorting
- Data integrity critical

**HIPAA consideration:**

JSON fields still support:
- Database encryption
- Audit logging
- Backup/recovery
- Access controls

This demonstrates:
- **Pragmatic data modeling** (hybrid approach)
- **Performance awareness** (indexed columns for queries)
- **Domain knowledge** (DICOM complexity)
- **Database features** (modern JSON support)

---

### Q6: Explain select_related() and prefetch_related(). Where did you use them in your project and why?

**Answer:**

Both are Django ORM optimizations to **reduce database queries** (solve the N+1 problem), but they work differently.

**select_related() - SQL JOIN**

Used for **ForeignKey** and **OneToOne** relationships. Creates a SQL JOIN and fetches related objects in a single query.

**In my project** (`views.py:133`):

```python
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.select_related('hospital').all()
```

**Without select_related:**
```python
patients = Patient.objects.all()  # Query 1
for patient in patients:  # 100 patients
    print(patient.hospital.name)  # Query 2, 3, 4... 101 total queries! ❌
```

**With select_related:**
```python
patients = Patient.objects.select_related('hospital').all()  # 1 query with JOIN
for patient in patients:
    print(patient.hospital.name)  # No additional queries ✅
```

**Generated SQL:**
```sql
SELECT patient.*, hospital.*
FROM patient
INNER JOIN hospital ON patient.hospital_id = hospital.id;
```

**prefetch_related() - Separate Queries + Python JOIN**

Used for **ManyToMany** and **reverse ForeignKey** (one-to-many). Fetches related objects in separate queries, then joins in Python.

**In my project** (`views.py:261-262`):

```python
queryset = ImagingStudy.objects.select_related(
    'patient', 'patient__hospital'
).prefetch_related('images', 'diagnosis').all()
```

**Why prefetch_related for 'images'?**

`ImagingStudy → DicomImage` is a one-to-many relationship (one study has many images). Can't use JOIN because it would duplicate study data.

**Without prefetch_related:**
```python
studies = ImagingStudy.objects.all()  # Query 1
for study in studies:  # 50 studies
    images = study.images.all()  # Query 2, 3, 4... 51 total! ❌
```

**With prefetch_related:**
```python
studies = ImagingStudy.objects.prefetch_related('images').all()
# Query 1: SELECT * FROM imaging_study
# Query 2: SELECT * FROM dicom_image WHERE study_id IN (1,2,3...50)
# Total: 2 queries ✅
```

**Combining both** (`views.py:261-262`):

```python
ImagingStudy.objects.select_related(
    'patient',              # ForeignKey → JOIN
    'patient__hospital'     # Chained ForeignKey → JOIN
).prefetch_related(
    'images',               # Reverse FK → Separate query
    'diagnosis'             # OneToOne → Separate query (optional)
)
```

**Generated SQL:**
```sql
-- Query 1: Main query with JOINs
SELECT imaging_study.*, patient.*, hospital.*
FROM imaging_study
INNER JOIN patient ON imaging_study.patient_id = patient.id
INNER JOIN hospital ON patient.hospital_id = hospital.id;

-- Query 2: Prefetch images
SELECT * FROM dicom_image
WHERE study_id IN (1, 2, 3, ...);

-- Query 3: Prefetch diagnosis
SELECT * FROM diagnosis
WHERE study_id IN (1, 2, 3, ...);
```

**Real-world impact:**

API endpoint: `GET /api/studies/`

**Before optimization:**
- 1 query for studies
- 50 queries for patients (N)
- 50 queries for hospitals (N)
- 50 queries for images (N)
- 50 queries for diagnoses (N)
- **Total: 201 queries** 🔥

**After optimization:**
- 1 query (study + patient + hospital via JOINs)
- 1 query (all images)
- 1 query (all diagnoses)
- **Total: 3 queries** ✅

**Performance: 67x reduction in queries!**

**When to use each:**

| Relationship | Method | Why |
|-------------|--------|-----|
| ForeignKey (many-to-one) | `select_related()` | SQL JOIN efficient |
| OneToOneField | `select_related()` | SQL JOIN efficient |
| ManyToManyField | `prefetch_related()` | Avoids cartesian product |
| Reverse ForeignKey (one-to-many) | `prefetch_related()` | Avoids duplicates |

**Another example from serializers** (`serializers.py:76-79`):

```python
def get_recent_studies(self, obj):
    """Get 5 most recent studies"""
    recent = obj.imaging_studies.all()[:5]  # Could trigger N+1!
    return ImagingStudyListSerializer(recent, many=True).data
```

**Better approach:**
```python
queryset = Patient.objects.prefetch_related(
    Prefetch('imaging_studies',
             queryset=ImagingStudy.objects.order_by('-study_date')[:5])
).all()
```

**Debugging N+1 queries:**

```python
# settings.py (development)
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',  # Shows all SQL queries
        }
    }
}

# Or use Django Debug Toolbar
# Shows query count per page
```

**Common mistake:**

```python
# ❌ Wrong: Accessing prefetched data incorrectly
studies = ImagingStudy.objects.prefetch_related('images').all()
for study in studies:
    # This triggers new query, ignoring prefetch!
    images = study.images.filter(is_dicom=True)
```

```python
# ✅ Correct: Use Prefetch object for filtering
from django.db.models import Prefetch

studies = ImagingStudy.objects.prefetch_related(
    Prefetch('images',
             queryset=DicomImage.objects.filter(is_dicom=True))
)
```

This demonstrates:
- **Query optimization** expertise
- **Understanding of ORM internals**
- **Performance awareness**
- **Real-world problem solving** (N+1 queries)

---

### Q7: How do Django migrations work? What would you do if you had a migration conflict in production?

**Answer:**

Django migrations are **version control for your database schema**. They track and apply changes to your database structure.

**How migrations work:**

**1. Create models:**
```python
class Patient(models.Model):
    first_name = models.CharField(max_length=100)
```

**2. Generate migration:**
```bash
python manage.py makemigrations
# Creates: migrations/0001_initial.py
```

**3. Migration file structure:**
```python
class Migration(migrations.Migration):
    dependencies = [
        ('medical_imaging', '0000_previous_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='Patient',
            fields=[
                ('id', models.BigAutoField(primary_key=True)),
                ('first_name', models.CharField(max_length=100)),
            ],
        ),
    ]
```

**4. Apply migration:**
```bash
python manage.py migrate
# Executes SQL: CREATE TABLE patient ...
```

**Migration tracking:**

Django uses `django_migrations` table to track applied migrations:
```sql
SELECT * FROM django_migrations;
-- app | name | applied
-- medical_imaging | 0001_initial | 2024-01-15 10:30:00
```

**Common migration operations:**

**Adding a field:**
```python
# 1. Add to model
class Patient(models.Model):
    email = models.EmailField(blank=True)  # blank=True important!

# 2. Generate migration
python manage.py makemigrations

# 3. Review generated migration
# migrations/0002_patient_email.py
operations = [
    migrations.AddField(
        model_name='patient',
        name='email',
        field=models.EmailField(blank=True),
    ),
]

# 4. Apply
python manage.py migrate
```

**Renaming a field (risky!):**
```python
# ❌ Wrong: Django sees this as delete + create
class Patient(models.Model):
    # mrn = models.CharField(max_length=50)  # Old
    medical_record_number = models.CharField(max_length=50)  # New

# ✅ Correct: Use RenameField
operations = [
    migrations.RenameField(
        model_name='patient',
        old_name='mrn',
        new_name='medical_record_number',
    ),
]
```

**Migration conflict scenarios:**

**Scenario 1: Merge conflict (most common)**

Two developers create migrations with same number:
```
Branch A: 0005_add_patient_email.py
Branch B: 0005_add_study_status.py
```

**Solution:**
```bash
# 1. Merge both branches
git merge feature-branch

# 2. Django detects conflict
python manage.py makemigrations --merge
# Creates: 0006_merge_20240115_1030.py

# 3. Review merge migration
class Migration(migrations.Migration):
    dependencies = [
        ('medical_imaging', '0005_add_patient_email'),
        ('medical_imaging', '0005_add_study_status'),
    ]
    operations = []  # Usually empty

# 4. Test migrations
python manage.py migrate
```

**Scenario 2: Production migration conflict**

Production is on `0004`, but your local has `0005` and `0006`. Another developer deployed `0005_different` to production.

```
Local:      0004 → 0005_yours → 0006_yours
Production: 0004 → 0005_theirs
```

**Solution:**
```bash
# 1. Pull latest code
git pull origin main

# 2. Rebase your migrations
python manage.py makemigrations --merge

# 3. Create a new migration that combines changes
# If conflict is severe, may need to:
# - Delete your local 0005 and 0006
# - Pull production migrations
# - Recreate your model changes
# - Generate fresh migrations

# 4. Test thoroughly in staging
python manage.py migrate

# 5. Deploy to production
```

**Scenario 3: Data migration conflict**

Need to populate new field with data:

```python
# migrations/0007_populate_mrn.py
from django.db import migrations

def populate_mrn(apps, schema_editor):
    Patient = apps.get_model('medical_imaging', 'Patient')
    for patient in Patient.objects.all():
        if not patient.medical_record_number:
            patient.medical_record_number = f"MRN-{patient.id:06d}"
            patient.save()

def reverse_populate(apps, schema_editor):
    pass  # Optional: cleanup for rollback

class Migration(migrations.Migration):
    dependencies = [
        ('medical_imaging', '0006_patient_medical_record_number'),
    ]

    operations = [
        migrations.RunPython(populate_mrn, reverse_populate),
    ]
```

**Best practices:**

**1. Always review migrations before applying:**
```bash
python manage.py sqlmigrate medical_imaging 0005
# Shows actual SQL that will run
```

**2. Test migrations in staging first:**
```bash
# Never test migrations directly in production!
# Use staging environment identical to production
```

**3. Backup before major migrations:**
```bash
# PostgreSQL
pg_dump dbname > backup_before_migration.sql

# MySQL
mysqldump -u user -p dbname > backup.sql
```

**4. Use --fake for special cases:**
```bash
# If you manually applied changes
python manage.py migrate --fake medical_imaging 0005
```

**5. Squash old migrations:**
```bash
# Combine many migrations into one (after deployed)
python manage.py squashmigrations medical_imaging 0001 0050
```

**Rolling back migrations:**

```bash
# Rollback to specific migration
python manage.py migrate medical_imaging 0004

# Rollback all app migrations
python manage.py migrate medical_imaging zero

# Show migration status
python manage.py showmigrations
```

**Production migration strategy:**

**Zero-downtime deployment:**

```python
# Step 1: Add field as nullable
class Patient(models.Model):
    email = models.EmailField(null=True, blank=True)  # Nullable initially

# Deploy + Migrate

# Step 2: Populate data
# migrations/0008_populate_email.py
def populate_emails(apps, schema_editor):
    # Populate from external source
    pass

# Deploy + Migrate

# Step 3: Make field non-nullable (if needed)
class Patient(models.Model):
    email = models.EmailField()  # Now required

# Deploy + Migrate
```

**Common pitfalls:**

❌ **Adding non-nullable field without default to existing table**
```python
# This fails if table has data!
email = models.EmailField()  # No default, no null
```

✅ **Correct approach:**
```python
email = models.EmailField(default='', blank=True)
# Or use null=True temporarily, then populate, then remove null
```

❌ **Renaming field + table in same migration**
```python
# Too risky! Django may not handle correctly
```

✅ **Correct: Separate migrations**
```python
# Migration 1: Rename field
# Migration 2: Rename table (if needed)
```

This demonstrates:
- **Database schema management** knowledge
- **Production deployment** experience
- **Conflict resolution** skills
- **Risk mitigation** awareness

---

### Q8: Explain Django model validators. How did you use MinValueValidator in your DicomImage model?

**Answer:**

Django **validators** enforce **data integrity** at the model/form level—catching invalid data before it reaches the database.

**In my project** (`models.py:137-140`):

```python
instance_number = models.IntegerField(
    validators=[MinValueValidator(1)],
    help_text='Image sequence number in study'
)
```

**Why MinValueValidator(1)?**

✅ **Business rule**: DICOM instance numbers start at 1 (not 0)
✅ **Data integrity**: Prevents negative or zero instance numbers
✅ **Early validation**: Catches errors before database INSERT
✅ **Clear errors**: Returns meaningful error messages

**How validation works:**

```python
# Creating a DicomImage
image = DicomImage(
    study=study,
    instance_number=0,  # Invalid!
    image_file=file
)

# Validation happens on:
image.full_clean()  # Explicit validation
# Or
image.save()  # If you call full_clean() manually first
```

**Error message:**
```python
ValidationError: {
    'instance_number': ['Ensure this value is greater than or equal to 1.']
}
```

**Built-in validators:**

**1. MinValueValidator / MaxValueValidator**
```python
# From my project
age = models.IntegerField(
    validators=[
        MinValueValidator(0),
        MaxValueValidator(150)
    ]
)
```

**2. MinLengthValidator / MaxLengthValidator**
```python
medical_record_number = models.CharField(
    max_length=50,  # Built-in validation
    validators=[MinLengthValidator(5)]
)
```

**3. EmailValidator** (built-in with EmailField)
```python
email = models.EmailField()  # Auto-includes EmailValidator
```

**4. URLValidator** (built-in with URLField)
```python
website = models.URLField()  # Auto-includes URLValidator
```

**5. RegexValidator**
```python
from django.core.validators import RegexValidator

phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be in format: '+999999999'. Up to 15 digits allowed."
)

phone = models.CharField(
    max_length=20,
    validators=[phone_regex]
)
```

**Custom validators:**

**Example: Validate DICOM file extension**
```python
from django.core.exceptions import ValidationError

def validate_dicom_file(value):
    """Validate that uploaded file is a DICOM file"""
    if not value.name.endswith('.dcm'):
        raise ValidationError(
            'File must be a DICOM file (.dcm extension)',
            code='invalid_dicom'
        )

    # Optional: Check DICOM magic bytes
    value.seek(0)
    header = value.read(132)
    if header[128:132] != b'DICM':
        raise ValidationError(
            'File does not contain valid DICOM header',
            code='invalid_dicom_header'
        )
    value.seek(0)  # Reset file pointer

class DicomImage(models.Model):
    image_file = models.FileField(
        upload_to='dicom_image/%Y/%m/%d/',
        validators=[validate_dicom_file]
    )
```

**Example: Validate medical record number format**
```python
def validate_mrn_format(value):
    """Validate MRN format: MRN-XXXXXX"""
    if not value.startswith('MRN-'):
        raise ValidationError(
            'Medical record number must start with "MRN-"',
            code='invalid_mrn_prefix'
        )

    if len(value) != 10:  # MRN-XXXXXX = 10 chars
        raise ValidationError(
            'Medical record number must be exactly 10 characters',
            code='invalid_mrn_length'
        )

    suffix = value[4:]
    if not suffix.isdigit():
        raise ValidationError(
            'Medical record number suffix must be numeric',
            code='invalid_mrn_suffix'
        )

class Patient(models.Model):
    medical_record_number = models.CharField(
        max_length=50,
        unique=True,
        validators=[validate_mrn_format]
    )
```

**Validators vs. Database constraints:**

| Aspect | Validators | Database Constraints |
|--------|-----------|---------------------|
| **When** | Before save (Python) | During INSERT/UPDATE (SQL) |
| **Error handling** | Python exceptions | Database errors |
| **Performance** | Pre-validation (faster) | Last line of defense |
| **Portability** | Database-agnostic | Database-specific |
| **Examples** | RegexValidator | CHECK constraints |

**Best practice: Use both!**

```python
# Model-level validation
instance_number = models.IntegerField(
    validators=[MinValueValidator(1)]  # Python validation
)

# Database-level constraint (via migration)
class Meta:
    constraints = [
        models.CheckConstraint(
            check=models.Q(instance_number__gte=1),
            name='instance_number_positive'
        )
    ]
```

**Form vs Model validation:**

**Model validation:**
```python
# Only runs when explicitly called
image.full_clean()  # Must call this
image.save()
```

**Form validation** (DRF automatically calls it):
```python
# In Django REST Framework serializers
class DicomImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DicomImage
        fields = '__all__'

    def validate_instance_number(self, value):
        """Custom field-level validation"""
        if value < 1:
            raise serializers.ValidationError(
                "Instance number must be positive"
            )
        return value
```

**Real-world example from my project:**

In `serializers.py:210-214`, validating contact message:

```python
def validate_message(self, value):
    """Ensure message is not too short"""
    if len(value.strip()) < 10:
        raise serializers.ValidationError(
            "Message must be at least 10 characters long."
        )
    return value
```

**When to use validators:**

✅ **Business rules**: MRN format, age ranges, DICOM instance numbers
✅ **Data format**: Phone numbers, file types, URLs
✅ **Cross-field validation**: Start date < End date
✅ **External validation**: API calls, file content checks

❌ **Don't use for:**
- Simple type validation (use correct field type)
- Database uniqueness (use `unique=True`)
- Null checks (use `null=False`)

**Validator execution order:**

```python
1. Field-level validators (validators=[...])
2. Model.clean() method
3. Model.clean_<fieldname>() methods
4. unique/unique_together checks
5. Database save
6. Database constraints (CHECK, UNIQUE, FK)
```

**Custom clean() method:**

```python
from django.core.exceptions import ValidationError

class ImagingStudy(models.Model):
    study_date = models.DateTimeField()
    completion_date = models.DateTimeField(null=True, blank=True)

    def clean(self):
        """Cross-field validation"""
        super().clean()

        if self.completion_date and self.study_date:
            if self.completion_date < self.study_date:
                raise ValidationError({
                    'completion_date': 'Completion date cannot be before study date'
                })
```

This demonstrates:
- **Data validation** understanding
- **Data integrity** focus
- **Django best practices**
- **Real-world application** (medical data validation)

---

### Q9: What are Django signals? When would you use them vs overriding save()?

**Answer:**

Django **signals** allow **decoupled applications** to get notified when certain actions occur. They follow the **Observer pattern**.

**Common built-in signals:**

```python
# Model signals
pre_save          # Before model.save()
post_save         # After model.save()
pre_delete        # Before model.delete()
post_delete       # After model.delete()

# Request/response signals
request_started
request_finished
```

**Example use case - File cleanup on delete:**

```python
# medical_imaging/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import DicomImage

@receiver(post_delete, sender=DicomImage)
def delete_image_file(sender, instance, **kwargs):
    """Delete physical file when DicomImage is deleted"""
    if instance.image_file:
        # Delete from filesystem or S3
        instance.image_file.delete(save=False)
```

**Register signal:**
```python
# medical_imaging/apps.py
from django.apps import AppConfig

class MedicalImagingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'medical_imaging'

    def ready(self):
        import medical_imaging.signals  # noqa
```

**Signals vs overriding save():**

| Scenario | Use Signal | Use save() Override |
|----------|------------|---------------------|
| **Same app logic** | ❌ | ✅ Cleaner |
| **Cross-app logic** | ✅ Decoupled | ❌ Creates coupling |
| **Third-party models** | ✅ Only option | ❌ Can't modify |
| **Debugging** | ❌ Harder to trace | ✅ Explicit |
| **Performance** | ⚠️ Slight overhead | ✅ Faster |
| **Testing** | ⚠️ More complex | ✅ Simpler |

**When to use save() override:**

```python
class Patient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    medical_record_number = models.CharField(max_length=50, blank=True)

    def save(self, *args, **kwargs):
        # Generate MRN if not provided
        if not self.medical_record_number:
            self.medical_record_number = f"MRN-{uuid.uuid4().hex[:6].upper()}"

        # Always call super()
        super().save(*args, **kwargs)
```

**✅ Good for:**
- Auto-populating fields
- Data normalization (e.g., lowercase email)
- Simple validation
- Core model logic

**When to use signals:**

```python
@receiver(post_save, sender=ImagingStudy)
def create_audit_log(sender, instance, created, **kwargs):
    """Log study creation in AuditLog table"""
    if created:
        AuditLog.objects.create(
            resource_type='ImagingStudy',
            resource_id=instance.id,
            action='create'
        )
```

**✅ Good for:**
- Audit logging
- Cache invalidation
- Sending notifications
- Cross-app coordination
- File cleanup

**Real-world example - Automatic PDF cleanup:**

```python
@receiver(post_delete, sender=PatientReport)
def cleanup_pdf_file(sender, instance, **kwargs):
    """Delete PDF file from storage when report is deleted"""
    if instance.pdf_file:
        try:
            # Works with local filesystem and S3
            storage = instance.pdf_file.storage
            if storage.exists(instance.pdf_file.name):
                storage.delete(instance.pdf_file.name)
        except Exception as e:
            logger.error(f"Failed to delete PDF file: {e}")
```

**Signal gotchas:**

**1. Signals fire on bulk operations differently:**
```python
# ❌ post_save NOT fired for each instance
Patient.objects.bulk_create([patient1, patient2, patient3])

# ✅ post_save fired for each
for patient in patients:
    patient.save()
```

**2. Signals can cause infinite loops:**
```python
# ❌ DANGER: Infinite recursion!
@receiver(post_save, sender=Patient)
def update_patient(sender, instance, **kwargs):
    instance.updated_at = timezone.now()
    instance.save()  # Triggers post_save again!
```

**✅ Solution:**
```python
@receiver(post_save, sender=Patient)
def update_patient(sender, instance, created, **kwargs):
    if created:  # Only on creation
        # Do something
        pass
```

Or use `update()`:
```python
@receiver(post_save, sender=Patient)
def update_patient(sender, instance, **kwargs):
    # update() doesn't trigger signals
    Patient.objects.filter(pk=instance.pk).update(
        updated_at=timezone.now()
    )
```

**3. Testing with signals:**
```python
# Disable signals in tests if needed
from django.test import override_settings

@override_settings(SIGNAL_HANDLERS_DISABLED=True)
def test_patient_creation():
    # Signals won't fire
    patient = Patient.objects.create(...)
```

**Custom signals:**

```python
# medical_imaging/signals.py
from django.dispatch import Signal

# Define custom signal
dicom_processed = Signal()  # Can pass arguments

# Send signal
dicom_processed.send(
    sender=DicomImage,
    instance=image,
    metadata=dicom_metadata
)

# Receive signal
@receiver(dicom_processed)
def handle_dicom_processed(sender, instance, metadata, **kwargs):
    # Update statistics, cache, etc.
    pass
```

**Performance consideration:**

Signals add overhead—each save() might trigger multiple signal handlers:

```python
patient.save()
# Triggers:
# 1. pre_save signal
# 2. Actual database INSERT
# 3. post_save signal
# 4. Any custom signals
```

For bulk operations, prefer `bulk_create()` or direct SQL.

**My recommendation:**

✅ **Use save() override** for:
- Core model behavior
- Field auto-population
- Simple validation
- Performance-critical code

✅ **Use signals** for:
- Cross-app communication
- Audit trails
- Notifications
- File cleanup
- Cache invalidation
- Third-party model hooks

This demonstrates:
- **Design pattern** knowledge (Observer pattern)
- **Django architecture** understanding
- **Performance** awareness
- **Practical trade-offs**

---

### Q10: What's the difference between Django Manager and QuerySet? When would you create a custom manager?

**Answer:**

**Manager** = Interface for database queries (attached to model class)
**QuerySet** = Lazy-evaluated database query result (returned by manager methods)

**Default manager:**

```python
Patient.objects  # This is a Manager
Patient.objects.all()  # This returns a QuerySet
Patient.objects.filter(gender='M')  # This returns a QuerySet
```

**Key differences:**

| Manager | QuerySet |
|---------|----------|
| Attached to model class | Returned by manager methods |
| `Patient.objects` | `Patient.objects.all()` |
| Provides initial queries | Chainable, filterable |
| One per model (default) | Many instances |
| Not lazy | Lazy (evaluates on access) |

**Custom Manager - When and Why:**

**Use case 1: Common filters**

```python
class PublishedStudyManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='completed')

class ImagingStudy(models.Model):
    # Fields...
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    # Default manager
    objects = models.Manager()

    # Custom manager for published studies
    published = PublishedStudyManager()

# Usage:
ImagingStudy.objects.all()  # All studies
ImagingStudy.published.all()  # Only completed studies
```

**Use case 2: Common query methods**

```python
class PatientManager(models.Manager):
    def by_hospital(self, hospital_id):
        return self.filter(hospital_id=hospital_id)

    def adults_only(self):
        from datetime import date
        eighteen_years_ago = date.today().replace(year=date.today().year - 18)
        return self.filter(date_of_birth__lte=eighteen_years_ago)

    def with_recent_studies(self):
        return self.prefetch_related(
            Prefetch('imaging_studies',
                     queryset=ImagingStudy.objects.order_by('-study_date')[:5])
        )

class Patient(models.Model):
    # Fields...
    objects = PatientManager()

# Usage:
Patient.objects.by_hospital(5).adults_only()
Patient.objects.with_recent_studies()
```

**Use case 3: Soft deletes**

```python
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

class ImagingStudy(models.Model):
    # Fields...
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Default: only non-deleted
    objects = SoftDeleteManager()

    # All records (including deleted)
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        # Soft delete
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self):
        # Actual delete
        super().delete()

# Usage:
ImagingStudy.objects.all()  # Only non-deleted
ImagingStudy.all_objects.all()  # Including deleted
```

**QuerySet methods:**

```python
# QuerySets are lazy and chainable
qs = Patient.objects.filter(gender='M')  # Not executed yet
qs = qs.filter(hospital_id=5)  # Still not executed
qs = qs.order_by('last_name')  # Still not executed

# Executed when:
list(qs)  # Conversion to list
for p in qs:  # Iteration
qs[0]  # Indexing
len(qs)  # Length check
bool(qs)  # Boolean evaluation
```

**Custom QuerySet:**

```python
class ImagingStudyQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')

    def by_modality(self, modality):
        return self.filter(modality=modality)

    def recent(self, days=30):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

class ImagingStudyManager(models.Manager):
    def get_queryset(self):
        return ImagingStudyQuerySet(self.model, using=self._db)

    # Proxy methods for convenience
    def pending(self):
        return self.get_queryset().pending()

    def by_modality(self, modality):
        return self.get_queryset().by_modality(modality)

class ImagingStudy(models.Model):
    # Fields...
    objects = ImagingStudyManager()

# Usage (chainable!):
ImagingStudy.objects.pending().by_modality('CT').recent(7)
```

**Better approach - QuerySet.as_manager():**

```python
class ImagingStudyQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status='pending')

    def by_modality(self, modality):
        return self.filter(modality=modality)

class ImagingStudy(models.Model):
    # Fields...
    objects = ImagingStudyQuerySet.as_manager()

# Same usage, less code!
ImagingStudy.objects.pending().by_modality('CT')
```

This demonstrates:
- **Django ORM** depth
- **Code reusability**
- **Clean API design**

---

### Q11: Explain Django's Meta class options. Which ones did you use in your models?

**Answer:**

The `Meta` class provides **model-level metadata** - configuration that isn't field definitions.

**Common Meta options I used:**

**1. ordering** (`models.py:109`):
```python
class ImagingStudy(models.Model):
    class Meta:
        ordering = ['-study_date']  # Most recent first
```
Default sort order for QuerySets: `ImagingStudy.objects.all()` automatically sorted.

**2. verbose_name_plural** (`models.py:110, 248`):
```python
class Meta:
    verbose_name_plural = 'Imaging Studies'  # Not "Imaging Studys"
```
Displays correctly in Django admin.

**3. indexes** (`models.py:111-118`):
```python
class Meta:
    indexes = [
        models.Index(fields=['patient', '-study_date']),
        models.Index(fields=['status']),
    ]
```
Database performance optimization (covered in Q2).

**4. unique_together** (`models.py:206`):
```python
class Meta:
    unique_together = ['study', 'instance_number']
```
Prevents duplicate DICOM instances within a study.

**5. constraints** (modern approach):
```python
class Meta:
    constraints = [
        models.CheckConstraint(
            check=models.Q(instance_number__gte=1),
            name='instance_number_positive'
        ),
        models.UniqueConstraint(
            fields=['study', 'instance_number'],
            name='unique_study_instance'
        )
    ]
```

**Other important Meta options:**

**db_table** - Custom table name:
```python
class Meta:
    db_table = 'imaging_studies'  # Instead of myapp_imagingstudy
```

**abstract** - Base model (not a table):
```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # No database table created

class Patient(TimeStampedModel):  # Inherits fields
    # ...
```

**permissions** - Custom permissions:
```python
class Meta:
    permissions = [
        ('can_approve_diagnosis', 'Can approve diagnosis'),
        ('can_view_phi', 'Can view protected health information'),
    ]
```

**default_related_name**:
```python
class Meta:
    default_related_name = 'studies'
# Now: patient.studies.all() instead of patient.imagingstudy_set.all()
```

**get_latest_by**:
```python
class Meta:
    get_latest_by = 'study_date'

# Usage:
latest_study = ImagingStudy.objects.latest()  # Gets most recent
```

**managed** - Django controls table:
```python
class Meta:
    managed = False  # Django won't create/modify table (legacy DB)
```

---

### Q12: What's the difference between null=True and blank=True in Django models?

**Answer:**

**null=True** = **Database-level** (allows NULL in database)
**blank=True** = **Validation-level** (allows empty string in forms)

**Key differences:**

| Aspect | `null=True` | `blank=True` |
|--------|-------------|--------------|
| **Level** | Database | Django validation |
| **Affects** | SQL column | Forms/serializers |
| **For strings** | ❌ Usually wrong | ✅ Use this |
| **For numbers/dates** | ✅ Use this | Optional |

**Examples from my project:**

**1. Optional string field** (`models.py:50-51`):
```python
phone = models.CharField(max_length=20, blank=True)  # No null=True!
email = models.EmailField(blank=True)
```
**Why not null=True?** Django convention: empty strings, not NULL for text.

**2. Optional foreign key** (`models.py:233-238`):
```python
radiologist = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,  # Must allow NULL
    blank=True,  # Optional in forms
    related_name='diagnoses'
)
```
**Why both?** FK requires `null=True` for NULL database value, `blank=True` for form validation.

**3. Optional number field** (`models.py:145-149`):
```python
slice_thickness = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    null=True,    # Allows NULL in DB
    blank=True,   # Optional in forms
)
```
**Why both?** Numbers should use NULL (not 0) to represent "no value".

**4. Required field (default)**:
```python
first_name = models.CharField(max_length=100)
# No null, no blank = required everywhere
```

**Decision tree:**

```
Is field required?
├─ YES → No null, no blank
└─ NO → Is it a string field (CharField, TextField, EmailField)?
    ├─ YES → blank=True only
    └─ NO → null=True, blank=True
```

**Database reality:**

**CharField with blank=True:**
```python
phone = models.CharField(max_length=20, blank=True)
```
SQL:
```sql
phone VARCHAR(20) NOT NULL DEFAULT ''
-- Empty = '' not NULL
```

**CharField with null=True:** (bad practice!)
```python
phone = models.CharField(max_length=20, null=True, blank=True)
```
SQL:
```sql
phone VARCHAR(20) NULL
-- Two "empty" states: NULL and ''  ❌ Confusing!
```

**Why this matters:**
```python
# Bad: Two ways to represent "no phone"
Patient.objects.filter(phone='')  # Empty string
Patient.objects.filter(phone__isnull=True)  # NULL

# Good: One way
Patient.objects.filter(phone='')  # Only this
```

**Exceptions - When to use null=True on strings:**

1. **Must distinguish "unknown" from "intentionally blank"**
2. **Legacy database compatibility**
3. **Specific business requirement**

This demonstrates:
- **Django conventions** understanding
- **Database design** knowledge
- **Data consistency** awareness

---

## SQL Fundamentals

### Q13: Explain different types of SQL JOINs with examples from your medical imaging database.

**Answer:**

SQL JOINs combine rows from two or more tables based on related columns.

**Database schema context:**
```
Hospital (id, name)
    ↓
Patient (id, first_name, last_name, hospital_id)
    ↓
ImagingStudy (id, study_date, modality, patient_id)
    ↓
DicomImage (id, image_file, instance_number, study_id)
```

**1. INNER JOIN** (most common)

Returns only rows with matches in BOTH tables.

```sql
-- Get patients with their hospital names
SELECT
    p.id,
    p.first_name,
    p.last_name,
    h.name AS hospital_name
FROM patient p
INNER JOIN hospital h ON p.hospital_id = h.id;
```

**Result:** Only patients that have a valid hospital.
**Excludes:** Orphaned patients (if hospital_id is NULL or invalid).

**Django ORM equivalent:**
```python
Patient.objects.select_related('hospital')
```

**2. LEFT JOIN (LEFT OUTER JOIN)**

Returns ALL rows from left table + matching rows from right table.

```sql
-- Get all studies with diagnoses (if they exist)
SELECT
    s.id,
    s.study_date,
    s.modality,
    d.findings,
    d.severity
FROM imaging_study s
LEFT JOIN diagnosis d ON s.id = d.study_id
ORDER BY s.study_date DESC;
```

**Result:** ALL studies, with diagnosis info if available (NULL if no diagnosis).

**Use case:** "Show all CT scans, including those not yet diagnosed"

**Django ORM:**
```python
ImagingStudy.objects.select_related('diagnosis')
# Django automatically does LEFT JOIN for nullable FKs
```

**3. RIGHT JOIN (RIGHT OUTER JOIN)**

Returns ALL rows from right table + matching rows from left table.

```sql
-- Get all hospitals and their patient count (including hospitals with 0 patients)
SELECT
    h.id,
    h.name,
    COUNT(p.id) AS patient_count
FROM patient p
RIGHT JOIN hospital h ON p.hospital_id = h.id
GROUP BY h.id, h.name;
```

**Result:** ALL hospitals, even those with no patients (count = 0).

**Note:** In MySQL/PostgreSQL, can rewrite as LEFT JOIN by swapping tables.

**4. FULL OUTER JOIN**

Returns ALL rows from BOTH tables (MySQL doesn't support natively).

```sql
-- PostgreSQL syntax
SELECT *
FROM table1 t1
FULL OUTER JOIN table2 t2 ON t1.id = t2.foreign_id;
```

**MySQL workaround:**
```sql
SELECT * FROM table1 LEFT JOIN table2 ON ...
UNION
SELECT * FROM table1 RIGHT JOIN table2 ON ...;
```

**5. CROSS JOIN (Cartesian Product)**

Returns ALL combinations of rows from both tables.

```sql
-- Rarely used, but example: All possible modality/body-part combinations
SELECT
    m.modality,
    b.body_part
FROM (SELECT DISTINCT modality FROM imaging_study) m
CROSS JOIN (SELECT DISTINCT body_part FROM imaging_study) b;
```

**Result:** Every modality paired with every body part.

**6. SELF JOIN**

Joining a table to itself.

```sql
-- Find patients from the same hospital
SELECT
    p1.first_name AS patient1,
    p2.first_name AS patient2,
    h.name AS hospital
FROM patient p1
INNER JOIN patient p2 ON p1.hospital_id = p2.hospital_id
INNER JOIN hospital h ON p1.hospital_id = h.id
WHERE p1.id < p2.id  -- Avoid duplicates
ORDER BY h.name;
```

**Real-world examples from my project:**

**Example 1: Patient with hospital and study count**
```sql
SELECT
    p.id,
    p.first_name,
    p.last_name,
    h.name AS hospital_name,
    COUNT(s.id) AS study_count
FROM patient p
INNER JOIN hospital h ON p.hospital_id = h.id
LEFT JOIN imaging_study s ON p.id = s.patient_id
GROUP BY p.id, p.first_name, p.last_name, h.name
ORDER BY study_count DESC;
```

**Example 2: Studies with image count**
```sql
SELECT
    s.id,
    s.study_date,
    s.modality,
    p.first_name || ' ' || p.last_name AS patient_name,
    COUNT(img.id) AS image_count
FROM imaging_study s
INNER JOIN patient p ON s.patient_id = p.id
LEFT JOIN dicom_image img ON s.id = img.study_id
GROUP BY s.id, s.study_date, s.modality, patient_name
HAVING COUNT(img.id) > 0;
```

**Example 3: Recent studies with diagnosis**
```sql
SELECT
    s.id,
    s.study_date,
    s.modality,
    p.medical_record_number,
    CASE
        WHEN d.id IS NOT NULL THEN 'Diagnosed'
        ELSE 'Pending'
    END AS status,
    d.severity
FROM imaging_study s
INNER JOIN patient p ON s.patient_id = p.id
LEFT JOIN diagnosis d ON s.id = d.study_id
WHERE s.study_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY s.study_date DESC;
```

**JOIN performance tips:**

✅ **Always index foreign key columns**
```sql
CREATE INDEX idx_patient_hospital ON patient(hospital_id);
CREATE INDEX idx_study_patient ON imaging_study(patient_id);
```

✅ **Use appropriate JOIN type**
- INNER JOIN when you only want matches
- LEFT JOIN when you need all from left table

❌ **Avoid:**
- Too many JOINs in one query (>5-6)
- JOINs without indexes
- SELECT * with JOINs (specify columns)

**Visual representation:**

```
INNER JOIN:     ┌───┐      (Only overlap)
                │ ∩ │
                └───┘

LEFT JOIN:   ┌─────┐┌───┐  (All left + overlap)
             │  A  ││ ∩ │
             └─────┘└───┘

RIGHT JOIN:     ┌───┐┌─────┐  (All right + overlap)
                │ ∩ ││  B  │
                └───┘└─────┘

FULL OUTER:  ┌─────┐┌───┐┌─────┐  (Everything)
             │  A  ││ ∩ ││  B  │
             └─────┘└───┘└─────┘
```

This demonstrates:
- **SQL fundamentals** mastery
- **Database query** optimization
- **Real-world application** in medical domain

---

### Q14: Explain GROUP BY, HAVING, and aggregate functions. Write a query to find hospitals with more than 10 patients.

**Answer:**

**GROUP BY** groups rows that have the same values. Used with **aggregate functions** (COUNT, SUM, AVG, MAX, MIN).

**HAVING** filters groups (like WHERE filters rows).

**Aggregate Functions:**

```sql
COUNT(*)        -- Count all rows
COUNT(column)   -- Count non-NULL values
SUM(column)     -- Sum numeric values
AVG(column)     -- Average
MAX(column)     -- Maximum value
MIN(column)     -- Minimum value
```

**Example 1: Hospitals with more than 10 patients**

```sql
SELECT
    h.id,
    h.name,
    COUNT(p.id) AS patient_count
FROM hospital h
LEFT JOIN patient p ON h.id = p.hospital_id
GROUP BY h.id, h.name
HAVING COUNT(p.id) > 10
ORDER BY patient_count DESC;
```

**Breakdown:**
1. `LEFT JOIN` - Include hospitals with 0 patients
2. `GROUP BY h.id, h.name` - Group by hospital
3. `COUNT(p.id)` - Count patients per hospital
4. `HAVING COUNT(p.id) > 10` - Filter groups (not individual rows)
5. `ORDER BY` - Sort by count

**Example 2: Patient demographics by hospital**

```sql
SELECT
    h.name AS hospital_name,
    COUNT(*) AS total_patients,
    COUNT(CASE WHEN p.gender = 'M' THEN 1 END) AS male_count,
    COUNT(CASE WHEN p.gender = 'F' THEN 1 END) AS female_count,
    AVG(YEAR(CURDATE()) - YEAR(p.date_of_birth)) AS avg_age
FROM hospital h
INNER JOIN patient p ON h.id = p.hospital_id
GROUP BY h.id, h.name
HAVING total_patients >= 5
ORDER BY total_patients DESC;
```

**Example 3: Study statistics by modality**

```sql
SELECT
    modality,
    COUNT(*) AS study_count,
    COUNT(DISTINCT patient_id) AS unique_patients,
    MIN(study_date) AS earliest_study,
    MAX(study_date) AS latest_study
FROM imaging_study
WHERE study_date >= '2024-01-01'
GROUP BY modality
ORDER BY study_count DESC;
```

**Example 4: Patients with multiple studies**

```sql
SELECT
    p.id,
    p.medical_record_number,
    p.first_name,
    p.last_name,
    COUNT(s.id) AS study_count
FROM patient p
INNER JOIN imaging_study s ON p.id = s.patient_id
GROUP BY p.id, p.medical_record_number, p.first_name, p.last_name
HAVING COUNT(s.id) > 1
ORDER BY study_count DESC;
```

**WHERE vs HAVING:**

```sql
-- ✅ Correct: Filter before grouping
SELECT
    hospital_id,
    COUNT(*) AS patient_count
FROM patient
WHERE created_at >= '2024-01-01'  -- Filter ROWS
GROUP BY hospital_id
HAVING COUNT(*) > 5;               -- Filter GROUPS

-- ❌ Wrong: Can't use aggregate in WHERE
SELECT hospital_id, COUNT(*) AS patient_count
FROM patient
WHERE COUNT(*) > 5  -- ERROR! Can't use aggregate in WHERE
GROUP BY hospital_id;
```

**Execution order:**

```
1. FROM       - Get tables
2. WHERE      - Filter rows
3. GROUP BY   - Group rows
4. HAVING     - Filter groups
5. SELECT     - Calculate aggregates
6. ORDER BY   - Sort results
7. LIMIT      - Limit rows
```

**Complex example: Monthly study volume**

```sql
SELECT
    DATE_FORMAT(study_date, '%Y-%m') AS month,
    modality,
    COUNT(*) AS study_count,
    COUNT(DISTINCT patient_id) AS unique_patients,
    AVG(image_count) AS avg_images_per_study
FROM (
    SELECT
        s.study_date,
        s.modality,
        s.patient_id,
        COUNT(img.id) AS image_count
    FROM imaging_study s
    LEFT JOIN dicom_image img ON s.id = img.study_id
    GROUP BY s.id, s.study_date, s.modality, s.patient_id
) AS study_with_counts
GROUP BY month, modality
HAVING study_count > 10
ORDER BY month DESC, study_count DESC;
```

**Django ORM equivalent:**

```python
from django.db.models import Count, Avg, Q

# Hospitals with more than 10 patients
Hospital.objects.annotate(
    patient_count=Count('patients')
).filter(
    patient_count__gt=10
).order_by('-patient_count')

# Study count by modality
ImagingStudy.objects.values('modality').annotate(
    count=Count('id'),
    unique_patients=Count('patient', distinct=True)
).order_by('-count')
```

**Common pitfalls:**

❌ **Forgetting to include non-aggregated columns in GROUP BY**
```sql
-- MySQL 5.7+ strict mode ERROR
SELECT hospital_id, name, COUNT(*)
FROM patient
GROUP BY hospital_id;  -- Must include 'name' in GROUP BY
```

✅ **Correct:**
```sql
SELECT hospital_id, name, COUNT(*)
FROM patient
GROUP BY hospital_id, name;
```

❌ **Using alias in HAVING (database-dependent)**
```sql
-- May not work in all databases
SELECT COUNT(*) AS cnt
FROM patient
GROUP BY hospital_id
HAVING cnt > 10;  -- Use COUNT(*) instead
```

This demonstrates:
- **SQL aggregation** mastery
- **Data analysis** skills
- **Query optimization** understanding

---

### Q15: What are database indexes? How do they work and when should you use them?

**Answer:**

**Indexes** are data structures that improve query performance by allowing faster data retrieval—like a book's index helps find pages quickly.

**How indexes work:**

Think of a phone book:
- **Without index**: Scan every page to find "Smith, John" (full table scan - O(n))
- **With index**: Jump directly to "S" section (index lookup - O(log n))

**B-Tree Index (most common):**

```
                    [50]
                   /    \
             [25]          [75]
            /    \        /    \
        [10,20] [30,40] [60,70] [80,90]
```

Allows:
- Fast lookups: O(log n)
- Range queries: WHERE age BETWEEN 18 AND 65
- Sorted results: ORDER BY

**Types of indexes:**

**1. Single-column index:**
```sql
CREATE INDEX idx_patient_mrn ON patient(medical_record_number);
```

**Use for:** Frequent WHERE/JOIN conditions on single column

**2. Composite (multi-column) index:**
```sql
CREATE INDEX idx_patient_hospital_lastname
ON patient(hospital_id, last_name);
```

**Use for:** Queries filtering by multiple columns
```sql
-- ✅ Uses index
SELECT * FROM patient
WHERE hospital_id = 5 AND last_name = 'Smith';

-- ✅ Uses index (leftmost prefix)
SELECT * FROM patient WHERE hospital_id = 5;

-- ❌ Doesn't use index (skips leftmost column)
SELECT * FROM patient WHERE last_name = 'Smith';
```

**3. Unique index:**
```sql
CREATE UNIQUE INDEX idx_patient_mrn_unique
ON patient(medical_record_number);
```

Enforces uniqueness + provides index.

**4. Full-text index:**
```sql
CREATE FULLTEXT INDEX idx_diagnosis_findings
ON diagnosis(findings, impression);

-- Usage
SELECT * FROM diagnosis
WHERE MATCH(findings, impression) AGAINST('tumor malignant');
```

**Use for:** Text search queries

**5. Covering index:**
```sql
CREATE INDEX idx_study_covering
ON imaging_study(patient_id, study_date, modality);
```

Includes all columns needed by query—no table access required.

```sql
-- ✅ Can be satisfied entirely by index
SELECT patient_id, study_date, modality
FROM imaging_study
WHERE patient_id = 100;
```

**When to create indexes:**

✅ **CREATE index for:**
- Primary keys (auto-indexed)
- Foreign keys (Django doesn't auto-index!)
- Columns in WHERE clauses
- Columns in JOIN conditions
- Columns in ORDER BY
- Columns frequently searched

❌ **DON'T index:**
- Small tables (<1000 rows)
- Columns rarely used in queries
- Columns with low cardinality (e.g., gender with 2-3 values)
- Tables with frequent INSERT/UPDATE/DELETE

**Examples from my project:**

**Patient table indexes:**
```sql
-- Single column - unique lookups
CREATE INDEX idx_patient_mrn ON patient(medical_record_number);

-- Composite - hospital patient list sorted by name
CREATE INDEX idx_patient_hospital_name
ON patient(hospital_id, last_name, first_name);

-- Date-based queries
CREATE INDEX idx_patient_created ON patient(created_at);

-- Email lookups (patient portal login)
CREATE INDEX idx_patient_email ON patient(email);
```

**ImagingStudy table indexes:**
```sql
-- Patient's study history (most common query)
CREATE INDEX idx_study_patient_date
ON imaging_study(patient_id, study_date DESC);

-- Filter by modality and date
CREATE INDEX idx_study_modality_date
ON imaging_study(modality, study_date DESC);

-- Pending studies dashboard
CREATE INDEX idx_study_status_date
ON imaging_study(status, study_date DESC);
```

**Viewing indexes:**

```sql
-- MySQL
SHOW INDEX FROM patient;

-- PostgreSQL
\d patient

-- Check if query uses index
EXPLAIN SELECT * FROM patient WHERE medical_record_number = 'MRN-001';
```

**EXPLAIN output:**

```sql
EXPLAIN SELECT * FROM patient WHERE hospital_id = 5;

-- Good: Using index
+----+-------------+---------+------+---------------+------+---------+-------+------+-------+
| id | select_type | table   | type | possible_keys | key  | key_len | ref   | rows | Extra |
+----+-------------+---------+------+---------------+------+---------+-------+------+-------+
|  1 | SIMPLE      | patient | ref  | idx_hospital  | idx  | 4       | const |   50 | NULL  |
+----+-------------+---------+------+---------------+------+---------+-------+------+-------+

-- Bad: Full table scan
+----+-------------+---------+------+---------------+------+---------+------+-------+-------------+
| id | select_type | table   | type | possible_keys | key  | key_len | ref  | rows  | Extra       |
+----+-------------+---------+------+---------------+------+---------+------+-------+-------------+
|  1 | SIMPLE      | patient | ALL  | NULL          | NULL | NULL    | NULL | 10000 | Using where |
+----+-------------+---------+------+---------------+------+---------+------+-------+-------------+
```

**Index maintenance:**

```sql
-- Rebuild fragmented index (MySQL)
OPTIMIZE TABLE patient;

-- Rebuild index (PostgreSQL)
REINDEX INDEX idx_patient_hospital_name;

-- Drop unused index
DROP INDEX idx_old_unused ON patient;
```

**Index size considerations:**

```sql
-- Check index sizes (MySQL)
SELECT
    table_name,
    index_name,
    ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
FROM mysql.innodb_index_stats
WHERE database_name = 'medical_imaging'
ORDER BY size_mb DESC;
```

**Trade-offs:**

| Aspect | Benefit | Cost |
|--------|---------|------|
| **SELECT** | ✅ Much faster | - |
| **INSERT** | - | ❌ Slower (update index) |
| **UPDATE** | - | ❌ Slower (if indexed columns change) |
| **DELETE** | - | ❌ Slower (update index) |
| **Storage** | - | ❌ 10-30% more disk space |

**Real-world impact:**

**Before index on `imaging_study(patient_id, study_date)`:**
```sql
SELECT * FROM imaging_study
WHERE patient_id = 100
ORDER BY study_date DESC;
-- Full table scan: 2.5 seconds (1M rows)
```

**After index:**
```sql
-- Same query
-- Index seek: 0.003 seconds (800x faster!)
```

**Best practices:**

1. **Profile before indexing** - Use EXPLAIN to find slow queries
2. **Index foreign keys** - Django doesn't do this automatically
3. **Composite index column order** - Most selective first
4. **Monitor index usage** - Remove unused indexes
5. **Limit indexes** - Too many slow down writes

**Django index creation:**

```python
class Patient(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['hospital', 'last_name']),
            models.Index(fields=['medical_record_number']),
        ]
```

This demonstrates:
- **Database performance** expertise
- **Index strategy** understanding
- **Trade-off analysis** skills

---

### Q16: What are database transactions? Explain ACID properties with an example.

**Answer:**

A **transaction** is a sequence of database operations that must be executed as a single unit—either all succeed or all fail.

**ACID Properties:**

**A - Atomicity** (All or Nothing)

Either all operations in a transaction complete, or none do.

```sql
START TRANSACTION;

-- Transfer patient from Hospital A to Hospital B
UPDATE patient SET hospital_id = 2 WHERE id = 100;
INSERT INTO audit_log (action, resource_type, resource_id)
VALUES ('transfer', 'patient', 100);

COMMIT;  -- Both succeed

-- If INSERT fails, UPDATE is rolled back automatically
```

**Django example:**
```python
from django.db import transaction

try:
    with transaction.atomic():
        patient.hospital_id = new_hospital.id
        patient.save()

        AuditLog.objects.create(
            action='transfer',
            resource_type='patient',
            resource_id=patient.id
        )
        # Both saved or both rolled back
except Exception as e:
    # Transaction automatically rolled back
    logger.error(f"Transfer failed: {e}")
```

**C - Consistency** (Valid State to Valid State)

Transaction moves database from one valid state to another—maintains data integrity rules.

```sql
-- ❌ This violates consistency
START TRANSACTION;
UPDATE patient SET hospital_id = 999;  -- Hospital doesn't exist!
COMMIT;  -- Fails due to foreign key constraint

-- ✅ This maintains consistency
START TRANSACTION;
UPDATE patient SET hospital_id = 2;  -- Valid hospital
COMMIT;  -- Success
```

**I - Isolation** (Transactions don't interfere)

Concurrent transactions don't affect each other's results.

**Isolation levels:**

```sql
-- 1. READ UNCOMMITTED (lowest isolation, dirty reads possible)
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 2. READ COMMITTED (prevents dirty reads)
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- 3. REPEATABLE READ (MySQL default, prevents non-repeatable reads)
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;

-- 4. SERIALIZABLE (highest isolation, slowest)
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

**Example problem without isolation:**
```sql
-- Transaction A
SELECT COUNT(*) FROM patient WHERE hospital_id = 1;  -- Returns 100

-- Transaction B (concurrent)
INSERT INTO patient (hospital_id, ...) VALUES (1, ...);
COMMIT;

-- Transaction A (continued)
SELECT COUNT(*) FROM patient WHERE hospital_id = 1;  -- Returns 101!
-- Different result in same transaction! (non-repeatable read)
```

**D - Durability** (Persists after commit)

Once committed, changes are permanent (even if system crashes).

```sql
START TRANSACTION;
INSERT INTO patient (...) VALUES (...);
COMMIT;  -- Data written to disk, survives power failure
```

**Real-world medical imaging example:**

**Creating imaging study with images:**
```python
@transaction.atomic
def create_study_with_images(patient_id, study_data, image_files):
    """
    Create study and all images atomically
    If any image fails, entire study creation is rolled back
    """
    # Create study
    study = ImagingStudy.objects.create(
        patient_id=patient_id,
        **study_data
    )

    # Create all images
    for idx, image_file in enumerate(image_files, 1):
        DicomImage.objects.create(
            study=study,
            image_file=image_file,
            instance_number=idx
        )

    # Create audit log
    AuditLog.objects.create(
        action='create',
        resource_type='ImagingStudy',
        resource_id=study.id
    )

    # All succeed or all rolled back
    return study
```

**Transaction commands:**

```sql
-- MySQL/PostgreSQL
START TRANSACTION;  -- or BEGIN;
-- ... SQL statements ...
COMMIT;  -- Save changes

-- or
ROLLBACK;  -- Undo changes

-- Savepoints (partial rollback)
START TRANSACTION;
INSERT INTO patient (...);
SAVEPOINT sp1;
UPDATE patient SET ...;
ROLLBACK TO sp1;  -- Undo UPDATE, keep INSERT
COMMIT;
```

**Django transaction decorators:**

```python
# Function-level transaction
@transaction.atomic
def transfer_patient(patient_id, new_hospital_id):
    patient = Patient.objects.get(id=patient_id)
    patient.hospital_id = new_hospital_id
    patient.save()
    # ... more operations
    # All succeed or all rolled back

# Context manager (more control)
def process_diagnosis(study_id, diagnosis_data):
    study = ImagingStudy.objects.get(id=study_id)

    with transaction.atomic():
        diagnosis = Diagnosis.objects.create(
            study=study,
            **diagnosis_data
        )
        study.status = 'completed'
        study.save()
```

**Nested transactions:**

```python
@transaction.atomic  # Outer transaction
def process_bulk_studies(study_ids):
    for study_id in study_ids:
        try:
            with transaction.atomic():  # Inner savepoint
                process_single_study(study_id)
        except Exception:
            # This study fails, but outer transaction continues
            continue
```

**Locking:**

```sql
-- Pessimistic locking (lock rows)
START TRANSACTION;
SELECT * FROM patient WHERE id = 1 FOR UPDATE;  -- Lock row
-- ... update patient ...
COMMIT;  -- Release lock
```

```python
# Django pessimistic locking
with transaction.atomic():
    patient = Patient.objects.select_for_update().get(id=1)
    patient.status = 'processing'
    patient.save()
```

**Optimistic locking:**

```python
# Using version field
class Patient(models.Model):
    version = models.IntegerField(default=0)

# Update only if version matches
updated = Patient.objects.filter(
    id=patient_id,
    version=current_version
).update(
    status='updated',
    version=F('version') + 1
)

if not updated:
    raise ConcurrentModificationError()
```

This demonstrates:
- **Transaction management** understanding
- **Data integrity** awareness
- **Concurrency** handling

---

### Q17: Write a SQL query to find duplicate medical record numbers in the patient table.

**Answer:**

**Multiple approaches to find duplicates:**

**Approach 1: Using GROUP BY and HAVING**

```sql
SELECT
    medical_record_number,
    COUNT(*) AS duplicate_count
FROM patient
GROUP BY medical_record_number
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

**Approach 2: Show all duplicate patient details**

```sql
SELECT p.*
FROM patient p
INNER JOIN (
    SELECT medical_record_number
    FROM patient
    GROUP BY medical_record_number
    HAVING COUNT(*) > 1
) duplicates ON p.medical_record_number = duplicates.medical_record_number
ORDER BY p.medical_record_number, p.id;
```

**Approach 3: Using window functions (PostgreSQL/MySQL 8+)**

```sql
SELECT
    id,
    medical_record_number,
    first_name,
    last_name,
    COUNT(*) OVER (PARTITION BY medical_record_number) AS duplicate_count
FROM patient
WHERE (
    SELECT COUNT(*)
    FROM patient p2
    WHERE p2.medical_record_number = patient.medical_record_number
) > 1
ORDER BY medical_record_number, id;
```

**Approach 4: Self-join**

```sql
SELECT DISTINCT
    p1.id AS patient1_id,
    p2.id AS patient2_id,
    p1.medical_record_number,
    p1.first_name AS patient1_name,
    p2.first_name AS patient2_name
FROM patient p1
INNER JOIN patient p2
    ON p1.medical_record_number = p2.medical_record_number
    AND p1.id < p2.id  -- Avoid showing same pair twice
ORDER BY p1.medical_record_number;
```

**Finding duplicates with additional criteria:**

```sql
-- Duplicates in same hospital
SELECT
    hospital_id,
    medical_record_number,
    COUNT(*) AS count
FROM patient
GROUP BY hospital_id, medical_record_number
HAVING COUNT(*) > 1;
```

**Find potential duplicates by name:**

```sql
SELECT
    first_name,
    last_name,
    date_of_birth,
    COUNT(*) AS count,
    GROUP_CONCAT(id) AS patient_ids
FROM patient
GROUP BY first_name, last_name, date_of_birth
HAVING COUNT(*) > 1;
```

**Delete duplicates (keep oldest):**

```sql
-- Preview duplicates to delete
SELECT p1.*
FROM patient p1
INNER JOIN patient p2
    ON p1.medical_record_number = p2.medical_record_number
    AND p1.id > p2.id;  -- Keep lower ID (older record)

-- Delete duplicates (BE CAREFUL!)
DELETE p1
FROM patient p1
INNER JOIN patient p2
    ON p1.medical_record_number = p2.medical_record_number
    AND p1.id > p2.id;
```

**Django ORM approach:**

```python
from django.db.models import Count

# Find duplicate MRNs
duplicates = Patient.objects.values('medical_record_number').annotate(
    count=Count('id')
).filter(count__gt=1)

for dup in duplicates:
    mrn = dup['medical_record_number']
    patients = Patient.objects.filter(medical_record_number=mrn)
    print(f"MRN {mrn} has {dup['count']} patients:")
    for p in patients:
        print(f"  - ID: {p.id}, Name: {p.full_name}")
```

**Prevention - add unique constraint:**

```sql
-- Prevent future duplicates
ALTER TABLE patient
ADD CONSTRAINT unique_mrn UNIQUE (medical_record_number);
```

```python
# Django model
class Patient(models.Model):
    medical_record_number = models.CharField(
        max_length=50,
        unique=True  # Database constraint
    )
```

This demonstrates:
- **Data quality** analysis
- **Query techniques** (GROUP BY, joins, subqueries)
- **Problem-solving** skills

---

### Q18: Explain the difference between DELETE, TRUNCATE, and DROP in SQL.

**Answer:**

All three remove data, but they work differently:

**DELETE** - Removes rows (DML)

```sql
-- Delete specific rows
DELETE FROM patient WHERE hospital_id = 5;

-- Delete all rows
DELETE FROM patient;
```

**Characteristics:**
✅ Can use WHERE clause (selective deletion)
✅ Can be rolled back (in transaction)
✅ Triggers fire (e.g., post_delete signals)
✅ Slow for large tables (row-by-row)
❌ Doesn't reset AUTO_INCREMENT

**TRUNCATE** - Removes all rows (DDL)

```sql
TRUNCATE TABLE patient;
```

**Characteristics:**
✅ Very fast (drops and recreates table structure)
✅ Resets AUTO_INCREMENT counter
❌ Cannot use WHERE clause (all or nothing)
❌ Cannot be rolled back (in most databases)
❌ Triggers don't fire
❌ Foreign key constraints may prevent it

**DROP** - Removes entire table (DDL)

```sql
DROP TABLE patient;
```

**Characteristics:**
- Deletes table structure AND data
- Cannot be rolled back
- Removes indexes, constraints, triggers
- Table ceases to exist

**Comparison table:**

| Feature | DELETE | TRUNCATE | DROP |
|---------|--------|----------|------|
| **Speed** | Slow | Fast | Fast |
| **WHERE clause** | ✅ Yes | ❌ No | ❌ No |
| **Rollback** | ✅ Yes | ❌ No | ❌ No |
| **Reset AUTO_INCREMENT** | ❌ No | ✅ Yes | ✅ Yes (table gone) |
| **Triggers** | ✅ Fire | ❌ Don't fire | ❌ Don't fire |
| **Structure** | Keep | Keep | ❌ Remove |
| **Type** | DML | DDL | DDL |

**Examples:**

**1. DELETE with conditions:**
```sql
-- Delete old audit logs (keep last 90 days)
DELETE FROM audit_log
WHERE timestamp < DATE_SUB(NOW(), INTERVAL 90 DAY);

-- In transaction
START TRANSACTION;
DELETE FROM imaging_study WHERE status = 'archived';
-- Can rollback if needed
COMMIT;
```

**2. TRUNCATE for clearing tables:**
```sql
-- Clear test data
TRUNCATE TABLE patient;
TRUNCATE TABLE imaging_study;
-- Fast, resets IDs to 1

-- ❌ This fails if foreign keys exist
TRUNCATE TABLE hospital;  -- ERROR: patients reference hospital
```

**3. DROP to remove table:**
```sql
-- Remove obsolete table
DROP TABLE old_backup_table;

-- Drop with safety check
DROP TABLE IF EXISTS temp_table;
```

**Foreign key considerations:**

```sql
-- DELETE: Cascade works
DELETE FROM hospital WHERE id = 1;
-- If CASCADE configured, deletes related patients

-- TRUNCATE: Blocked by foreign keys
TRUNCATE TABLE hospital;
-- ERROR: Cannot truncate table with foreign key references

-- Workaround: disable checks (risky!)
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE patient;
SET FOREIGN_KEY_CHECKS = 1;
```

**Django equivalents:**

```python
# DELETE
Patient.objects.filter(hospital_id=5).delete()  # Conditional
Patient.objects.all().delete()  # All rows

# TRUNCATE (no direct method, use raw SQL)
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("TRUNCATE TABLE medical_imaging_patient")

# DROP (via migration)
python manage.py makemigrations  # After removing model
python manage.py migrate
```

**Performance comparison:**

```sql
-- Large table (1 million rows)

DELETE FROM patient;
-- Time: 45 seconds (logs each deletion)

TRUNCATE TABLE patient;
-- Time: 0.5 seconds (instant)

DROP TABLE patient;
-- Time: 0.3 seconds (instant)
```

**When to use each:**

**DELETE:**
- Removing specific rows (WHERE clause)
- Need to rollback
- Need triggers to fire
- Foreign key cascades required

**TRUNCATE:**
- Clearing entire table quickly
- Resetting AUTO_INCREMENT
- Test data cleanup
- No foreign key dependencies

**DROP:**
- Removing obsolete tables
- Database cleanup
- Schema changes

**Real-world example:**

```sql
-- Monthly cleanup job
START TRANSACTION;

-- Delete old audit logs (keep structure)
DELETE FROM audit_log
WHERE timestamp < DATE_SUB(NOW(), INTERVAL 6 MONTH);

-- Clear temp processing table
TRUNCATE TABLE temp_image_processing;

-- Remove old backup table
DROP TABLE IF EXISTS patient_backup_2023;

COMMIT;
```

This demonstrates:
- **SQL command** knowledge
- **Performance** understanding
- **Data management** skills

---

### Q19: What are SQL subqueries? Write a query to find patients who have more studies than the average.

**Answer:**

A **subquery** is a query nested inside another query. It can be used in SELECT, FROM, WHERE, or HAVING clauses.

**Types of subqueries:**

**1. Scalar subquery** (returns single value)
**2. Row subquery** (returns single row)
**3. Column subquery** (returns single column)
**4. Table subquery** (returns table)

**Find patients with more studies than average:**

```sql
SELECT
    p.id,
    p.medical_record_number,
    p.first_name,
    p.last_name,
    COUNT(s.id) AS study_count
FROM patient p
LEFT JOIN imaging_study s ON p.id = s.patient_id
GROUP BY p.id, p.medical_record_number, p.first_name, p.last_name
HAVING COUNT(s.id) > (
    -- Subquery: calculate average studies per patient
    SELECT AVG(study_count)
    FROM (
        SELECT patient_id, COUNT(*) AS study_count
        FROM imaging_study
        GROUP BY patient_id
    ) AS patient_studies
)
ORDER BY study_count DESC;
```

**Subquery in WHERE clause:**

```sql
-- Find patients from hospitals with more than 50 patients
SELECT *
FROM patient
WHERE hospital_id IN (
    SELECT hospital_id
    FROM patient
    GROUP BY hospital_id
    HAVING COUNT(*) > 50
);
```

**Subquery in FROM clause (derived table):**

```sql
-- Monthly study statistics
SELECT
    month,
    AVG(daily_count) AS avg_daily_studies
FROM (
    SELECT
        DATE_FORMAT(study_date, '%Y-%m') AS month,
        DATE(study_date) AS day,
        COUNT(*) AS daily_count
    FROM imaging_study
    GROUP BY month, day
) AS daily_stats
GROUP BY month
ORDER BY month DESC;
```

**Correlated subquery** (references outer query):

```sql
-- Find studies with more images than average for their modality
SELECT
    s.id,
    s.modality,
    (SELECT COUNT(*) FROM dicom_image WHERE study_id = s.id) AS image_count
FROM imaging_study s
WHERE (
    SELECT COUNT(*)
    FROM dicom_image
    WHERE study_id = s.id
) > (
    -- Average images for this modality
    SELECT AVG(img_count)
    FROM (
        SELECT st.id, COUNT(img.id) AS img_count
        FROM imaging_study st
        LEFT JOIN dicom_image img ON st.id = img.study_id
        WHERE st.modality = s.modality  -- Correlated!
        GROUP BY st.id
    ) AS modality_avg
);
```

**EXISTS subquery** (more efficient than IN for large datasets):

```sql
-- Find patients who have at least one CT scan
SELECT p.*
FROM patient p
WHERE EXISTS (
    SELECT 1
    FROM imaging_study s
    WHERE s.patient_id = p.id
    AND s.modality = 'CT'
);
```

**NOT EXISTS:**

```sql
-- Find patients with no studies
SELECT p.*
FROM patient p
WHERE NOT EXISTS (
    SELECT 1
    FROM imaging_study s
    WHERE s.patient_id = p.id
);
```

**Subquery vs JOIN:**

```sql
-- Using subquery
SELECT *
FROM patient
WHERE hospital_id IN (
    SELECT id FROM hospital WHERE name LIKE '%General%'
);

-- Using JOIN (often faster)
SELECT p.*
FROM patient p
INNER JOIN hospital h ON p.hospital_id = h.id
WHERE h.name LIKE '%General%';
```

**Complex example - Find hospitals with above-average patient satisfaction:**

```sql
SELECT
    h.name,
    (
        SELECT COUNT(*)
        FROM patient p
        WHERE p.hospital_id = h.id
    ) AS patient_count,
    (
        SELECT COUNT(*)
        FROM imaging_study s
        INNER JOIN patient p ON s.patient_id = p.id
        WHERE p.hospital_id = h.id
    ) AS total_studies
FROM hospital h
WHERE (
    SELECT COUNT(*)
    FROM patient p
    WHERE p.hospital_id = h.id
) > (
    SELECT AVG(patient_count)
    FROM (
        SELECT hospital_id, COUNT(*) AS patient_count
        FROM patient
        GROUP BY hospital_id
    ) AS hospital_patients
)
ORDER BY patient_count DESC;
```

**Django ORM equivalent:**

```python
from django.db.models import Count, Avg, Subquery, OuterRef

# Patients with more studies than average
avg_studies = ImagingStudy.objects.values('patient').annotate(
    count=Count('id')
).aggregate(Avg('count'))['count__avg']

patients = Patient.objects.annotate(
    study_count=Count('imaging_studies')
).filter(
    study_count__gt=avg_studies
)

# Patients from hospitals with >50 patients
Patient.objects.filter(
    hospital__in=Hospital.objects.annotate(
        patient_count=Count('patients')
    ).filter(patient_count__gt=50)
)

# Using Subquery
from django.db.models import Subquery, OuterRef

# Get most recent study date for each patient
recent_study = ImagingStudy.objects.filter(
    patient=OuterRef('pk')
).order_by('-study_date').values('study_date')[:1]

patients_with_recent = Patient.objects.annotate(
    most_recent_study=Subquery(recent_study)
)
```

This demonstrates:
- **Subquery** mastery
- **Query optimization** choices (subquery vs JOIN)
- **Complex data analysis**

---

### Q20: Explain database normalization. What are the different normal forms?

**Answer:**

**Normalization** is the process of organizing data to **reduce redundancy** and **improve data integrity**.

**Why normalize?**

✅ Eliminates duplicate data
✅ Prevents update anomalies
✅ Ensures data consistency
✅ Reduces storage

**Normal Forms:**

**1st Normal Form (1NF) - Atomic Values**

Each column contains atomic (indivisible) values. No repeating groups.

**❌ Not 1NF:**
```
patient
| id | name       | phone_numbers              |
|----|------------|----------------------------|
| 1  | John Doe   | 555-0001, 555-0002        |
```

**✅ 1NF:**
```
patient
| id | name       |
|----|------------|
| 1  | John Doe   |

patient_phone
| patient_id | phone_number |
|------------|--------------|
| 1          | 555-0001     |
| 1          | 555-0002     |
```

**2nd Normal Form (2NF) - No Partial Dependencies**

Must be in 1NF + all non-key attributes depend on **entire** primary key (matters for composite keys).

**❌ Not 2NF:**
```
imaging_study
| study_id | patient_id | patient_name | modality |
|----------|------------|--------------|----------|
| 1        | 100        | John Doe     | CT       |
```
Problem: `patient_name` depends only on `patient_id`, not the full key `study_id`.

**✅ 2NF:**
```
patient
| id  | name     |
|-----|----------|
| 100 | John Doe |

imaging_study
| study_id | patient_id | modality |
|----------|------------|----------|
| 1        | 100        | CT       |
```

**3rd Normal Form (3NF) - No Transitive Dependencies**

Must be in 2NF + no transitive dependencies (non-key attributes don't depend on other non-key attributes).

**❌ Not 3NF:**
```
imaging_study
| id | patient_id | hospital_id | hospital_name      |
|----|------------|-------------|--------------------|
| 1  | 100        | 5           | City General       |
```
Problem: `hospital_name` depends on `hospital_id` (transitive dependency).

**✅ 3NF:**
```
hospital
| id | name          |
|----|---------------|
| 5  | City General  |

patient
| id  | hospital_id |
|-----|-------------|
| 100 | 5           |

imaging_study
| id | patient_id |
|----|------------|
| 1  | 100        |
```

**Boyce-Codd Normal Form (BCNF)** - Stricter version of 3NF

Every determinant must be a candidate key.

**My project schema (normalized to 3NF):**

```
Hospital (3NF)
├─ id (PK)
├─ name
├─ address
└─ contact_email

Patient (3NF)
├─ id (PK)
├─ hospital_id (FK → Hospital)
├─ medical_record_number (unique)
├─ first_name
├─ last_name
└─ date_of_birth

ImagingStudy (3NF)
├─ id (PK)
├─ patient_id (FK → Patient)
├─ study_date
├─ modality
└─ status

DicomImage (3NF)
├─ id (PK)
├─ study_id (FK → ImagingStudy)
├─ instance_number
└─ image_file

Diagnosis (3NF)
├─ id (PK)
├─ study_id (FK → ImagingStudy, unique)
├─ findings
└─ severity
```

**Denormalization - When to break the rules:**

Sometimes you **intentionally** denormalize for performance:

**Example: Storing patient full_name**

```python
# ❌ Normalized (good for updates)
class Patient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
```

```python
# ✅ Denormalized (faster queries, but redundant)
class Patient(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    full_name = models.CharField(max_length=200)  # Redundant!

    def save(self, *args, **kwargs):
        self.full_name = f"{self.first_name} {self.last_name}"
        super().save(*args, **kwargs)
```

**When to denormalize:**

✅ Read-heavy applications
✅ Expensive joins
✅ Reporting/analytics
✅ Caching calculated values

❌ Don't denormalize:
- Write-heavy applications
- Frequently changing data
- Without clear performance gain

**Real-world example - Study count on Patient:**

```python
# Normalized (query on-demand)
study_count = patient.imaging_studies.count()  # DB query

# Denormalized (cached count)
class Patient(models.Model):
    cached_study_count = models.IntegerField(default=0)

# Update via signal
@receiver(post_save, sender=ImagingStudy)
def update_study_count(sender, instance, created, **kwargs):
    if created:
        Patient.objects.filter(pk=instance.patient_id).update(
            cached_study_count=F('cached_study_count') + 1
        )
```

This demonstrates:
- **Database design** principles
- **Normalization** understanding
- **Performance trade-offs**

---

### Q21: What is the difference between UNION, UNION ALL, INTERSECT, and EXCEPT in SQL?

**Answer:**

These are **set operations** that combine results from multiple SELECT statements.

**UNION** - Combines results, removes duplicates

```sql
-- All patients and staff members (no duplicates)
SELECT first_name, last_name, 'Patient' AS type
FROM patient
UNION
SELECT first_name, last_name, 'Staff' AS type
FROM staff;
```

**Characteristics:**
✅ Removes duplicate rows
❌ Slower (requires sorting/deduplication)
⚠️ Columns must match in number and type

**UNION ALL** - Combines results, keeps duplicates

```sql
-- All medical events (studies + diagnoses) with duplicates
SELECT study_date AS event_date, 'Study' AS type
FROM imaging_study
UNION ALL
SELECT created_at, 'Diagnosis' AS type
FROM diagnosis;
```

**Characteristics:**
✅ Faster (no deduplication)
✅ Keeps all rows including duplicates
⚠️ Use when you know there are no duplicates or want them

**Performance comparison:**

```sql
-- Slow: 100,000 rows → deduplicate → 95,000 rows
SELECT modality FROM imaging_study
UNION
SELECT modality FROM archived_imaging_study;

-- Fast: 100,000 rows → keep all
SELECT modality FROM imaging_study
UNION ALL
SELECT modality FROM archived_imaging_study;
```

**INTERSECT** - Returns only common rows (both sets)

```sql
-- Patients who are also in staff table (works for employees who are patients)
SELECT first_name, last_name
FROM patient
INTERSECT
SELECT first_name, last_name
FROM staff;
```

**MySQL doesn't support INTERSECT** (use JOIN instead):

```sql
-- MySQL equivalent using JOIN
SELECT DISTINCT p.first_name, p.last_name
FROM patient p
INNER JOIN staff s
    ON p.first_name = s.first_name
    AND p.last_name = s.last_name;
```

**EXCEPT** (or MINUS in Oracle) - Returns rows in first set but not in second

```sql
-- PostgreSQL
SELECT first_name, last_name
FROM patient
EXCEPT
SELECT first_name, last_name
FROM archived_patient;
```

**MySQL doesn't support EXCEPT** (use LEFT JOIN):

```sql
-- MySQL equivalent
SELECT p.first_name, p.last_name
FROM patient p
LEFT JOIN archived_patient ap
    ON p.first_name = ap.first_name
    AND p.last_name = ap.last_name
WHERE ap.id IS NULL;
```

**Real-world examples:**

**Example 1: All medical records timeline**

```sql
-- Combine studies and diagnoses into timeline
SELECT
    s.id AS event_id,
    'Study' AS event_type,
    s.study_date AS event_date,
    s.modality AS details
FROM imaging_study s
UNION ALL
SELECT
    d.id,
    'Diagnosis',
    d.created_at,
    d.severity
FROM diagnosis d
ORDER BY event_date DESC;
```

**Example 2: Active vs inactive patients**

```sql
-- Patients who had studies this year but not last year
SELECT patient_id
FROM imaging_study
WHERE YEAR(study_date) = 2024
EXCEPT
SELECT patient_id
FROM imaging_study
WHERE YEAR(study_date) = 2023;
```

**Example 3: Data validation**

```sql
-- Find orphaned studies (patient doesn't exist)
SELECT patient_id
FROM imaging_study
EXCEPT
SELECT id
FROM patient;
```

**Comparison table:**

| Operation | Removes Duplicates | Speed | MySQL Support |
|-----------|-------------------|-------|---------------|
| UNION | ✅ Yes | Slow | ✅ Yes |
| UNION ALL | ❌ No | Fast | ✅ Yes |
| INTERSECT | ✅ Yes | Medium | ❌ No (use JOIN) |
| EXCEPT/MINUS | ✅ Yes | Medium | ❌ No (use LEFT JOIN) |

**Rules for set operations:**

1. **Same number of columns**
```sql
-- ❌ Error: Different column counts
SELECT first_name, last_name FROM patient
UNION
SELECT id FROM imaging_study;
```

2. **Compatible data types**
```sql
-- ❌ Error: VARCHAR and INT
SELECT name FROM hospital
UNION
SELECT id FROM patient;
```

3. **ORDER BY goes at end**
```sql
-- ✅ Correct
SELECT * FROM patient WHERE hospital_id = 1
UNION ALL
SELECT * FROM patient WHERE hospital_id = 2
ORDER BY last_name;  -- Applies to entire result

-- ❌ Wrong
SELECT * FROM patient WHERE hospital_id = 1 ORDER BY last_name
UNION ALL
SELECT * FROM patient WHERE hospital_id = 2;
```

**Django ORM:**

```python
# UNION
from django.db.models import Q

# Django doesn't directly support UNION, use union()
qs1 = Patient.objects.filter(hospital_id=1).values('id', 'first_name')
qs2 = Patient.objects.filter(hospital_id=2).values('id', 'first_name')
combined = qs1.union(qs2)  # UNION (removes duplicates)

# UNION ALL
combined_all = qs1.union(qs2, all=True)  # UNION ALL (keeps duplicates)

# INTERSECT
intersection = qs1.intersection(qs2)

# EXCEPT (DIFFERENCE)
difference = qs1.difference(qs2)
```

This demonstrates:
- **Set operations** mastery
- **SQL portability** awareness (MySQL limitations)
- **Performance** considerations

---

### Q22: What are window functions (analytic functions) in SQL? Give examples.

**Answer:**

**Window functions** perform calculations across a set of rows related to the current row—without collapsing rows like GROUP BY does.

**Syntax:**
```sql
function() OVER (
    PARTITION BY column  -- Optional: group by
    ORDER BY column      -- Optional: order within group
    ROWS/RANGE clause    -- Optional: frame specification
)
```

**Common window functions:**

**ROW_NUMBER() - Assigns unique sequential numbers**

```sql
-- Number patients within each hospital
SELECT
    id,
    first_name,
    last_name,
    hospital_id,
    ROW_NUMBER() OVER (
        PARTITION BY hospital_id
        ORDER BY created_at
    ) AS patient_number_in_hospital
FROM patient;
```

**RANK() and DENSE_RANK() - Ranking with gaps/without gaps**

```sql
-- Rank studies by image count within each modality
SELECT
    s.id,
    s.modality,
    COUNT(img.id) AS image_count,
    RANK() OVER (
        PARTITION BY s.modality
        ORDER BY COUNT(img.id) DESC
    ) AS rank_with_gaps,
    DENSE_RANK() OVER (
        PARTITION BY s.modality
        ORDER BY COUNT(img.id) DESC
    ) AS rank_no_gaps
FROM imaging_study s
LEFT JOIN dicom_image img ON s.id = img.study_id
GROUP BY s.id, s.modality;
```

**Difference:**
- `RANK()`: 1, 2, 2, 4 (skips 3)
- `DENSE_RANK()`: 1, 2, 2, 3 (no skip)

**NTILE(n) - Divide into n buckets**

```sql
-- Divide patients into quartiles by study count
SELECT
    p.id,
    p.first_name,
    COUNT(s.id) AS study_count,
    NTILE(4) OVER (ORDER BY COUNT(s.id) DESC) AS quartile
FROM patient p
LEFT JOIN imaging_study s ON p.id = s.patient_id
GROUP BY p.id, p.first_name;
```

**LAG() and LEAD() - Access previous/next row**

```sql
-- Compare each study date with previous study for same patient
SELECT
    patient_id,
    study_date,
    LAG(study_date) OVER (
        PARTITION BY patient_id
        ORDER BY study_date
    ) AS previous_study_date,
    DATEDIFF(
        study_date,
        LAG(study_date) OVER (PARTITION BY patient_id ORDER BY study_date)
    ) AS days_since_last_study
FROM imaging_study
ORDER BY patient_id, study_date;
```

**FIRST_VALUE() and LAST_VALUE()**

```sql
-- Show first and most recent study per patient
SELECT DISTINCT
    patient_id,
    FIRST_VALUE(study_date) OVER (
        PARTITION BY patient_id
        ORDER BY study_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS first_study_date,
    LAST_VALUE(study_date) OVER (
        PARTITION BY patient_id
        ORDER BY study_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS latest_study_date
FROM imaging_study;
```

**Aggregate functions as window functions:**

```sql
-- Running total of studies per day
SELECT
    DATE(study_date) AS study_day,
    COUNT(*) AS daily_count,
    SUM(COUNT(*)) OVER (
        ORDER BY DATE(study_date)
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_total
FROM imaging_study
GROUP BY DATE(study_date)
ORDER BY study_day;
```

**Real-world medical imaging examples:**

**Example 1: Find most recent study for each patient**

```sql
SELECT *
FROM (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY patient_id
            ORDER BY study_date DESC
        ) AS rn
    FROM imaging_study s
) ranked
WHERE rn = 1;  -- Only most recent per patient
```

**Example 2: Calculate patient percentile by study count**

```sql
SELECT
    p.id,
    p.medical_record_number,
    COUNT(s.id) AS study_count,
    PERCENT_RANK() OVER (
        ORDER BY COUNT(s.id)
    ) AS percentile
FROM patient p
LEFT JOIN imaging_study s ON p.id = s.patient_id
GROUP BY p.id, p.medical_record_number;
```

**Example 3: Detect gaps in imaging (patients due for followup)**

```sql
SELECT
    patient_id,
    study_date,
    LEAD(study_date) OVER (
        PARTITION BY patient_id
        ORDER BY study_date
    ) AS next_study,
    DATEDIFF(
        LEAD(study_date) OVER (PARTITION BY patient_id ORDER BY study_date),
        study_date
    ) AS gap_days
FROM imaging_study
HAVING gap_days > 180;  -- 6 month gaps
```

**Frame specifications:**

```sql
ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW  -- All rows up to current
ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING           -- Sliding window of 3
ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING   -- Current to end
```

**MySQL 8+ and PostgreSQL support window functions. Earlier MySQL versions don't.**

This demonstrates:
- **Advanced SQL** expertise
- **Analytical thinking**
- **Modern SQL features**

---

### Q23: Explain the difference between CHAR vs VARCHAR, and INT vs BIGINT.

**Answer:**

These are fundamental **database data type** choices that impact storage, performance, and data integrity.

**CHAR vs VARCHAR:**

**CHAR(n)** - Fixed-length string

```sql
CREATE TABLE test (
    country_code CHAR(2)  -- Always 2 bytes: 'US', 'CA'
);
```

**Characteristics:**
✅ **Fixed storage**: Always uses n bytes (padded with spaces)
✅ **Faster**: Predictable storage = faster lookups
✅ **Good for**: Fixed-length data (country codes, status flags)
❌ **Wastes space**: 'A' in CHAR(10) uses 10 bytes

**VARCHAR(n)** - Variable-length string

```sql
CREATE TABLE patient (
    first_name VARCHAR(100)  -- Uses actual length + 1-2 bytes overhead
);
```

**Characteristics:**
✅ **Variable storage**: Only uses needed space + overhead
✅ **Space-efficient**: 'John' in VARCHAR(100) uses 5 bytes (not 100)
✅ **Good for**: Variable-length data (names, addresses, emails)
❌ **Slightly slower**: Variable length = more complex lookups

**Storage comparison:**

| Value | CHAR(10) | VARCHAR(10) |
|-------|----------|-------------|
| 'A' | 10 bytes | 2 bytes (1 + overhead) |
| 'Hello' | 10 bytes | 6 bytes (5 + overhead) |
| 'HelloWorld' | 10 bytes | 11 bytes (10 + overhead) |

**When to use:**

**CHAR:**
- Country codes: `CHAR(2)` for 'US', 'UK'
- State codes: `CHAR(2)` for 'CA', 'NY'
- Status flags: `CHAR(1)` for 'A' (active), 'I' (inactive)
- Fixed identifiers: `CHAR(36)` for UUIDs

**VARCHAR:**
- Names: `VARCHAR(100)`
- Emails: `VARCHAR(255)`
- Addresses: `VARCHAR(500)`
- Medical notes: `VARCHAR(5000)` or TEXT

**From my project:**

```python
# Fixed-length
class ImagingStudy(models.Model):
    modality = models.CharField(max_length=5)  # 'CT', 'MRI', 'XRAY'
    # Could use CHAR(5) in raw SQL

# Variable-length
class Patient(models.Model):
    first_name = models.CharField(max_length=100)  # VARCHAR
    medical_record_number = models.CharField(max_length=50)  # VARCHAR
```

---

**INT vs BIGINT:**

**INT** - 4-byte signed integer

```sql
hospital_id INT  -- Range: -2,147,483,648 to 2,147,483,647
```

**Characteristics:**
- **Storage**: 4 bytes
- **Range**: ~2.1 billion values
- **Good for**: Most ID columns, counts, small numbers
- **Auto-increment**: Can handle up to 2 billion records

**BIGINT** - 8-byte signed integer

```sql
image_id BIGINT  -- Range: -9,223,372,036,854,775,808 to 9+ quintillion
```

**Characteristics:**
- **Storage**: 8 bytes (double INT)
- **Range**: ~9.2 quintillion values
- **Good for**: Very large datasets, timestamps, large counts
- **Auto-increment**: Can handle trillions of records

**Comparison:**

| Type | Bytes | Max Value | Use Case |
|------|-------|-----------|----------|
| TINYINT | 1 | 255 (unsigned) | Age, small counts |
| SMALLINT | 2 | 32,767 | Port numbers |
| MEDIUMINT | 3 | 8,388,607 | Medium datasets |
| INT | 4 | 2,147,483,647 | Standard IDs |
| BIGINT | 8 | 9+ quintillion | Timestamps, huge datasets |

**When to use:**

**INT (most common):**
```sql
CREATE TABLE patient (
    id INT AUTO_INCREMENT PRIMARY KEY,  -- Fine for millions of patients
    hospital_id INT,
    age TINYINT,  -- 0-150
);
```

**BIGINT (when needed):**
```sql
CREATE TABLE dicom_image (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,  -- Billions of images
    file_size_bytes BIGINT,  -- Files >2GB need BIGINT
    created_timestamp BIGINT  -- Unix timestamps (milliseconds)
);
```

**Storage impact on large tables:**

```
Table: dicom_image (1 billion rows)

INT id:      4 bytes × 1B = 4 GB
BIGINT id:   8 bytes × 1B = 8 GB

Difference: 4 GB extra (plus indexes!)
```

**Real-world example from my project:**

```python
class DicomImage(models.Model):
    id = models.BigAutoField(primary_key=True)  # BIGINT (medical imaging = huge datasets)
    study = models.ForeignKey(ImagingStudy)     # INT is fine
    file_size_bytes = models.BigIntegerField()  # BIGINT (files can be >2GB)
    instance_number = models.IntegerField()     # INT (instances per study < 2B)
```

**Django defaults:**

```python
# Django 3.2+
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'  # BIGINT IDs by default

# Older Django
id = models.AutoField(primary_key=True)  # INT
```

**Performance consideration:**

INT vs BIGINT doesn't significantly affect query speed, but:
- **Indexes are larger** with BIGINT (more disk I/O)
- **Memory usage** increases (index cache)
- **Network transfer** doubles for ID columns

**Recommendation:**

- ✅ Use **INT** for most ID columns (handles billions of records)
- ✅ Use **BIGINT** only when:
  - Expecting > 2 billion records
  - Storing large numbers (file sizes, timestamps)
  - Future-proofing critical tables

**Other numeric types:**

```sql
DECIMAL(10,2)  -- Exact decimal (currency, measurements) - $1234.56
FLOAT/DOUBLE   -- Approximate decimal (scientific data) - less precise
```

This demonstrates:
- **Data type** understanding
- **Storage optimization**
- **Scalability** planning

---

### Q24: What is a CTE (Common Table Expression)? How is it different from a subquery?

**Answer:**

A **CTE (Common Table Expression)** is a temporary named result set that exists only during query execution. Think of it as a "named subquery" defined using the `WITH` clause.

**Syntax:**

```sql
WITH cte_name AS (
    SELECT ...
)
SELECT * FROM cte_name;
```

**Simple example:**

```sql
-- CTE to calculate average studies per patient
WITH avg_studies AS (
    SELECT AVG(study_count) AS avg_count
    FROM (
        SELECT patient_id, COUNT(*) AS study_count
        FROM imaging_study
        GROUP BY patient_id
    ) patient_counts
)
SELECT
    p.id,
    p.medical_record_number,
    COUNT(s.id) AS study_count
FROM patient p
LEFT JOIN imaging_study s ON p.id = s.patient_id
CROSS JOIN avg_studies
GROUP BY p.id, p.medical_record_number
HAVING COUNT(s.id) > avg_studies.avg_count;
```

**Multiple CTEs:**

```sql
WITH
hospital_stats AS (
    SELECT
        hospital_id,
        COUNT(*) AS patient_count
    FROM patient
    GROUP BY hospital_id
),
study_stats AS (
    SELECT
        p.hospital_id,
        COUNT(s.id) AS total_studies
    FROM patient p
    LEFT JOIN imaging_study s ON p.id = s.patient_id
    GROUP BY p.hospital_id
)
SELECT
    h.name,
    hs.patient_count,
    ss.total_studies
FROM hospital h
LEFT JOIN hospital_stats hs ON h.id = hs.hospital_id
LEFT JOIN study_stats ss ON h.id = ss.hospital_id
ORDER BY hs.patient_count DESC;
```

**Recursive CTE** (advanced):

```sql
-- Organizational hierarchy (if hospitals had parent-child relationships)
WITH RECURSIVE hospital_hierarchy AS (
    -- Base case: top-level hospitals
    SELECT id, name, parent_id, 1 AS level
    FROM hospital
    WHERE parent_id IS NULL

    UNION ALL

    -- Recursive case: children
    SELECT h.id, h.name, h.parent_id, hh.level + 1
    FROM hospital h
    INNER JOIN hospital_hierarchy hh ON h.parent_id = hh.id
)
SELECT * FROM hospital_hierarchy ORDER BY level, name;
```

**CTE vs Subquery:**

**Subquery (inline):**
```sql
SELECT *
FROM patient
WHERE hospital_id IN (
    SELECT id
    FROM hospital
    WHERE name LIKE '%General%'
);
```

**Same query with CTE:**
```sql
WITH general_hospitals AS (
    SELECT id
    FROM hospital
    WHERE name LIKE '%General%'
)
SELECT *
FROM patient
WHERE hospital_id IN (SELECT id FROM general_hospitals);
```

**Advantages of CTEs:**

✅ **Readability**: Named result sets are self-documenting
✅ **Reusability**: Reference same CTE multiple times
✅ **Debugging**: Test CTEs independently
✅ **Recursion**: Only way to do recursive queries
✅ **Complex queries**: Break into logical steps

**Example - Reusing CTE:**

```sql
WITH patient_study_counts AS (
    SELECT
        patient_id,
        COUNT(*) AS study_count
    FROM imaging_study
    GROUP BY patient_id
)
SELECT
    (SELECT AVG(study_count) FROM patient_study_counts) AS avg_studies,
    (SELECT MAX(study_count) FROM patient_study_counts) AS max_studies,
    (SELECT COUNT(*) FROM patient_study_counts WHERE study_count > 5) AS active_patients;
```

**Real-world example from medical imaging:**

```sql
-- Find patients with above-average CT scans
WITH ct_scan_counts AS (
    SELECT
        patient_id,
        COUNT(*) AS ct_count
    FROM imaging_study
    WHERE modality = 'CT'
    GROUP BY patient_id
),
avg_ct AS (
    SELECT AVG(ct_count) AS avg_count
    FROM ct_scan_counts
)
SELECT
    p.id,
    p.medical_record_number,
    p.first_name,
    p.last_name,
    csc.ct_count,
    ac.avg_count
FROM patient p
INNER JOIN ct_scan_counts csc ON p.id = csc.patient_id
CROSS JOIN avg_ct ac
WHERE csc.ct_count > ac.avg_count
ORDER BY csc.ct_count DESC;
```

**Comparison table:**

| Feature | CTE | Subquery |
|---------|-----|----------|
| **Readability** | ✅ Excellent | ⚠️ Can be messy |
| **Reusability** | ✅ Yes | ❌ No (must repeat) |
| **Recursive** | ✅ Yes | ❌ No |
| **Performance** | ~Same | ~Same |
| **Debugging** | ✅ Easy | ⚠️ Harder |

**Performance note:**

CTEs and subqueries have **similar performance** in modern databases. The optimizer often converts them to the same execution plan.

**Materialized CTEs** (PostgreSQL):

```sql
-- Force materialization (compute once, reuse result)
WITH MATERIALIZED patient_stats AS (
    SELECT patient_id, COUNT(*) AS study_count
    FROM imaging_study
    GROUP BY patient_id
)
SELECT * FROM patient_stats;
```

**Django ORM doesn't directly support CTEs**, but you can use raw SQL:

```python
from django.db import connection

query = """
WITH study_counts AS (
    SELECT patient_id, COUNT(*) AS count
    FROM imaging_study
    GROUP BY patient_id
)
SELECT p.*, sc.count
FROM patient p
LEFT JOIN study_counts sc ON p.id = sc.patient_id
"""

with connection.cursor() as cursor:
    cursor.execute(query)
    results = cursor.fetchall()
```

**When to use CTEs:**

✅ **Complex multi-step queries**
✅ **Need to reference same subquery multiple times**
✅ **Recursive queries** (hierarchies, graphs)
✅ **Improving code readability**
✅ **Debugging complex queries**

This demonstrates:
- **Advanced SQL** techniques
- **Query organization** skills
- **Modern SQL** features

---

## REST API Architecture

### Q25: Explain REST API principles. What makes an API RESTful?

**Answer:**

**REST (Representational State Transfer)** is an architectural style for designing networked applications. A RESTful API follows specific principles:

**1. Client-Server Architecture**

Separation of concerns: client (UI) and server (data/logic) are independent.

```
Client (Next.js) ←→ HTTP ←→ Server (Django API) ←→ Database
```

**2. Stateless**

Each request contains all information needed—server doesn't store client state between requests.

```python
# ❌ Stateful (bad)
# Server remembers last request
if session.get('last_patient_id'):
    patient_id = session['last_patient_id']

# ✅ Stateless (good)
# Client sends all needed data
GET /api/patients/123/  # Patient ID in URL
```

**3. Cacheable**

Responses must define if they can be cached.

```python
# Django REST Framework
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()

    # Response headers automatically include cache directives
    # Cache-Control: max-age=3600
```

**4. Uniform Interface**

Standardized way to interact with resources.

**a) Resource Identification (URIs):**
```
/api/patients/          # Collection
/api/patients/123/      # Specific resource
/api/patients/123/studies/  # Nested resource
```

**b) Resource Manipulation through Representations (JSON/XML):**
```json
GET /api/patients/123/
{
  "id": 123,
  "first_name": "John",
  "last_name": "Doe"
}
```

**c) Self-descriptive Messages (HTTP methods + status codes):**
```
GET    /api/patients/     → 200 OK (list)
POST   /api/patients/     → 201 Created
GET    /api/patients/123/ → 200 OK (detail)
PUT    /api/patients/123/ → 200 OK (full update)
PATCH  /api/patients/123/ → 200 OK (partial update)
DELETE /api/patients/123/ → 204 No Content
```

**d) HATEOAS (Hypermedia As The Engine Of Application State):**
```json
{
  "id": 123,
  "first_name": "John",
  "links": {
    "self": "/api/patients/123/",
    "studies": "/api/patients/123/studies/",
    "hospital": "/api/hospitals/5/"
  }
}
```

**5. Layered System**

Client can't tell if connected directly to server or through intermediaries (load balancers, caches, proxies).

**6. Code on Demand (Optional)**

Server can send executable code (JavaScript) to client.

---

**RESTful URL Design:**

**Good (resource-based):**
```
GET    /api/patients/              # List all patients
POST   /api/patients/              # Create patient
GET    /api/patients/123/          # Get specific patient
PUT    /api/patients/123/          # Update patient
DELETE /api/patients/123/          # Delete patient
GET    /api/patients/123/studies/  # Patient's studies
```

**Bad (verb-based, not RESTful):**
```
❌ /api/getPatients/
❌ /api/createPatient/
❌ /api/updatePatient?id=123
❌ /api/deletePatient/123/
```

**HTTP Status Codes:**

```python
# Success
200 OK           # GET, PUT, PATCH successful
201 Created      # POST successful
204 No Content   # DELETE successful

# Client Errors
400 Bad Request  # Invalid data
401 Unauthorized # Not authenticated
403 Forbidden    # Authenticated but not authorized
404 Not Found    # Resource doesn't exist
409 Conflict     # Duplicate or constraint violation

# Server Errors
500 Internal Server Error
503 Service Unavailable
```

**From my project** (`views.py:128-280`):

```python
class PatientViewSet(viewsets.ModelViewSet):
    """
    RESTful API for Patient management

    list:    GET  /api/patients/
    create:  POST /api/patients/
    retrieve: GET  /api/patients/{id}/
    update:  PUT  /api/patients/{id}/
    partial_update: PATCH /api/patients/{id}/
    destroy: DELETE /api/patients/{id}/
    """
    queryset = Patient.objects.select_related('hospital').all()
    serializer_class = PatientSerializer
    filterset_fields = ['hospital', 'gender']
    search_fields = ['first_name', 'last_name', 'medical_record_number']
    ordering_fields = ['last_name', 'created_at']
```

**Versioning:**

```
/api/v1/patients/
/api/v2/patients/  # Breaking changes in v2
```

**Pagination:**

```json
GET /api/patients/?page=2
{
  "count": 150,
  "next": "/api/patients/?page=3",
  "previous": "/api/patients/?page=1",
  "results": [...]
}
```

**Filtering:**

```
/api/studies/?modality=CT&status=pending
/api/patients/?hospital=5&gender=M
/api/patients/?search=John
```

This demonstrates:
- **REST principles** understanding
- **API design** best practices
- **HTTP protocol** knowledge

---

### Q26: Explain Django REST Framework ViewSets, Serializers, and how they work together.

**Answer:**

**Django REST Framework (DRF)** provides tools to build RESTful APIs. The three key components are:

**1. Model** (Django ORM)
**2. Serializer** (converts data)
**3. ViewSet** (handles requests)

**Flow:**
```
HTTP Request → ViewSet → Serializer → Model → Database
HTTP Response ← ViewSet ← Serializer ← Model ← Database
```

---

**Serializers** - Convert between complex data types (models) and JSON

**Basic Serializer** (`serializers.py:15-50`):

```python
class PatientSerializer(serializers.ModelSerializer):
    # Computed fields
    full_name = serializers.ReadOnlyField()
    age = serializers.SerializerMethodField()

    # Related field customization
    hospital_name = serializers.CharField(source='hospital.name', read_only=True)

    class Meta:
        model = Patient
        fields = [
            'id', 'medical_record_number', 'first_name', 'last_name',
            'full_name', 'age', 'gender', 'date_of_birth',
            'hospital', 'hospital_name', 'email', 'phone'
        ]
        read_only_fields = ['id', 'full_name', 'hospital_name']

    def get_age(self, obj):
        """Calculate age from date_of_birth"""
        from datetime import date
        if obj.date_of_birth:
            today = date.today()
            return today.year - obj.date_of_birth.year
        return None

    def validate_medical_record_number(self, value):
        """Custom validation"""
        if not value.startswith('MRN-'):
            raise serializers.ValidationError(
                "Medical record number must start with 'MRN-'"
            )
        return value
```

**Nested Serializers:**

```python
class DicomImageSerializer(serializers.ModelSerializer):
    file_size_mb = serializers.ReadOnlyField()  # From @property

    class Meta:
        model = DicomImage
        fields = ['id', 'instance_number', 'image_file', 'file_size_mb']

class ImagingStudyDetailSerializer(serializers.ModelSerializer):
    images = DicomImageSerializer(many=True, read_only=True)  # Nested
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)

    class Meta:
        model = ImagingStudy
        fields = [
            'id', 'study_date', 'modality', 'status', 'body_part',
            'patient', 'patient_name', 'images'
        ]
```

**Different Serializers for List vs Detail:**

```python
# List serializer - minimal fields
class ImagingStudyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagingStudy
        fields = ['id', 'study_date', 'modality', 'status']

# Detail serializer - all fields + relations
class ImagingStudyDetailSerializer(serializers.ModelSerializer):
    images = DicomImageSerializer(many=True, read_only=True)
    diagnosis = DiagnosisSerializer(read_only=True)

    class Meta:
        model = ImagingStudy
        fields = '__all__'
```

---

**ViewSets** - Handle CRUD operations

**ModelViewSet** (full CRUD) (`views.py:128-147`):

```python
class PatientViewSet(viewsets.ModelViewSet):
    """
    Provides: list, create, retrieve, update, partial_update, destroy
    """
    queryset = Patient.objects.select_related('hospital').all()
    serializer_class = PatientSerializer

    # Filtering & Search
    filterset_fields = ['hospital', 'gender']
    search_fields = ['first_name', 'last_name', 'medical_record_number']
    ordering_fields = ['last_name', 'created_at']

    # Pagination (from settings)
    pagination_class = PageNumberPagination

    def get_queryset(self):
        """Customize queryset based on user"""
        queryset = super().get_queryset()

        # Filter by hospital for non-admin users
        if not self.request.user.is_staff:
            queryset = queryset.filter(hospital=self.request.user.hospital)

        return queryset
```

**Custom Actions:**

```python
class ImagingStudyViewSet(viewsets.ModelViewSet):
    queryset = ImagingStudy.objects.all()
    serializer_class = ImagingStudySerializer

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Custom endpoint: GET /api/studies/pending/"""
        pending_studies = self.queryset.filter(status='pending')
        serializer = self.get_serializer(pending_studies, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Custom endpoint: POST /api/studies/{id}/complete/"""
        study = self.get_object()
        study.status = 'completed'
        study.save()
        return Response({'status': 'study marked complete'})
```

**Different Serializers for Different Actions:**

```python
class ImagingStudyViewSet(viewsets.ModelViewSet):
    queryset = ImagingStudy.objects.all()

    def get_serializer_class(self):
        """Use different serializers for list vs detail"""
        if self.action == 'list':
            return ImagingStudyListSerializer
        return ImagingStudyDetailSerializer
```

**ReadOnlyModelViewSet** (only list, retrieve):

```python
class HospitalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Only: list, retrieve (no create/update/delete)
    """
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer
```

---

**URL Routing** (`urls.py`):

```python
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'patients', PatientViewSet)
router.register(r'studies', ImagingStudyViewSet)
router.register(r'hospitals', HospitalViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]

# Automatically creates:
# /api/patients/
# /api/patients/{id}/
# /api/studies/
# /api/studies/{id}/
# /api/studies/pending/        # Custom action
# /api/studies/{id}/complete/  # Custom action
```

---

**Complete Example Flow:**

**Request:** `POST /api/patients/`

```json
{
  "first_name": "John",
  "last_name": "Doe",
  "medical_record_number": "MRN-001",
  "date_of_birth": "1980-01-15",
  "gender": "M",
  "hospital": 5
}
```

**What happens:**

1. **Router** routes to `PatientViewSet.create()`
2. **ViewSet** receives request
3. **Serializer** validates data:
   - Checks required fields
   - Runs `validate_medical_record_number()`
   - Validates foreign key (hospital exists)
4. **Serializer.save()** creates Patient instance
5. **Model.save()** inserts into database
6. **Serializer** converts Patient back to JSON
7. **ViewSet** returns `201 Created` response

```json
{
  "id": 123,
  "first_name": "John",
  "last_name": "Doe",
  "full_name": "John Doe",
  "medical_record_number": "MRN-001",
  "age": 44,
  "gender": "M",
  "hospital": 5,
  "hospital_name": "City General Hospital"
}
```

---

**Permission Classes:**

```python
from rest_framework.permissions import IsAuthenticated

class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # Require login

    def get_permissions(self):
        """Different permissions for different actions"""
        if self.action == 'destroy':
            return [IsAdminUser()]  # Only admin can delete
        return super().get_permissions()
```

This demonstrates:
- **DRF architecture** understanding
- **Serialization** patterns
- **ViewSet customization**

---

### Q27: How do you handle file uploads in Django REST Framework? Explain your DICOM image upload implementation.

**Answer:**

**File uploads** in DRF require special handling—multipart/form-data instead of JSON.

**Model with FileField** (`models.py:125-136`):

```python
class DicomImage(models.Model):
    study = models.ForeignKey(ImagingStudy, on_delete=models.CASCADE)
    image_file = models.FileField(
        upload_to='dicom_images/%Y/%m/%d/',  # Organized by date
        max_length=500
    )
    instance_number = models.IntegerField(validators=[MinValueValidator(1)])
    file_size_bytes = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

**Serializer** (`serializers.py:109-130`):

```python
class DicomImageSerializer(serializers.ModelSerializer):
    # FileField automatically handles file uploads
    image_file = serializers.FileField()

    # Display file size in human-readable format
    file_size_mb = serializers.ReadOnlyField()

    class Meta:
        model = DicomImage
        fields = [
            'id', 'study', 'image_file', 'instance_number',
            'file_size_bytes', 'file_size_mb', 'uploaded_at'
        ]
        read_only_fields = ['file_size_bytes', 'uploaded_at']

    def validate_image_file(self, value):
        """Validate DICOM file"""
        # Check file extension
        if not value.name.endswith('.dcm'):
            raise serializers.ValidationError("Only .dcm files allowed")

        # Check file size (max 500MB)
        max_size = 500 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f"File too large (max {max_size/1024/1024}MB)")

        return value

    def create(self, validated_data):
        """Store file size on creation"""
        validated_data['file_size_bytes'] = validated_data['image_file'].size
        return super().create(validated_data)
```

**ViewSet** (`views.py:289-325`):

```python
class DicomImageViewSet(viewsets.ModelViewSet):
    queryset = DicomImage.objects.all()
    serializer_class = DicomImageSerializer
    parser_classes = [MultiPartParser, FormParser]  # Handle file uploads

    def create(self, request, *args, **kwargs):
        """Handle file upload"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Save file
        instance = serializer.save()

        # Trigger async DICOM processing
        from .tasks import process_dicom_image
        process_dicom_image.delay(instance.id)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

**Frontend Upload (Next.js/React):**

```typescript
// Upload DICOM file
const uploadDicomImage = async (studyId: number, file: File) => {
  const formData = new FormData();
  formData.append('study', studyId.toString());
  formData.append('image_file', file);
  formData.append('instance_number', '1');

  const response = await fetch('/api/dicom-images/', {
    method: 'POST',
    body: formData,  // Don't set Content-Type! Browser sets it automatically
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  return response.json();
};
```

**File Storage Configuration** (`settings.py`):

```python
# Local Development
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Production (AWS S3)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'my-dicom-images'
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'private'
```

**Async Processing with Celery** (`tasks.py:71-135`):

```python
@shared_task
def process_dicom_image(image_id):
    """
    Parse DICOM file and extract metadata
    Runs asynchronously to avoid blocking upload
    """
    image = DicomImage.objects.get(id=image_id)

    # Download file from S3 (if using S3)
    file_obj = image.image_file.open('rb')

    try:
        # Parse DICOM using pydicom
        dicom_dataset, metadata = DicomParsingService.parse_dicom_file(file_obj)

        # Update model with metadata
        image.dicom_metadata = metadata
        image.rows = metadata['image']['rows']
        image.columns = metadata['image']['columns']
        image.slice_thickness = metadata['spatial']['slice_thickness']
        image.save()

        return f"Processed DICOM image {image_id}"

    except Exception as e:
        logger.error(f"Failed to process DICOM {image_id}: {e}")
        raise
    finally:
        file_obj.close()
```

**Multiple File Upload:**

```python
class BulkDicomUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        """Upload multiple DICOM files at once"""
        study_id = request.data.get('study')
        files = request.FILES.getlist('files')  # Multiple files

        created_images = []
        for idx, file in enumerate(files, 1):
            image = DicomImage.objects.create(
                study_id=study_id,
                image_file=file,
                instance_number=idx
            )
            created_images.append(image)

            # Process async
            process_dicom_image.delay(image.id)

        serializer = DicomImageSerializer(created_images, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

**File Download:**

```python
@action(detail=True, methods=['get'])
def download(self, request, pk=None):
    """Download DICOM file"""
    image = self.get_object()

    # Check permissions
    if not request.user.has_perm('view_dicom'):
        return Response(
            {'error': 'No permission'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Generate signed URL (S3) or serve file
    if settings.USE_S3:
        url = image.image_file.url  # Temporary signed URL
        return Response({'download_url': url})
    else:
        # Serve file directly
        response = FileResponse(
            image.image_file.open('rb'),
            as_attachment=True,
            filename=f"dicom_{image.id}.dcm"
        )
        return response
```

**Security Considerations:**

1. **Validate file type** (check magic bytes, not just extension)
2. **Limit file size** (prevent DoS)
3. **Scan for malware** (ClamAV integration)
4. **Use signed URLs** (time-limited S3 URLs)
5. **Check permissions** (who can upload/download)

**Performance:**

- **Async processing**: Don't parse large DICOM files during upload (blocks request)
- **Direct S3 upload**: Let client upload directly to S3, then notify backend
- **Chunked upload**: For very large files (>100MB)

This demonstrates:
- **File handling** in Django
- **Async processing** awareness
- **Production considerations** (S3, security)

---

### Q28: How do you implement pagination in Django REST Framework? What are the different pagination styles?

**Answer:**

**Pagination** splits large datasets into smaller pages to improve performance and user experience.

**DRF Pagination Styles:**

**1. PageNumberPagination** (most common)

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}
```

**Request:**
```
GET /api/patients/?page=2
```

**Response:**
```json
{
  "count": 150,
  "next": "http://api.example.com/api/patients/?page=3",
  "previous": "http://api.example.com/api/patients/?page=1",
  "results": [
    {
      "id": 21,
      "first_name": "John",
      "last_name": "Doe"
    },
    // ... 19 more
  ]
}
```

**Custom PageNumberPagination:**

```python
from rest_framework.pagination import PageNumberPagination

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'  # Allow client to control page size
    max_page_size = 100  # Maximum allowed page size

# Use in ViewSet
class PatientViewSet(viewsets.ModelViewSet):
    pagination_class = CustomPagination
```

**2. LimitOffsetPagination**

```python
# Request
GET /api/patients/?limit=20&offset=40

# Response
{
  "count": 150,
  "next": "http://api.example.com/api/patients/?limit=20&offset=60",
  "previous": "http://api.example.com/api/patients/?limit=20&offset=20",
  "results": [...]
}
```

**Use case:** More flexible, allows arbitrary offsets

**3. CursorPagination** (best for large datasets)

```python
from rest_framework.pagination import CursorPagination

class CreatedAtCursorPagination(CursorPagination):
    page_size = 20
    ordering = '-created_at'  # Must specify ordering

# Request
GET /api/patients/?cursor=cD0yMDIzLTAxLTE1KzEzJTNBMzAlM0EwMA%3D%3D

# Response
{
  "next": "http://api.example.com/?cursor=cD0yMDIzLTAx...",
  "previous": "http://api.example.com/?cursor=cj1yMDIzLTA...",
  "results": [...]
}
```

**Advantages:**
- ✅ Constant performance (doesn't slow down on later pages)
- ✅ Prevents duplication if items added during pagination
- ✅ Best for infinite scroll

**Disadvantages:**
- ❌ Can't jump to arbitrary page
- ❌ More complex cursor encoding

**Comparison:**

| Style | Jump to Page | Performance | Use Case |
|-------|-------------|-------------|----------|
| PageNumber | ✅ Yes | ⚠️ Slower on high pages | General use |
| LimitOffset | ✅ Yes | ⚠️ Slower on high offsets | Flexible queries |
| Cursor | ❌ No | ✅ Always fast | Large datasets, infinite scroll |

**Custom Pagination Example:**

```python
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """Customize response format"""
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })
```

**Disable pagination for specific view:**

```python
class HospitalViewSet(viewsets.ModelViewSet):
    pagination_class = None  # No pagination
```

This demonstrates:
- **API optimization** techniques
- **User experience** consideration
- **Performance** awareness

---

### Q29: Explain API authentication vs authorization. How did you implement authentication in your project?

**Answer:**

**Authentication** = Who are you? (Identity)
**Authorization** = What can you do? (Permissions)

**Authentication Methods:**

**1. Session-based (traditional)**
```python
# Django creates session cookie
# Good for: Same-domain apps, Django templates
```

**2. Token-based (API standard)**
```python
# Client stores token, sends in header
Authorization: Token abc123xyz
# Good for: APIs, mobile apps, SPAs
```

**3. JWT (JSON Web Tokens)**
```python
# Stateless, self-contained token
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
# Good for: Microservices, distributed systems
```

**In my project** - Using **django-allauth headless** with session tokens:

**Backend Configuration:**

```python
# settings.py
INSTALLED_APPS = [
    'allauth',
    'allauth.account',
    'allauth.headless',
]

HEADLESS_ONLY = True
HEADLESS_TOKEN_STRATEGY = 'allauth.headless.tokens.sessions.SessionTokenStrategy'

# API requires authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

**Authentication Flow:**

```
1. User logs in: POST /api/auth/login
   {
     "email": "user@example.com",
     "password": "password123"
   }

2. Server validates credentials

3. Server returns session token:
   {
     "user": {...},
     "meta": {
       "session_token": "abc123xyz"
     }
   }

4. Client stores token (localStorage)

5. Client sends token in requests:
   X-Session-Token: abc123xyz

6. Server validates token and identifies user

7. Request proceeds with authenticated user
```

**ViewSet with authentication:**

```python
from rest_framework.permissions import IsAuthenticated

class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # Requires auth

    def get_queryset(self):
        # Filter data by authenticated user
        user = self.request.user
        if user.is_staff:
            return Patient.objects.all()
        return Patient.objects.filter(hospital=user.hospital)
```

**Custom Permissions:**

```python
from rest_framework import permissions

class IsHospitalAdmin(permissions.BasePermission):
    """Only hospital admins can access"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff

class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object-level permission - only owner can edit"""

    def has_object_permission(self, request, view, obj):
        # Read permissions allowed to authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only to owner
        return obj.created_by == request.user

# Usage
class DiagnosisViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
```

**Multiple Authentication Classes:**

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',  # For browser
        'rest_framework.authentication.TokenAuthentication',     # For API
    ],
}
```

**Permission Levels:**

```python
# AllowAny - public endpoint
class PublicHospitalListView(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]

# IsAuthenticated - logged in users
class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

# IsAdminUser - staff only
class AuditLogViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAdminUser]

# Custom - complex logic
class DiagnosisViewSet(viewsets.ModelViewSet):
    permission_classes = [IsRadiologist]
```

**Role-based Authorization:**

```python
def get_permissions(self):
    """Different permissions per action"""
    if self.action == 'list':
        return [permissions.IsAuthenticated()]
    elif self.action == 'create':
        return [permissions.IsAuthenticated(), IsRadiologist()]
    elif self.action in ['update', 'destroy']:
        return [permissions.IsAdminUser()]
    return super().get_permissions()
```

**Frontend (Next.js) - Storing and sending token:**

```typescript
// Login
const login = async (email: string, password: string) => {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });

  const data = await response.json();

  // Store token
  localStorage.setItem('session_token', data.meta.session_token);

  return data;
};

// Authenticated request
const fetchPatients = async () => {
  const token = localStorage.getItem('session_token');

  const response = await fetch('/api/patients/', {
    headers: {
      'X-Session-Token': token
    }
  });

  return response.json();
};
```

This demonstrates:
- **Authentication** vs **Authorization** understanding
- **Security** implementation
- **Real-world** API patterns

---

### Q30: How do you handle errors and exceptions in Django REST Framework?

**Answer:**

**Error handling** ensures consistent API responses and good user experience.

**DRF Default Error Responses:**

```json
// 400 Bad Request
{
  "field_name": ["This field is required."],
  "email": ["Enter a valid email address."]
}

// 404 Not Found
{
  "detail": "Not found."
}

// 403 Forbidden
{
  "detail": "You do not have permission to perform this action."
}

// 500 Internal Server Error
{
  "detail": "Internal server error."
}
```

**Validation Errors:**

```python
from rest_framework import serializers

class PatientSerializer(serializers.ModelSerializer):
    def validate_age(self, value):
        """Field-level validation"""
        if value < 0 or value > 150:
            raise serializers.ValidationError("Age must be between 0 and 150")
        return value

    def validate(self, data):
        """Object-level validation"""
        if data['date_of_birth'] and data.get('age'):
            # Validate age matches DOB
            calculated_age = calculate_age(data['date_of_birth'])
            if calculated_age != data['age']:
                raise serializers.ValidationError({
                    'age': 'Age does not match date of birth'
                })
        return data
```

**Custom Exception Handler:**

```python
# utils/exception_handler.py
from rest_framework.views import exception_handler
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    """Custom exception handler for consistent error format"""

    # Call DRF's default handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Customize error response format
        custom_response = {
            'error': {
                'status_code': response.status_code,
                'message': str(exc),
                'details': response.data
            }
        }

        # Add request info for debugging
        if settings.DEBUG:
            custom_response['error']['path'] = context['request'].path
            custom_response['error']['method'] = context['request'].method

        response.data = custom_response

    return response

# settings.py
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'utils.exception_handler.custom_exception_handler'
}
```

**Custom Response:**
```json
{
  "error": {
    "status_code": 400,
    "message": "Validation failed",
    "details": {
      "medical_record_number": ["This field must start with 'MRN-'"]
    }
  }
}
```

**Raising Custom Exceptions:**

```python
from rest_framework.exceptions import APIException

class DICOMProcessingError(APIException):
    status_code = 422
    default_detail = 'DICOM file processing failed'
    default_code = 'dicom_processing_error'

# Usage in view
class DicomImageViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        try:
            # Process DICOM file
            process_dicom(request.data['file'])
        except InvalidDICOMError:
            raise DICOMProcessingError('Invalid DICOM format')
```

**Try-Except in ViewSets:**

```python
from rest_framework import status
from rest_framework.response import Response

class ImagingStudyViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        try:
            study = self.get_object()

            # Business logic
            if not study.images.exists():
                return Response(
                    {'error': 'Cannot complete study without images'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            study.status = 'completed'
            study.save()

            return Response({'status': 'completed'})

        except ImagingStudy.DoesNotExist:
            return Response(
                {'error': 'Study not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error completing study {pk}: {e}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
```

**Database Errors:**

```python
from django.db import IntegrityError

def create(self, request, *args, **kwargs):
    try:
        return super().create(request, *args, **kwargs)
    except IntegrityError as e:
        if 'unique constraint' in str(e).lower():
            return Response(
                {'error': 'Medical record number already exists'},
                status=status.HTTP_409_CONFLICT
            )
        raise
```

**Logging Errors:**

```python
import logging

logger = logging.getLogger(__name__)

class PatientViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            # Log error with context
            logger.error(
                f"Failed to create patient: {e}",
                extra={
                    'user': request.user.id,
                    'data': request.data,
                    'ip': request.META.get('REMOTE_ADDR')
                },
                exc_info=True  # Include stack trace
            )
            raise
```

**Global Error Middleware:**

```python
# middleware.py
class ErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log 4xx and 5xx errors
        if response.status_code >= 400:
            logger.warning(
                f"{request.method} {request.path} -> {response.status_code}",
                extra={
                    'status': response.status_code,
                    'user': getattr(request, 'user', None),
                    'data': request.body
                }
            )

        return response
```

**Testing Error Responses:**

```python
# tests/test_api.py
def test_create_patient_with_invalid_mrn(api_client):
    """Test that invalid MRN returns 400"""
    data = {
        'first_name': 'John',
        'last_name': 'Doe',
        'medical_record_number': 'INVALID'  # Should start with MRN-
    }

    response = api_client.post('/api/patients/', data)

    assert response.status_code == 400
    assert 'medical_record_number' in response.data
```

This demonstrates:
- **Error handling** best practices
- **User experience** focus
- **Debugging** support

---

### Q31: What is CORS? How did you configure it for your Django backend and Next.js frontend?

**Answer:**

**CORS (Cross-Origin Resource Sharing)** is a security mechanism that allows or restricts web applications from making requests to a different domain than the one serving the web page.

**The Problem (Same-Origin Policy):**

```
Frontend: http://localhost:3000 (Next.js)
Backend:  http://localhost:8000 (Django)

Different origins → Browser blocks requests by default
```

**Without CORS:**
```javascript
// Frontend makes request
fetch('http://localhost:8000/api/patients/')

// Browser error:
// "Access to fetch has been blocked by CORS policy"
```

**CORS Headers:**

```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
```

**Django Configuration:**

**1. Install django-cors-headers:**
```bash
pip install django-cors-headers
```

**2. Configure settings.py:**
```python
INSTALLED_APPS = [
    'corsheaders',  # Must be before CommonMiddleware
    'django.contrib.staticfiles',
    # ...
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # At top!
    'django.middleware.common.CommonMiddleware',
    # ...
]

# Development - Allow specific origins
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Production
CORS_ALLOWED_ORIGINS = [
    'https://myapp.com',
    'https://www.myapp.com',
]

# Allow credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS = True

# Allowed HTTP methods
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Allowed headers
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-session-token',  # Custom header for allauth
]
```

**For my project** (django-allauth headless):

```python
# Allow custom session token header
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-session-token',  # django-allauth headless uses this
]

# Must allow credentials for session-based auth
CORS_ALLOW_CREDENTIALS = True
```

**Next.js Frontend Configuration:**

```typescript
// lib/api/client.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = {
  async request(endpoint: string, options: RequestInit = {}) {
    const token = localStorage.getItem('session_token');

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      credentials: 'include',  // Send cookies/credentials
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Token': token || '',
        ...options.headers,
      },
    });

    return response;
  }
};
```

**CORS Preflight Request:**

For complex requests (POST, custom headers), browser sends OPTIONS request first:

```
1. Browser: OPTIONS /api/patients/
   Origin: http://localhost:3000
   Access-Control-Request-Method: POST
   Access-Control-Request-Headers: x-session-token

2. Server: 200 OK
   Access-Control-Allow-Origin: http://localhost:3000
   Access-Control-Allow-Methods: POST
   Access-Control-Allow-Headers: x-session-token

3. Browser: POST /api/patients/ (actual request)
```

**Django handles OPTIONS automatically** with django-cors-headers.

**Security Considerations:**

**❌ Don't do this (too permissive):**
```python
CORS_ALLOW_ALL_ORIGINS = True  # Allows ANY website!
CORS_ORIGIN_ALLOW_ALL = True   # Same as above
```

**✅ Do this (specific origins):**
```python
CORS_ALLOWED_ORIGINS = [
    'https://myapp.com',
]

# Or use regex for subdomains
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://\w+\.myapp\.com$",  # Matches *.myapp.com
]
```

**Environment-based Configuration:**

```python
# settings.py
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        'https://myapp.com',
        'https://www.myapp.com',
    ]
```

**Testing CORS:**

```bash
# Test from browser console
fetch('http://localhost:8000/api/patients/', {
  credentials: 'include',
  headers: {
    'X-Session-Token': 'your-token'
  }
})
.then(res => res.json())
.then(data => console.log(data));
```

**Common CORS Errors:**

**1. "No 'Access-Control-Allow-Origin' header"**
```
Fix: Add origin to CORS_ALLOWED_ORIGINS
```

**2. "Credentials flag is true, but Access-Control-Allow-Credentials is false"**
```python
Fix: CORS_ALLOW_CREDENTIALS = True
```

**3. "Header 'x-session-token' is not allowed"**
```python
Fix: Add to CORS_ALLOW_HEADERS
```

**4. "Method POST is not allowed"**
```python
Fix: Ensure POST in CORS_ALLOW_METHODS
```

**Debugging:**

```python
# Enable CORS logging
LOGGING = {
    'loggers': {
        'corsheaders': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

This demonstrates:
- **Web security** understanding
- **Cross-origin** communication
- **Production** configuration

---

## Celery & Async Processing

### Q32: What is Celery? Why did you use it in your medical imaging platform?

**Answer:**

**Celery** is a distributed task queue for executing asynchronous, long-running tasks outside the request-response cycle.

**Why use Celery?**

✅ **Don't block HTTP responses** - User doesn't wait for slow operations
✅ **Background processing** - Handle time-intensive tasks
✅ **Scheduled tasks** - Cron-like periodic tasks
✅ **Scalability** - Distribute work across multiple workers
✅ **Retry logic** - Automatic retry on failure
✅ **Task prioritization** - Different queues for different priorities

**Architecture:**

```
Django App (Producer)
    ↓ (publish task)
Message Broker (Redis/RabbitMQ)
    ↓ (pull task)
Celery Workers (Consumers)
    ↓ (process task)
Result Backend (Redis/Database)
```

**In my medical imaging platform**, I use Celery for:

**1. DICOM Image Processing** (`tasks.py:71-135`)

```python
@shared_task
def process_dicom_image(image_id):
    """
    Parse DICOM file, extract metadata
    Too slow to do during HTTP upload (blocks user)
    """
    image = DicomImage.objects.get(id=image_id)

    # Open file (from S3 or local storage)
    with image.image_file.open('rb') as f:
        # Parse DICOM (can take 5-30 seconds for large files)
        dataset = pydicom.dcmread(f)

        # Extract metadata
        metadata = {
            'patient_name': str(dataset.PatientName),
            'study_date': dataset.StudyDate,
            'modality': dataset.Modality,
            'rows': int(dataset.Rows),
            'columns': int(dataset.Columns),
            # ... hundreds of DICOM tags
        }

        # Update database
        image.dicom_metadata = metadata
        image.rows = metadata['rows']
        image.columns = metadata['columns']
        image.save()

    return f"Processed DICOM image {image_id}"
```

**Triggered in view** (`views.py:315-320`):

```python
def create(self, request, *args, **kwargs):
    # Save file quickly
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()

    # Process asynchronously (returns immediately)
    process_dicom_image.delay(instance.id)

    # User gets instant response
    return Response(serializer.data, status=201)
```

**2. PDF Report Generation** (`tasks.py:138-187`)

```python
@shared_task
def generate_patient_report_pdf(report_id):
    """
    Generate PDF report with diagnosis, images
    Can take 10-60 seconds depending on image count
    """
    report = PatientReport.objects.get(id=report_id)

    # Create PDF (uses ReportLab)
    pdf_buffer = generate_pdf(
        patient=report.patient,
        studies=report.studies.all(),
        diagnosis=report.diagnosis
    )

    # Save PDF to storage
    pdf_file = ContentFile(pdf_buffer.getvalue())
    report.pdf_file.save(f'report_{report_id}.pdf', pdf_file)
    report.status = 'completed'
    report.save()

    # Send email notification
    send_report_email.delay(report_id)

    return f"Generated PDF for report {report_id}"
```

**3. Email Notifications** (`tasks.py:190-210`):

```python
@shared_task(bind=True, max_retries=3)
def send_report_email(self, report_id):
    """
    Send email with PDF attachment
    Retries on failure
    """
    try:
        report = PatientReport.objects.get(id=report_id)

        send_mail(
            subject=f'Medical Report for {report.patient.full_name}',
            message='Your medical report is attached.',
            from_email='noreply@hospital.com',
            recipient_list=[report.patient.email],
            attachments=[(report.pdf_file.name, report.pdf_file.read())]
        )

    except Exception as exc:
        # Retry after 60 seconds
        raise self.retry(exc=exc, countdown=60)
```

**Configuration** (`settings.py`):

```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Task time limits
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes (warning)

# Task result expiration
CELERY_RESULT_EXPIRES = 3600  # 1 hour
```

**Celery App** (`celery.py`):

```python
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'firstproject.settings')

app = Celery('firstproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

**Running Celery:**

```bash
# Start worker
celery -A firstproject worker --loglevel=info

# Start with concurrency
celery -A firstproject worker --concurrency=4

# Start beat (for periodic tasks)
celery -A firstproject beat --loglevel=info
```

**docker-compose.yml**:

```yaml
services:
  redis:
    image: redis:7
    ports:
      - "6379:6379"

  celery_worker:
    build: .
    command: celery -A firstproject worker --loglevel=info
    depends_on:
      - redis
      - db
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0

  celery_beat:
    build: .
    command: celery -A firstproject beat --loglevel=info
    depends_on:
      - redis
```

**Task Monitoring:**

```python
# Check task status
from celery.result import AsyncResult

result = process_dicom_image.delay(123)
print(result.id)  # Task ID
print(result.state)  # PENDING, STARTED, SUCCESS, FAILURE
print(result.ready())  # True if completed
print(result.get())  # Block until complete, return result
```

**Periodic Tasks** (Celery Beat):

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-old-audit-logs': {
        'task': 'medical_imaging.tasks.cleanup_audit_logs',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'generate-daily-report': {
        'task': 'medical_imaging.tasks.generate_daily_statistics',
        'schedule': crontab(hour=0, minute=0),  # Midnight
    },
}
```

**Error Handling:**

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_dicom_image(self, image_id):
    try:
        # Process DICOM
        pass
    except SoftTimeLimitExceeded:
        # Task took too long
        logger.error(f"DICOM processing timed out for {image_id}")
        raise
    except Exception as exc:
        # Retry 3 times with 60 second delay
        logger.error(f"DICOM processing failed: {exc}")
        raise self.retry(exc=exc)
```

**Why Celery over Alternatives?**

| Solution | Use Case | Pros | Cons |
|----------|----------|------|------|
| **Celery** | Complex workflows | Feature-rich, scalable | Complex setup |
| **Django Q** | Simple tasks | Django-native | Less features |
| **RQ (Redis Queue)** | Simple tasks | Simple, Pythonic | Redis only |
| **Dramatiq** | General tasks | Modern, fast | Smaller ecosystem |

This demonstrates:
- **Async processing** understanding
- **System architecture** knowledge
- **Performance** optimization

---

### **Q33: How would you implement API versioning in Django REST Framework? Why is it important?**

**API versioning** is crucial for maintaining backward compatibility while evolving your API. It allows you to introduce breaking changes without affecting existing clients.

**Why API versioning is important:**

1. **Backward compatibility**: Old clients continue working while new features are added
2. **Gradual migration**: Clients can update at their own pace
3. **Deprecation management**: Clearly communicate which versions are ending support
4. **A/B testing**: Test new API designs without affecting production clients
5. **Mobile app compatibility**: Users may not update apps immediately

**DRF supports multiple versioning schemes:**

**1. URL Path Versioning (Most Common)**

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'VERSION_PARAM': 'version',
}

# urls.py
urlpatterns = [
    path('api/v1/', include('medical_imaging.urls')),
    path('api/v2/', include('medical_imaging.urls_v2')),
]

# Usage in views
class PatientViewSet(viewsets.ModelViewSet):
    def list(self, request):
        if request.version == 'v1':
            # Old behavior
            serializer = PatientSerializerV1(patients, many=True)
        else:
            # New behavior with additional fields
            serializer = PatientSerializerV2(patients, many=True)
        return Response(serializer.data)
```

**2. Accept Header Versioning**

```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.AcceptHeaderVersioning',
}

# Client request header:
# Accept: application/json; version=v1
```

**3. Query Parameter Versioning**

```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.QueryParameterVersioning',
}

# Request: GET /api/patients/?version=v2
```

**4. Hostname Versioning**

```python
# v1.api.example.com vs v2.api.example.com
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.HostNameVersioning',
}
```

**Real-world example - Medical Imaging API evolution:**

```python
# v1: Basic patient info
class PatientSerializerV1(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ['id', 'medical_record_number', 'full_name', 'age']

# v2: Added HIPAA-compliant audit trail
class PatientSerializerV2(serializers.ModelSerializer):
    access_log = AuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = ['id', 'medical_record_number', 'full_name', 'age',
                  'access_log', 'data_retention_date']

# views.py
class PatientViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.version == 'v1':
            return PatientSerializerV1
        return PatientSerializerV2

    def get_queryset(self):
        queryset = Patient.objects.all()
        if self.request.version == 'v2':
            # v2 includes audit logs
            queryset = queryset.prefetch_related('access_log')
        return queryset
```

**Migration strategy:**

```python
# Step 1: Add deprecation warnings to v1
@api_view(['GET'])
def old_patient_endpoint(request):
    # Add deprecation header
    response = Response(data)
    response['Warning'] = '299 - "API v1 will be deprecated on 2025-06-01. Please migrate to v2"'
    response['Sunset'] = 'Wed, 01 Jun 2025 00:00:00 GMT'  # RFC 8594
    return response

# Step 2: Support both versions during transition
# Step 3: Monitor v1 usage (log analytics)
# Step 4: Remove v1 after sunset date
```

**Comparison of versioning strategies:**

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **URL Path** | ✅ Clear, visible<br>✅ Easy to route<br>✅ Cacheable | ❌ URL proliferation | Public APIs, mobile apps |
| **Accept Header** | ✅ RESTful<br>✅ Clean URLs | ❌ Harder to test<br>❌ Not cacheable | Internal APIs |
| **Query Param** | ✅ Simple<br>✅ Easy to test | ❌ Not RESTful<br>❌ Cache issues | Quick prototypes |
| **Hostname** | ✅ Infrastructure-level control | ❌ DNS/SSL overhead | Enterprise, multi-region |

**This demonstrates:**
- Understanding of API evolution and lifecycle management
- Knowledge of DRF versioning strategies
- Practical migration planning for production systems
- Backward compatibility considerations for healthcare applications

---

### **Q34: Explain API throttling and rate limiting. How would you implement it in your Django application?**

**Throttling** controls the rate at which clients can make requests to your API, preventing abuse and ensuring fair resource allocation.

**Why throttling is critical:**

1. **Prevent abuse**: Stop malicious actors from overwhelming your server
2. **Fair usage**: Ensure all users get reasonable access
3. **Cost control**: Limit expensive operations (DICOM processing, PDF generation)
4. **SLA enforcement**: Different rate limits for free vs premium tiers
5. **Infrastructure protection**: Prevent database overload

**DRF Built-in Throttling Classes:**

**1. AnonRateThrottle** - For unauthenticated users
**2. UserRateThrottle** - For authenticated users
**3. ScopedRateThrottle** - Per-endpoint custom rates

**Implementation in Medical Imaging Platform:**

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10/hour',      # Anonymous users: 10 requests/hour
        'user': '100/hour',     # Authenticated users: 100 requests/hour
        'upload': '5/minute',   # DICOM uploads: 5 per minute
        'reports': '20/day',    # PDF reports: 20 per day
        'premium': '1000/hour', # Premium hospitals
    }
}
```

**Using throttling in views:**

```python
# views.py
from rest_framework.throttling import UserRateThrottle, ScopedRateThrottle

class UploadRateThrottle(UserRateThrottle):
    """Custom throttle for DICOM uploads"""
    scope = 'upload'

class ReportRateThrottle(UserRateThrottle):
    """Custom throttle for PDF reports"""
    scope = 'reports'

class DicomImageViewSet(viewsets.ModelViewSet):
    throttle_classes = [UploadRateThrottle]  # Apply upload throttling

    @action(detail=False, methods=['post'])
    def upload(self, request):
        # This endpoint is rate-limited to 5/minute
        file = request.FILES.get('file')
        # Process DICOM upload
        return Response({'status': 'processing'})

class PatientReportViewSet(viewsets.ViewSet):
    throttle_classes = [ReportRateThrottle]

    @action(detail=True, methods=['post'])
    def generate_pdf(self, request, pk=None):
        # This endpoint is rate-limited to 20/day
        # Expensive operation: PDF generation
        patient = Patient.objects.get(pk=pk)
        # Trigger Celery task
        task = generate_patient_report_pdf.delay(patient.id)
        return Response({'task_id': task.id})
```

**Custom throttling based on hospital tier:**

```python
# throttles.py
from rest_framework.throttling import UserRateThrottle

class HospitalTierThrottle(UserRateThrottle):
    """
    Different rate limits based on hospital subscription tier
    """
    def get_rate(self):
        user = self.request.user
        if not user.is_authenticated:
            return '10/hour'

        try:
            hospital = user.hospital  # Assuming user has hospital FK
            if hospital.subscription_tier == 'premium':
                return '1000/hour'
            elif hospital.subscription_tier == 'standard':
                return '100/hour'
            else:
                return '50/hour'  # Free tier
        except:
            return '100/hour'  # Default

    def get_cache_key(self, request, view):
        # Cache key based on hospital, not just user
        if request.user.is_authenticated:
            ident = request.user.hospital.id
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

# views.py
class ImagingStudyViewSet(viewsets.ModelViewSet):
    throttle_classes = [HospitalTierThrottle]
```

**Handling throttle responses:**

When a client exceeds the rate limit, DRF returns:

```
HTTP 429 Too Many Requests
Retry-After: 3600
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640995200

{
    "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

**Frontend handling (Next.js):**

```typescript
// lib/api/client.ts
export async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    credentials: 'include',
  });

  if (response.status === 429) {
    const retryAfter = response.headers.get('Retry-After');
    throw new Error(`Rate limit exceeded. Retry after ${retryAfter} seconds.`);
  }

  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }

  return response.json();
}

// Component usage with retry logic
const handleUpload = async (file: File) => {
  try {
    await uploadDicomImage(file);
  } catch (error) {
    if (error.message.includes('Rate limit')) {
      toast.error('Upload limit reached. Please wait before uploading again.');
    }
  }
};
```

**Redis-based throttling for distributed systems:**

```python
# For production with multiple servers, use Redis cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# DRF automatically uses this cache for throttling
```

**Monitoring throttled requests:**

```python
# middleware.py
class ThrottleLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code == 429:
            logger.warning(
                f"Throttled request: {request.user} - {request.path}",
                extra={
                    'user': request.user.id,
                    'ip': request.META.get('REMOTE_ADDR'),
                    'endpoint': request.path
                }
            )
        return response
```

**Alternative throttling solutions:**

| Solution | Use Case |
|----------|----------|
| **DRF Throttling** | Simple API rate limiting, per-user limits |
| **Django Ratelimit** | View-level limiting, IP-based blocking |
| **Nginx rate limiting** | Infrastructure-level, protects against DDoS |
| **Cloudflare** | CDN-level, protects entire application |
| **Kong/API Gateway** | Microservices, complex routing rules |

**This demonstrates:**
- Understanding of API security and resource management
- Knowledge of DRF throttling mechanisms
- Ability to implement tier-based pricing/access control
- Production-ready rate limiting for healthcare applications

---

### **Q35: What are some strategies for API caching? How would you implement caching in your medical imaging API?**

**API caching** stores responses to reduce database queries, improve response times, and decrease server load. However, in **medical applications**, caching requires careful consideration due to **data sensitivity and compliance**.

**Caching strategies:**

**1. HTTP Caching (Browser/CDN level)**
**2. View-level caching (Django cache framework)**
**3. Query-level caching (ORM optimization)**
**4. Application-level caching (Redis/Memcached)**

**HTTP caching with Cache-Control headers:**

```python
# views.py
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.utils.cache import patch_cache_control

class HospitalViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Hospital data changes infrequently - safe to cache
    """
    queryset = Hospital.objects.all()
    serializer_class = HospitalSerializer

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Add cache headers
        patch_cache_control(response, max_age=900, public=True)
        return response

# Generated response headers:
# Cache-Control: max-age=900, public
# This tells browsers and CDNs they can cache this response
```

**Per-user caching (session-based):**

```python
from django.core.cache import cache

class PatientViewSet(viewsets.ModelViewSet):
    """
    Patient data is sensitive - use private caching
    """

    def list(self, request):
        user_id = request.user.id
        cache_key = f'patient_list_user_{user_id}'

        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        # Not in cache - query database
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        # Cache for 5 minutes (short TTL for medical data)
        cache.set(cache_key, data, timeout=300)

        # Set private cache header (don't cache in CDN)
        response = Response(data)
        patch_cache_control(response, private=True, max_age=300)
        return response
```

**Conditional requests with ETags:**

```python
from django.views.decorators.http import condition
from django.utils.http import http_date

class ImagingStudyViewSet(viewsets.ModelViewSet):

    def retrieve(self, request, pk=None):
        study = self.get_object()

        # Generate ETag based on last modified time
        etag = f'"{study.updated_at.timestamp()}"'
        last_modified = study.updated_at

        # Check if client has current version
        if request.META.get('HTTP_IF_NONE_MATCH') == etag:
            return Response(status=304)  # Not Modified

        serializer = self.get_serializer(study)
        response = Response(serializer.data)

        # Add ETag and Last-Modified headers
        response['ETag'] = etag
        response['Last-Modified'] = http_date(last_modified.timestamp())
        return response

# Client request:
# GET /api/studies/123/
# If-None-Match: "1640995200.0"
#
# Server response (if not modified):
# HTTP 304 Not Modified
# (No body sent - saves bandwidth)
```

**Redis caching for expensive queries:**

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'medical_imaging',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# views.py
from django.core.cache import cache
from django.db.models import Count, Avg

class DashboardStatsView(APIView):
    """
    Dashboard statistics - expensive aggregation queries
    """

    def get(self, request):
        hospital_id = request.user.hospital.id
        cache_key = f'dashboard_stats_hospital_{hospital_id}'

        # Try cache first
        stats = cache.get(cache_key)

        if not stats:
            # Expensive query - aggregates across millions of records
            stats = {
                'total_patients': Patient.objects.filter(hospital_id=hospital_id).count(),
                'total_studies': ImagingStudy.objects.filter(hospital_id=hospital_id).count(),
                'avg_images_per_study': ImagingStudy.objects.filter(
                    hospital_id=hospital_id
                ).aggregate(avg=Avg('images__id'))['avg'],
                'studies_by_modality': list(
                    ImagingStudy.objects.filter(hospital_id=hospital_id)
                    .values('modality')
                    .annotate(count=Count('id'))
                ),
            }

            # Cache for 10 minutes
            cache.set(cache_key, stats, timeout=600)

        return Response(stats)
```

**Cache invalidation (critical for medical data):**

```python
# models.py
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Patient)
@receiver(post_delete, sender=Patient)
def invalidate_patient_cache(sender, instance, **kwargs):
    """
    Invalidate cache when patient data changes
    """
    # Clear specific patient cache
    cache.delete(f'patient_{instance.id}')

    # Clear hospital's patient list cache
    cache.delete(f'patient_list_hospital_{instance.hospital.id}')

    # Clear dashboard stats
    cache.delete(f'dashboard_stats_hospital_{instance.hospital.id}')

@receiver(post_save, sender=ImagingStudy)
def invalidate_study_cache(sender, instance, **kwargs):
    """
    When a study is created/updated, invalidate related caches
    """
    # Clear patient's studies cache
    cache.delete(f'patient_studies_{instance.patient.id}')

    # Clear dashboard stats
    cache.delete(f'dashboard_stats_hospital_{instance.hospital.id}')
```

**What NOT to cache in medical applications:**

❌ **Never cache:**
- Real-time patient vital signs
- Diagnostic results (until confirmed)
- Prescription data
- Audit logs
- Authentication tokens

✅ **Safe to cache (with short TTL):**
- Hospital information
- User profiles
- Dashboard statistics
- DICOM metadata (after processing)
- Static reference data (modalities, body parts)

**Frontend caching with React Query (already implemented):**

```typescript
// frontend/lib/hooks/usePatients.ts
import { useQuery } from '@tanstack/react-query';

export const usePatients = (params?: PatientQueryParams) => {
  return useQuery({
    queryKey: ['patients', params],
    queryFn: () => patientService.getAll(params),
    staleTime: 5 * 60 * 1000,  // Consider data fresh for 5 minutes
    cacheTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
    // Automatically refetch when window regains focus
    refetchOnWindowFocus: true,
  });
};

// React Query automatically:
// 1. Caches query results
// 2. Deduplicates requests
// 3. Background refetching
// 4. Optimistic updates
```

**Comparison of caching strategies:**

| Strategy | Speed | Complexity | Best For |
|----------|-------|------------|----------|
| **HTTP Cache** | ⚡⚡⚡ | Low | Static content, public data |
| **Django Cache** | ⚡⚡ | Medium | Dynamic data, per-user |
| **Redis** | ⚡⚡⚡ | Medium | High-traffic, distributed |
| **React Query** | ⚡⚡⚡ | Low | Frontend, real-time UX |

**This demonstrates:**
- Understanding of multi-layer caching strategies
- HIPAA compliance awareness (private data handling)
- Cache invalidation strategies for data consistency
- Performance optimization for high-traffic medical systems

---

### **Q36: How do you handle real-time updates and webhooks in a REST API?**

While **REST is stateless**, real-time features are often needed in medical applications (new study uploads, diagnosis updates, alert notifications). Here are several approaches:

**1. Polling (Simplest)**

Client periodically requests updates:

```typescript
// frontend/lib/hooks/useRealtimeStudies.ts
import { useQuery } from '@tanstack/react-query';

export const useRealtimeStudies = (patientId: number) => {
  return useQuery({
    queryKey: ['studies', patientId],
    queryFn: () => studyService.getByPatient(patientId),
    refetchInterval: 10000,  // Poll every 10 seconds
    // Stop polling when window not visible
    refetchIntervalInBackground: false,
  });
};
```

**Pros:** Simple, works everywhere  
**Cons:** Inefficient, high server load, not truly real-time

**2. Long Polling**

Server holds request open until new data arrives:

```python
# views.py
from django.http import JsonResponse
import time

class StudyUpdatesView(APIView):
    def get(self, request, patient_id):
        last_check = request.GET.get('since')
        timeout = 30  # Hold for max 30 seconds
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check for new studies
            new_studies = ImagingStudy.objects.filter(
                patient_id=patient_id,
                created_at__gt=last_check
            )

            if new_studies.exists():
                serializer = ImagingStudySerializer(new_studies, many=True)
                return JsonResponse({
                    'studies': serializer.data,
                    'timestamp': timezone.now().isoformat()
                })

            time.sleep(1)  # Check every second

        # Timeout - return empty
        return JsonResponse({'studies': [], 'timestamp': timezone.now().isoformat()})
```

**3. Server-Sent Events (SSE)**

Server pushes updates to client over HTTP:

```python
# views.py
from django.http import StreamingHttpResponse
import json

class StudyUpdatesStreamView(APIView):
    def get(self, request, patient_id):
        def event_stream():
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"

            last_check = timezone.now()
            while True:
                # Check for new studies
                new_studies = ImagingStudy.objects.filter(
                    patient_id=patient_id,
                    created_at__gt=last_check
                ).order_by('-created_at')

                if new_studies.exists():
                    for study in new_studies:
                        data = ImagingStudySerializer(study).data
                        yield f"data: {json.dumps(data)}\n\n"
                    last_check = timezone.now()

                time.sleep(5)  # Check every 5 seconds

        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

# Frontend usage
const eventSource = new EventSource('/api/studies/123/stream/');
eventSource.onmessage = (event) => {
  const study = JSON.parse(event.data);
  console.log('New study:', study);
};
```

**4. WebSockets (Best for real-time)**

Bi-directional communication using Django Channels:

```python
# Install: pip install channels channels-redis

# settings.py
INSTALLED_APPS += ['channels']

ASGI_APPLICATION = 'firstproject.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('redis', 6379)],
        },
    },
}

# consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class StudyUpdateConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.patient_id = self.scope['url_route']['kwargs']['patient_id']
        self.room_group_name = f'patient_{self.patient_id}_studies'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def study_update(self, event):
        # Send message to WebSocket
        await self.send_json({
            'type': 'study_update',
            'study': event['study']
        })

# routing.py
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/patients/<int:patient_id>/studies/', consumers.StudyUpdateConsumer.as_asgi()),
]

# Send updates when study created (signals.py)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@receiver(post_save, sender=ImagingStudy)
def notify_study_update(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'patient_{instance.patient.id}_studies',
            {
                'type': 'study_update',
                'study': ImagingStudySerializer(instance).data
            }
        )
```

**Frontend WebSocket client:**

```typescript
// frontend/lib/hooks/useStudyWebSocket.ts
import { useEffect, useState } from 'react';

export const useStudyWebSocket = (patientId: number) => {
  const [studies, setStudies] = useState<Study[]>([]);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/patients/${patientId}/studies/`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'study_update') {
        setStudies(prev => [data.study, ...prev]);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => ws.close();
  }, [patientId]);

  return studies;
};

// Usage in component
const StudyList = ({ patientId }) => {
  const realtimeStudies = useStudyWebSocket(patientId);

  return (
    <div>
      {realtimeStudies.map(study => (
        <StudyCard key={study.id} study={study} />
      ))}
    </div>
  );
};
```

**5. Webhooks (Server-to-Server)**

Your API sends HTTP POST to client's endpoint when events occur:

```python
# models.py
class WebhookSubscription(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50)  # 'study.created', 'diagnosis.completed'
    callback_url = models.URLField()
    secret = models.CharField(max_length=100)  # For signature verification
    is_active = models.BooleanField(default=True)

# tasks.py
import hmac
import hashlib
import requests

@shared_task
def send_webhook(subscription_id, event_type, payload):
    """
    Send webhook to subscriber
    """
    subscription = WebhookSubscription.objects.get(id=subscription_id)

    # Create HMAC signature for security
    signature = hmac.new(
        subscription.secret.encode(),
        json.dumps(payload).encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': signature,
        'X-Event-Type': event_type,
    }

    try:
        response = requests.post(
            subscription.callback_url,
            json=payload,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"Webhook sent successfully to {subscription.callback_url}")
    except Exception as e:
        logger.error(f"Webhook failed: {str(e)}")
        # Retry logic here

# Trigger webhook on study creation
@receiver(post_save, sender=ImagingStudy)
def trigger_study_webhook(sender, instance, created, **kwargs):
    if created:
        subscriptions = WebhookSubscription.objects.filter(
            hospital=instance.hospital,
            event_type='study.created',
            is_active=True
        )

        payload = {
            'event': 'study.created',
            'study_id': instance.id,
            'patient_id': instance.patient.id,
            'timestamp': instance.created_at.isoformat()
        }

        for sub in subscriptions:
            send_webhook.delay(sub.id, 'study.created', payload)
```

**Webhook receiver (client side):**

```python
# Client's endpoint
@csrf_exempt
def receive_webhook(request):
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()

    if signature != expected_signature:
        return JsonResponse({'error': 'Invalid signature'}, status=403)

    # Process event
    data = json.loads(request.body)
    if data['event'] == 'study.created':
        # Handle new study
        process_new_study(data['study_id'])

    return JsonResponse({'status': 'received'})
```

**Comparison:**

| Method | Latency | Complexity | Server Load | Use Case |
|--------|---------|------------|-------------|----------|
| **Polling** | High (5-60s) | Low | High | Simple updates, low traffic |
| **Long Polling** | Medium (1-5s) | Medium | Medium | Moderate real-time needs |
| **SSE** | Low (<1s) | Medium | Medium | Server→Client only (notifications) |
| **WebSockets** | Very Low (<100ms) | High | Low | True real-time (chat, collaboration) |
| **Webhooks** | N/A | Medium | Low | Server-to-server integration |

**For the medical imaging platform:**
- **Dashboard stats**: Polling every 30s
- **New study notifications**: SSE or WebSockets
- **PACS integration**: Webhooks
- **Radiology collaboration**: WebSockets

**This demonstrates:**
- Understanding of real-time communication patterns
- Knowledge of WebSocket/Channels implementation
- Webhook security (HMAC signatures)
- Trade-offs between different approaches

---

## 5. Celery & Async Processing

### **Q37: How do you debug and monitor Celery tasks in production?**

**Debugging and monitoring Celery** is critical in production, especially for medical imaging where tasks process patient data and generate reports.

**1. Celery Flower (Real-time Monitoring)**

Flower is a web-based monitoring tool for Celery:

```bash
# Install Flower
pip install flower

# Run Flower
celery -A firstproject flower --port=5555

# Access at: http://localhost:5555
```

**Flower provides:**
- Task progress and status
- Worker statistics
- Real-time task execution graphs
- Task history and results
- Worker pool size and active tasks
- Task revocation and termination

**Docker Compose integration:**

```yaml
# docker-compose.yml
services:
  flower:
    build: .
    command: celery -A firstproject flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      - redis
      - celery_worker
```

**2. Logging Task Progress**

```python
# tasks.py
import logging
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(bind=True)
def process_dicom_image(self, image_id):
    """
    Process DICOM image with progress tracking
    """
    logger.info(f"Starting DICOM processing for image {image_id}")

    try:
        image = DicomImage.objects.get(id=image_id)

        # Update progress (available in Flower)
        self.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 5, 'status': 'Downloading file...'}
        )

        # Step 1: Download file
        logger.debug(f"Downloading file from {image.file_path}")
        # Process...

        self.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 5, 'status': 'Parsing DICOM tags...'}
        )

        # Step 2: Parse DICOM
        ds = pydicom.dcmread(image.file_path)
        logger.info(f"Parsed DICOM tags for {image_id}")

        self.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 5, 'status': 'Extracting metadata...'}
        )

        # Step 3: Extract metadata
        image.metadata = {
            'PatientName': str(ds.PatientName),
            'StudyDate': str(ds.StudyDate),
            'Modality': str(ds.Modality),
        }
        image.save()

        logger.info(f"DICOM processing completed for image {image_id}")

        return {
            'status': 'success',
            'image_id': image_id,
            'metadata': image.metadata
        }

    except Exception as exc:
        logger.error(f"DICOM processing failed for image {image_id}: {exc}", exc_info=True)
        raise
```

**3. Monitoring Task Results**

```python
# views.py
from celery.result import AsyncResult

class TaskStatusView(APIView):
    """
    Check task status for frontend polling
    """
    def get(self, request, task_id):
        task_result = AsyncResult(task_id)

        response_data = {
            'task_id': task_id,
            'state': task_result.state,
            'result': task_result.result,
        }

        # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
        if task_result.state == 'PROGRESS':
            # Custom progress state
            response_data.update({
                'current': task_result.info.get('current', 0),
                'total': task_result.info.get('total', 1),
                'status': task_result.info.get('status', ''),
            })
        elif task_result.state == 'FAILURE':
            # Task failed - get exception
            response_data['error'] = str(task_result.info)

        return Response(response_data)
```

**Frontend polling for task progress:**

```typescript
// frontend/lib/hooks/useTaskStatus.ts
import { useQuery } from '@tanstack/react-query';

export const useTaskStatus = (taskId: string) => {
  return useQuery({
    queryKey: ['task', taskId],
    queryFn: async () => {
      const response = await fetch(`/api/tasks/${taskId}/status/`);
      return response.json();
    },
    refetchInterval: (data) => {
      // Stop polling when task completes or fails
      if (data?.state === 'SUCCESS' || data?.state === 'FAILURE') {
        return false;
      }
      return 2000; // Poll every 2 seconds
    },
    enabled: !!taskId,
  });
};

// Component usage
const DicomUpload = () => {
  const [taskId, setTaskId] = useState<string | null>(null);
  const { data: taskStatus } = useTaskStatus(taskId);

  const handleUpload = async (file: File) => {
    const response = await uploadDicom(file);
    setTaskId(response.task_id);
  };

  return (
    <div>
      {taskStatus?.state === 'PROGRESS' && (
        <ProgressBar 
          current={taskStatus.current} 
          total={taskStatus.total}
          status={taskStatus.status}
        />
      )}
      {taskStatus?.state === 'SUCCESS' && <p>Upload complete!</p>}
      {taskStatus?.state === 'FAILURE' && <p>Error: {taskStatus.error}</p>}
    </div>
  );
};
```

**4. Celery Events and Monitoring**

```python
# management/commands/monitor_celery.py
from django.core.management.base import BaseCommand
from celery import Celery
from celery.events import EventReceiver

class Command(BaseCommand):
    help = 'Monitor Celery events in real-time'

    def handle(self, *args, **options):
        app = Celery('firstproject')
        app.config_from_object('django.conf:settings', namespace='CELERY')

        def on_task_sent(event):
            self.stdout.write(f"Task sent: {event['uuid']}")

        def on_task_started(event):
            self.stdout.write(f"Task started: {event['uuid']}")

        def on_task_succeeded(event):
            self.stdout.write(
                self.style.SUCCESS(f"Task succeeded: {event['uuid']} - Result: {event['result']}")
            )

        def on_task_failed(event):
            self.stdout.write(
                self.style.ERROR(f"Task failed: {event['uuid']} - Exception: {event['exception']}")
            )

        with app.connection() as connection:
            recv = EventReceiver(connection, handlers={
                'task-sent': on_task_sent,
                'task-started': on_task_started,
                'task-succeeded': on_task_succeeded,
                'task-failed': on_task_failed,
            })
            recv.capture(limit=None, timeout=None, wakeup=True)
```

**5. Structured Logging with ELK Stack**

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/celery/tasks.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
        },
    },
    'loggers': {
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'medical_imaging.tasks': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
    },
}

# tasks.py - Structured logging
logger.info(
    "DICOM processing started",
    extra={
        'image_id': image_id,
        'hospital_id': image.hospital.id,
        'file_size': image.file_size,
        'task_id': self.request.id,
    }
)
```

**6. Dead Letter Queue for Failed Tasks**

```python
# tasks.py
from celery import Task

class CallbackTask(Task):
    """
    Custom task class that logs failures
    """
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails after all retries
        """
        logger.error(
            f'Task {self.name} failed permanently',
            extra={
                'task_id': task_id,
                'exception': str(exc),
                'args': args,
                'kwargs': kwargs,
            }
        )

        # Store in database for manual review
        FailedTask.objects.create(
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            exception=str(exc),
            traceback=str(einfo),
        )

@shared_task(base=CallbackTask, bind=True, max_retries=3)
def process_dicom_image(self, image_id):
    # Task implementation
    pass
```

**7. Performance Metrics**

```python
# tasks.py
import time
from django.core.cache import cache

@shared_task(bind=True)
def process_dicom_image(self, image_id):
    start_time = time.time()

    try:
        # Processing logic
        result = process_image(image_id)

        # Record metrics
        duration = time.time() - start_time
        cache.incr('dicom_processing_count')
        cache.set(f'dicom_processing_last_duration', duration)

        logger.info(f"DICOM processing took {duration:.2f}s", extra={
            'duration': duration,
            'image_id': image_id,
        })

        return result
    except Exception as exc:
        cache.incr('dicom_processing_errors')
        raise
```

**Monitoring Checklist:**

✅ **Must monitor:**
- Task success/failure rates
- Task execution time
- Queue length and lag
- Worker health and resource usage
- Failed task count and reasons

✅ **Alerts to set up:**
- Queue depth > 1000 tasks
- Worker down for > 5 minutes
- Task failure rate > 5%
- Task execution time > 5 minutes
- Memory usage > 80%

**This demonstrates:**
- Production-ready Celery monitoring
- Task progress tracking for UX
- Structured logging for debugging
- Error handling and dead letter queues
- Performance metrics collection

---

### **Q38: What are Celery chains, groups, chords, and how would you use them in a medical imaging workflow? (ADVANCED)**

**Celery workflows** allow complex task orchestration. This is a **tricky interview question** because many developers know basic Celery but not workflow primitives.

**1. Chain - Sequential execution**

Tasks execute one after another, passing results:

```python
from celery import chain

# Scenario: DICOM upload → Parse → Extract metadata → Generate thumbnail
result = chain(
    upload_dicom.s(file_path),          # Step 1: Upload
    parse_dicom.s(),                     # Step 2: Parse (gets upload result)
    extract_metadata.s(),                # Step 3: Extract
    generate_thumbnail.s(),              # Step 4: Generate thumb
).apply_async()

# Equivalent shorthand
(upload_dicom.s(file_path) | parse_dicom.s() | extract_metadata.s() | generate_thumbnail.s()).apply_async()
```

**Real implementation:**

```python
# tasks.py
@shared_task
def upload_dicom(file_path):
    """Step 1: Upload file to S3"""
    s3_url = upload_to_s3(file_path)
    return {'s3_url': s3_url}

@shared_task
def parse_dicom(upload_result):
    """Step 2: Parse DICOM from S3"""
    s3_url = upload_result['s3_url']
    ds = pydicom.dcmread(s3_url)
    return {
        's3_url': s3_url,
        'patient_id': str(ds.PatientID),
        'study_date': str(ds.StudyDate),
    }

@shared_task
def extract_metadata(parse_result):
    """Step 3: Store metadata in database"""
    DicomImage.objects.create(
        file_path=parse_result['s3_url'],
        patient_id=parse_result['patient_id'],
        study_date=parse_result['study_date'],
    )
    return parse_result

@shared_task
def generate_thumbnail(metadata_result):
    """Step 4: Generate thumbnail"""
    # Generate and store thumbnail
    return {'status': 'complete'}
```

**2. Group - Parallel execution**

Execute multiple tasks in parallel, wait for all to complete:

```python
from celery import group

# Scenario: Process multiple DICOM images in parallel
job = group(
    process_dicom_image.s(1),
    process_dicom_image.s(2),
    process_dicom_image.s(3),
)
result = job.apply_async()

# Wait for all to complete
result.get()  # [result1, result2, result3]

# Or dynamically
study = ImagingStudy.objects.get(pk=study_id)
images = study.images.all()

job = group(process_dicom_image.s(img.id) for img in images)
result = job.apply_async()
```

**3. Chord - Group + Callback**

**TRICKY CONCEPT:** A chord runs tasks in parallel (like group), then executes a callback with all results.

```python
from celery import chord

# Scenario: Process all images in a study, then generate study report

# Process images in parallel, then aggregate results
workflow = chord(
    # Header: Parallel tasks
    (process_dicom_image.s(img.id) for img in images),
    # Callback: Runs after ALL tasks complete
    generate_study_report.s(study_id),
)
result = workflow.apply_async()
```

**Real-world medical imaging workflow:**

```python
# tasks.py
@shared_task
def process_dicom_image(image_id):
    """Process individual DICOM image"""
    image = DicomImage.objects.get(id=image_id)
    ds = pydicom.dcmread(image.file_path)

    # Extract metadata
    metadata = {
        'instance_number': int(ds.InstanceNumber),
        'slice_location': float(ds.SliceLocation),
        'pixel_data_size': len(ds.PixelData),
    }

    image.metadata = metadata
    image.status = 'processed'
    image.save()

    return {
        'image_id': image_id,
        'metadata': metadata
    }

@shared_task
def generate_study_report(results, study_id):
    """
    Callback: Generate report after all images processed
    Args:
        results: List of results from all process_dicom_image tasks
        study_id: Study ID passed to chord
    """
    study = ImagingStudy.objects.get(pk=study_id)

    # Aggregate results
    total_images = len(results)
    total_size = sum(r['metadata']['pixel_data_size'] for r in results)

    # Update study
    study.total_images = total_images
    study.total_size_bytes = total_size
    study.status = 'completed'
    study.save()

    # Generate PDF report
    pdf_path = create_study_pdf(study)

    return {
        'study_id': study_id,
        'report_path': pdf_path,
        'images_processed': total_images
    }

# views.py
@action(detail=True, methods=['post'])
def process_study(self, request, pk=None):
    """
    Endpoint to trigger study processing
    """
    study = self.get_object()
    images = study.images.all()

    # Create chord workflow
    workflow = chord(
        (process_dicom_image.s(img.id) for img in images),
        generate_study_report.s(study.id),  # Callback
    )

    result = workflow.apply_async()

    return Response({
        'task_id': result.id,
        'status': 'processing',
        'total_images': images.count()
    })
```

**4. Map - Apply same task to multiple arguments**

```python
from celery import group

# Scenario: Send email to multiple doctors about study completion
emails = ['doctor1@hospital.com', 'doctor2@hospital.com', 'doctor3@hospital.com']

# Instead of manually creating group
job = group(send_email.s(email, study_id) for email in emails)

# Use map
from celery import map
job = send_email.map(emails)
result = job.apply_async()
```

**5. Starmap - Map with multiple arguments**

```python
# Scenario: Process images with different compression levels
args = [
    (1, 'high'),
    (2, 'medium'),
    (3, 'low'),
]

from celery import starmap
job = process_image.starmap(args)
result = job.apply_async()
```

**6. Complex workflow: Patient report generation (ADVANCED)**

```python
# Scenario: Generate comprehensive patient report
# 1. Fetch patient data (parallel)
# 2. Generate sections (parallel)
# 3. Compile final PDF (sequential)

from celery import chain, group, chord

def generate_patient_report(patient_id):
    """
    Complex workflow:
    - Fetch studies, diagnoses, images in parallel
    - Generate report sections in parallel
    - Combine into final PDF
    """

    # Step 1: Fetch data in parallel
    fetch_data = group(
        fetch_patient_studies.s(patient_id),
        fetch_patient_diagnoses.s(patient_id),
        fetch_patient_images.s(patient_id),
    )

    # Step 2: Generate sections in parallel (after data fetched)
    # Then combine into PDF
    workflow = chain(
        fetch_data,
        chord(
            [
                generate_demographics_section.s(patient_id),
                generate_studies_section.s(),
                generate_diagnoses_section.s(),
                generate_images_section.s(),
            ],
            combine_pdf_sections.s(patient_id),  # Callback
        ),
        send_report_email.s(patient_id),  # Final step
    )

    result = workflow.apply_async()
    return result.id

# tasks.py
@shared_task
def fetch_patient_studies(patient_id):
    studies = ImagingStudy.objects.filter(patient_id=patient_id)
    return {'studies': list(studies.values())}

@shared_task
def generate_demographics_section(data, patient_id):
    patient = Patient.objects.get(pk=patient_id)
    pdf = create_demographics_pdf(patient)
    return {'section': 'demographics', 'path': pdf}

@shared_task
def combine_pdf_sections(sections, patient_id):
    """
    Callback that receives all section results
    """
    from PyPDF2 import PdfMerger

    merger = PdfMerger()
    for section in sections:
        merger.append(section['path'])

    output_path = f'/reports/patient_{patient_id}_full_report.pdf'
    merger.write(output_path)
    merger.close()

    return {
        'patient_id': patient_id,
        'report_path': output_path
    }

@shared_task
def send_report_email(pdf_result, patient_id):
    patient = Patient.objects.get(pk=patient_id)
    send_email_with_attachment(
        to=patient.email,
        subject='Your Medical Report',
        attachment=pdf_result['report_path']
    )
    return {'status': 'email_sent'}
```

**7. Error handling in workflows (TRICKY)**

```python
# Problem: If one task in a chord fails, what happens?
# Answer: The chord callback DOES NOT execute!

# Solution: Use errback
from celery import Task

class ErrorHandlingTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Log failure
        logger.error(f"Task failed: {task_id}")

        # Notify via email
        send_admin_alert(f"Task {task_id} failed: {exc}")

@shared_task(base=ErrorHandlingTask, bind=True)
def risky_task(self, arg):
    # Task that might fail
    pass

# Or use link_error
task.apply_async(link_error=handle_error_task.s())
```

**8. Canvas workflow visualization (ADVANCED CONCEPT)**

```python
# Question: What's the difference between these two?

# Option A: Chain inside group
group(
    chain(task1.s(), task2.s()),
    chain(task3.s(), task4.s()),
)

# Option B: Group inside chain
chain(
    group(task1.s(), task2.s()),
    group(task3.s(), task4.s()),
)

# Answer:
# A: Runs [task1→task2] and [task3→task4] IN PARALLEL
# B: Runs [task1, task2] in parallel, WAITS, then runs [task3, task4] in parallel
```

**Common pitfalls (TRICKY):**

❌ **Problem 1: Passing objects instead of IDs**
```python
# Wrong: Can't pickle model instances
task.delay(patient_obj)

# Correct: Pass ID
task.delay(patient_obj.id)
```

❌ **Problem 2: Forgetting .s() signature**
```python
# Wrong: This executes immediately!
chain(task1(), task2())

# Correct: Use .s() to create signature
chain(task1.s(), task2.s())
```

❌ **Problem 3: Chord callback signature**
```python
# Wrong: Callback doesn't receive header results
@shared_task
def callback(study_id):  # Missing results argument!
    pass

# Correct
@shared_task
def callback(results, study_id):  # results from header
    pass
```

**This demonstrates:**
- Deep understanding of Celery workflow primitives
- Complex task orchestration
- Real-world medical imaging pipeline
- Error handling in distributed systems
- Common pitfalls and gotchas

---

### **Q39: Explain the difference between Celery beat, crontab, and periodic tasks. How would you implement scheduled tasks? (TRICKY)**

**This is a tricky question** because candidates often confuse Celery Beat (the scheduler) with cron (Unix scheduler) and periodic tasks (the scheduled work itself).

**Key distinction:**
- **Cron**: Unix-level scheduler (runs at OS level)
- **Celery Beat**: Celery's scheduler (runs as a separate process)
- **Periodic Tasks**: The actual scheduled tasks (configured in code or database)

**1. Celery Beat Architecture**

```
┌─────────────────┐
│  Celery Beat    │ ← Scheduler process (only ONE should run)
│   (Scheduler)   │
└────────┬────────┘
         │ Sends tasks at scheduled times
         ↓
┌─────────────────┐
│   Redis Broker  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Celery Workers  │ ← Execute tasks
└─────────────────┘
```

**Important:** Only run ONE instance of celery beat, or tasks will be duplicated!

**2. Defining periodic tasks in code**

```python
# firstproject/celery.py
from celery import Celery
from celery.schedules import crontab

app = Celery('firstproject')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Define periodic tasks
app.conf.beat_schedule = {
    # Task 1: Clean up old audit logs every day at midnight
    'cleanup-audit-logs': {
        'task': 'medical_imaging.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=0, minute=0),  # Midnight daily
        'options': {'expires': 3600},  # Task expires after 1 hour
    },

    # Task 2: Generate daily hospital reports at 6 AM
    'generate-daily-reports': {
        'task': 'medical_imaging.tasks.generate_daily_hospital_reports',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'reports'},  # Route to specific queue
    },

    # Task 3: Check DICOM processing status every 10 minutes
    'check-processing-status': {
        'task': 'medical_imaging.tasks.check_dicom_processing_status',
        'schedule': 600.0,  # Every 10 minutes (in seconds)
    },

    # Task 4: Send pending reports every Monday at 9 AM
    'send-weekly-reports': {
        'task': 'medical_imaging.tasks.send_weekly_reports',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday
    },

    # Task 5: Archive old studies every month
    'archive-old-studies': {
        'task': 'medical_imaging.tasks.archive_old_studies',
        'schedule': crontab(0, 0, day_of_month='1'),  # 1st of month
    },
}
```

**3. Crontab expressions (TRICKY SYNTAX)**

```python
from celery.schedules import crontab

# Every minute
crontab()

# Every hour at 23 minutes
crontab(minute=23)

# Every day at midnight
crontab(hour=0, minute=0)

# Every Monday at 7:30 AM
crontab(hour=7, minute=30, day_of_week=1)

# Every weekday (Mon-Fri) at 5 PM
crontab(hour=17, minute=0, day_of_week='1-5')

# First day of every month at midnight
crontab(hour=0, minute=0, day_of_month='1')

# Every 10 minutes
crontab(minute='*/10')

# Multiple days: Monday, Wednesday, Friday
crontab(hour=9, minute=0, day_of_week='1,3,5')

# Last day of month (NOT directly supported - use conditional in task)
# Workaround: Run daily and check if tomorrow is next month
```

**4. Task implementations**

```python
# tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def cleanup_old_audit_logs():
    """
    Delete audit logs older than 90 days (HIPAA compliance)
    """
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count, _ = AuditLog.objects.filter(
        timestamp__lt=cutoff_date
    ).delete()

    logger.info(f"Deleted {deleted_count} audit logs older than {cutoff_date}")
    return {'deleted': deleted_count}

@shared_task
def generate_daily_hospital_reports():
    """
    Generate reports for each hospital summarizing yesterday's activity
    """
    yesterday = timezone.now() - timedelta(days=1)
    hospitals = Hospital.objects.filter(is_active=True)

    reports_generated = 0
    for hospital in hospitals:
        studies_count = ImagingStudy.objects.filter(
            hospital=hospital,
            created_at__date=yesterday.date()
        ).count()

        if studies_count > 0:
            # Generate report
            report = create_hospital_report(hospital, yesterday)
            send_report_email(hospital.contact_email, report)
            reports_generated += 1

    return {'reports_generated': reports_generated}

@shared_task
def check_dicom_processing_status():
    """
    Check for stuck DICOM processing tasks
    Alert if any image has been processing for > 30 minutes
    """
    stuck_threshold = timezone.now() - timedelta(minutes=30)

    stuck_images = DicomImage.objects.filter(
        status='processing',
        updated_at__lt=stuck_threshold
    )

    if stuck_images.exists():
        logger.warning(f"Found {stuck_images.count()} stuck DICOM processing tasks")
        # Send alert to admin
        send_admin_alert(f"{stuck_images.count()} stuck DICOM tasks")

        # Mark as failed
        stuck_images.update(status='failed')

    return {'stuck_images_found': stuck_images.count()}

@shared_task
def archive_old_studies():
    """
    Archive studies older than 2 years to cold storage (S3 Glacier)
    """
    archive_cutoff = timezone.now() - timedelta(days=730)  # 2 years

    old_studies = ImagingStudy.objects.filter(
        created_at__lt=archive_cutoff,
        is_archived=False
    )

    archived_count = 0
    for study in old_studies:
        # Move files to Glacier
        for image in study.images.all():
            move_to_glacier(image.file_path)

        study.is_archived = True
        study.save()
        archived_count += 1

    return {'archived_studies': archived_count}
```

**5. Running Celery Beat**

```bash
# Development
celery -A firstproject beat --loglevel=info

# Production (with workers and beat)
# Terminal 1: Workers
celery -A firstproject worker --loglevel=info --concurrency=4

# Terminal 2: Beat (scheduler)
celery -A firstproject beat --loglevel=info

# Or combined (NOT recommended for production)
celery -A firstproject worker --beat --loglevel=info
```

**Docker Compose setup:**

```yaml
services:
  celery_worker:
    build: .
    command: celery -A firstproject worker --loglevel=info --concurrency=4
    depends_on:
      - db
      - redis

  celery_beat:
    build: .
    command: celery -A firstproject beat --loglevel=info
    depends_on:
      - db
      - redis
    # IMPORTANT: Only run ONE beat instance!
    deploy:
      replicas: 1
```

**6. Dynamic periodic tasks (django-celery-beat)**

For tasks that need to be configured at runtime (not hardcoded):

```bash
pip install django-celery-beat
```

```python
# settings.py
INSTALLED_APPS += ['django_celery_beat']

# Run migrations
python manage.py migrate django_celery_beat

# Use database scheduler instead of code
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
```

**Admin interface for managing periodic tasks:**

```python
# admin.py
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule

# Now you can create tasks via Django admin!
```

**Create periodic task programmatically:**

```python
from django_celery_beat.models import PeriodicTask, CrontabSchedule

# Create crontab schedule (daily at midnight)
schedule, created = CrontabSchedule.objects.get_or_create(
    minute='0',
    hour='0',
    day_of_week='*',
    day_of_month='*',
    month_of_year='*',
)

# Create periodic task
PeriodicTask.objects.create(
    crontab=schedule,
    name='Cleanup audit logs - Hospital 1',
    task='medical_imaging.tasks.cleanup_old_audit_logs',
    kwargs=json.dumps({'hospital_id': 1}),
)
```

**7. Tricky scenarios**

**Q: What happens if a periodic task takes longer than its interval?**

```python
# Task runs every 10 minutes but takes 15 minutes to complete

# Answer: Celery Beat sends the task again at next interval!
# Result: Multiple instances running simultaneously

# Solution 1: Use task locking
from django.core.cache import cache

@shared_task
def long_running_task():
    lock_id = 'long_running_task_lock'

    # Try to acquire lock
    if cache.add(lock_id, 'true', timeout=600):  # 10 min lock
        try:
            # Do work
            process_data()
        finally:
            cache.delete(lock_id)
    else:
        logger.warning('Task already running, skipping')
        return {'status': 'skipped'}

# Solution 2: Use celery-once
# pip install celery-once
from celery_once import QueueOnce

@shared_task(base=QueueOnce, once={'graceful': True})
def long_running_task():
    # Only one instance will run at a time
    pass
```

**Q: How to pass arguments to periodic tasks?**

```python
# Method 1: Hardcode in beat_schedule
app.conf.beat_schedule = {
    'task-with-args': {
        'task': 'tasks.process_hospital',
        'schedule': crontab(hour=0, minute=0),
        'args': (1,),  # Positional args
        'kwargs': {'report_type': 'daily'},  # Keyword args
    },
}

# Method 2: Use django-celery-beat for dynamic args
PeriodicTask.objects.create(
    schedule=schedule,
    name='Process Hospital 1',
    task='tasks.process_hospital',
    args=json.dumps([1]),  # JSON string!
    kwargs=json.dumps({'report_type': 'daily'}),
)
```

**Q: Celery Beat vs Cron - which to use?**

| Feature | Celery Beat | Cron |
|---------|-------------|------|
| **Task execution** | Via Celery workers | Direct command execution |
| **Distributed** | ✅ Works across servers | ❌ Single server only |
| **Monitoring** | ✅ Via Flower/Celery | ❌ Limited |
| **Dynamic tasks** | ✅ Via django-celery-beat | ❌ Requires file edit |
| **Retry logic** | ✅ Built-in | ❌ Manual |
| **Dependencies** | ✅ Can access Django ORM | ⚠️ Must load Django |
| **Timezone** | ✅ Timezone-aware | ⚠️ Server timezone |

**Use Cron for:**
- System-level tasks (backups, log rotation)
- Simple one-off scripts
- Non-Python tasks

**Use Celery Beat for:**
- Tasks that need Django ORM
- Distributed systems
- Tasks requiring retry logic
- Dynamic scheduling

**This demonstrates:**
- Deep understanding of Celery Beat architecture
- Crontab expression syntax mastery
- Periodic task configuration strategies
- Handling edge cases (long-running tasks, locking)
- Knowledge of django-celery-beat for dynamic scheduling

---

### **Q40: What is the N+1 query problem and how does it relate to async tasks? How would you optimize database queries in Celery tasks? (HARD)**

**This is a HARD question** that combines database optimization with async processing - many candidates struggle here.

**The N+1 Problem:**

```python
# ❌ BAD: N+1 queries in Celery task
@shared_task
def generate_hospital_report(hospital_id):
    hospital = Hospital.objects.get(pk=hospital_id)  # 1 query

    patients = hospital.patients.all()  # 1 query

    report_data = []
    for patient in patients:  # N queries (one per patient!)
        studies = patient.studies.all()  # Query 1 for patient 1
                                          # Query 2 for patient 2
                                          # ... Query N for patient N
        report_data.append({
            'patient': patient.full_name,
            'total_studies': studies.count(),
        })

    # If hospital has 1000 patients: 1 + 1 + 1000 = 1002 queries!
    return report_data
```

**Why this is WORSE in Celery:**

1. **Task takes longer** → Blocks worker → Reduces throughput
2. **Database connections** → Each worker holds connection → Connection pool exhaustion
3. **Race conditions** → Data might change between queries
4. **Harder to debug** → Queries happen in background

**Solution 1: select_related() for forward ForeignKey/OneToOne**

```python
# ✅ GOOD: Use select_related()
@shared_task
def process_patient_studies(patient_id):
    # ❌ Without select_related (2 queries)
    patient = Patient.objects.get(pk=patient_id)
    hospital_name = patient.hospital.name  # Extra query!

    # ✅ With select_related (1 query with JOIN)
    patient = Patient.objects.select_related('hospital').get(pk=patient_id)
    hospital_name = patient.hospital.name  # No extra query!

    # SQL generated:
    # SELECT patient.*, hospital.*
    # FROM patient
    # INNER JOIN hospital ON patient.hospital_id = hospital.id
    # WHERE patient.id = 1
```

**Solution 2: prefetch_related() for reverse ForeignKey/ManyToMany**

```python
# ✅ GOOD: Use prefetch_related()
@shared_task
def generate_hospital_report(hospital_id):
    # Fetch hospital with all patients and their studies in 3 queries
    hospital = Hospital.objects.prefetch_related(
        'patients',                    # Query 2: Get all patients
        'patients__studies',           # Query 3: Get all studies
        'patients__studies__images',   # Query 4: Get all images
    ).get(pk=hospital_id)  # Query 1

    # Now iterate with NO additional queries
    report_data = []
    for patient in hospital.patients.all():  # From cache
        for study in patient.studies.all():  # From cache
            report_data.append({
                'patient': patient.full_name,
                'study': study.description,
                'images': study.images.count(),  # From cache
            })

    # Total: 4 queries instead of 1 + N + N*M!
    return report_data
```

**Solution 3: Prefetch + Custom QuerySet**

```python
from django.db.models import Prefetch

@shared_task
def generate_recent_studies_report(hospital_id):
    """
    Only prefetch studies from last 30 days
    """
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)

    recent_studies_queryset = ImagingStudy.objects.filter(
        created_at__gte=cutoff
    ).select_related('diagnosis')

    hospital = Hospital.objects.prefetch_related(
        'patients',
        Prefetch(
            'patients__studies',
            queryset=recent_studies_queryset,
            to_attr='recent_studies'  # Custom attribute name
        )
    ).get(pk=hospital_id)

    report_data = []
    for patient in hospital.patients.all():
        # Access via custom attribute
        for study in patient.recent_studies:  # Only recent studies
            report_data.append({
                'patient': patient.full_name,
                'study': study.description,
                'diagnosis': study.diagnosis.description if study.diagnosis else None,
            })

    return report_data
```

**Solution 4: Annotate and aggregate**

```python
from django.db.models import Count, Avg, F

@shared_task
def calculate_hospital_statistics(hospital_id):
    """
    Calculate statistics without loading all data into Python
    """
    # ❌ BAD: Load all data and count in Python
    patients = Patient.objects.filter(hospital_id=hospital_id)
    stats = []
    for patient in patients:
        study_count = patient.studies.count()  # Query per patient!
        stats.append({'patient_id': patient.id, 'study_count': study_count})

    # ✅ GOOD: Use database aggregation (1 query)
    patients_with_counts = Patient.objects.filter(
        hospital_id=hospital_id
    ).annotate(
        study_count=Count('studies'),
        avg_image_count=Avg('studies__images'),
        latest_study_date=Max('studies__created_at'),
    ).values('id', 'full_name', 'study_count', 'avg_image_count', 'latest_study_date')

    return list(patients_with_counts)

    # SQL generated:
    # SELECT patient.id, patient.full_name,
    #        COUNT(studies.id) as study_count,
    #        AVG(images.id) as avg_image_count,
    #        MAX(studies.created_at) as latest_study_date
    # FROM patient
    # LEFT JOIN imaging_study studies ON patient.id = studies.patient_id
    # LEFT JOIN dicom_image images ON studies.id = images.study_id
    # WHERE patient.hospital_id = 1
    # GROUP BY patient.id
```

**Solution 5: only() and defer() to reduce data transfer**

```python
@shared_task
def send_patient_notifications(hospital_id):
    """
    Send emails to patients - only need email and name
    """
    # ❌ BAD: Load all patient fields
    patients = Patient.objects.filter(hospital_id=hospital_id)
    # Loads: id, mrn, first_name, last_name, dob, gender, contact_number,
    #        email, address, city, state, zip_code, hospital_id, created_at, updated_at

    # ✅ GOOD: Only load needed fields
    patients = Patient.objects.filter(hospital_id=hospital_id).only('email', 'full_name')
    # Only loads: id, email, full_name (much less data transferred)

    for patient in patients:
        send_email(patient.email, f"Hello {patient.full_name}")

    # Alternatively, use values() for dict instead of model instances
    patients_data = Patient.objects.filter(hospital_id=hospital_id).values('email', 'full_name')
    for patient in patients_data:
        send_email(patient['email'], f"Hello {patient['full_name']}")
```

**Solution 6: Batch operations**

```python
@shared_task
def update_study_status(study_ids):
    """
    Update multiple studies efficiently
    """
    # ❌ BAD: Update one by one (N queries)
    for study_id in study_ids:
        study = ImagingStudy.objects.get(pk=study_id)
        study.status = 'processed'
        study.save()

    # ✅ GOOD: Batch update (1 query)
    ImagingStudy.objects.filter(id__in=study_ids).update(status='processed')

    # For more complex updates with F() expressions
    ImagingStudy.objects.filter(id__in=study_ids).update(
        processed_at=timezone.now(),
        processing_time=F('completed_at') - F('started_at'),
    )
```

**Solution 7: Bulk create for inserts**

```python
@shared_task
def process_dicom_batch(file_paths):
    """
    Process multiple DICOM files
    """
    # ❌ BAD: Create one by one (N queries + N signals)
    for file_path in file_paths:
        DicomImage.objects.create(
            file_path=file_path,
            status='pending',
        )

    # ✅ GOOD: Bulk create (1 query)
    images = [
        DicomImage(file_path=path, status='pending')
        for path in file_paths
    ]
    DicomImage.objects.bulk_create(images, batch_size=1000)

    # Note: bulk_create() doesn't call save() or signals!
    # If you need signals, use batch processing:
    for i in range(0, len(file_paths), 100):  # Process in batches of 100
        batch = file_paths[i:i+100]
        for path in batch:
            DicomImage.objects.create(file_path=path, status='pending')
```

**Solution 8: Database connection optimization**

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'django_db',
        'USER': 'root',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': 3306,
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
        'CONN_MAX_AGE': 600,  # Connection pooling (10 minutes)
    }
}

# Celery configuration
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100  # Restart worker after 100 tasks
# Prevents memory leaks and closes stale DB connections
```

**Solution 9: Query debugging in Celery**

```python
from django.db import connection
from django.test.utils import override_settings

@shared_task
@override_settings(DEBUG=True)  # Enable query logging
def debug_queries_task(hospital_id):
    from django.db import reset_queries

    reset_queries()  # Clear previous queries

    # Your code
    hospital = Hospital.objects.prefetch_related('patients__studies').get(pk=hospital_id)

    for patient in hospital.patients.all():
        for study in patient.studies.all():
            print(study.description)

    # Print all queries
    print(f"Total queries: {len(connection.queries)}")
    for query in connection.queries:
        print(f"Time: {query['time']}, SQL: {query['sql']}")

    return {'total_queries': len(connection.queries)}
```

**Solution 10: Using django-debug-toolbar in Celery**

```bash
pip install django-silk  # Better for async tasks than debug-toolbar
```

```python
# settings.py
INSTALLED_APPS += ['silk']

MIDDLEWARE += ['silk.middleware.SilkyMiddleware']

# Now view /silk/ in browser to see all queries, including from Celery tasks
```

**Real-world optimization example:**

```python
# BEFORE: 10,002 queries, takes 45 seconds
@shared_task
def generate_comprehensive_report(hospital_id):
    hospital = Hospital.objects.get(pk=hospital_id)  # 1 query
    patients = hospital.patients.all()  # 1 query

    report = []
    for patient in patients:  # 10,000 patients
        studies = patient.studies.all()  # 10,000 queries
        for study in studies:
            diagnosis = study.diagnosis  # If exists, another query
            report.append({
                'patient': patient.full_name,
                'study': study.description,
                'diagnosis': diagnosis.description if diagnosis else None,
            })

    return report

# AFTER: 4 queries, takes 2 seconds
@shared_task
def generate_comprehensive_report_optimized(hospital_id):
    hospital = Hospital.objects.prefetch_related(
        Prefetch('patients', queryset=Patient.objects.only('id', 'first_name', 'last_name')),
        Prefetch('patients__studies', queryset=ImagingStudy.objects.select_related('diagnosis')),
    ).get(pk=hospital_id)

    report = []
    for patient in hospital.patients.all():
        for study in patient.studies.all():
            report.append({
                'patient': patient.full_name,
                'study': study.description,
                'diagnosis': study.diagnosis.description if study.diagnosis else None,
            })

    return report
```

**Tricky interview follow-up:**

**Q: When would select_related() NOT help?**

A: For reverse relations or ManyToMany - use prefetch_related() instead!

```python
# ❌ WRONG: select_related() on reverse FK
hospital = Hospital.objects.select_related('patients').get(pk=1)
# Django ignores this! patients is a reverse relation

# ✅ CORRECT: Use prefetch_related()
hospital = Hospital.objects.prefetch_related('patients').get(pk=1)
```

**This demonstrates:**
- Deep understanding of Django ORM optimization
- Knowledge of N+1 problem and its impact on async tasks
- select_related() vs prefetch_related()
- Database query analysis and debugging
- Production-ready Celery task optimization

---

### **Q41: How would you handle task retries, exponential backoff, and dead letter queues in Celery? (ADVANCED)**

**This is an advanced question** testing knowledge of error handling and resilience in distributed systems.

**1. Basic retry configuration**

```python
@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Retry after 60 seconds
)
def unreliable_api_call(self, patient_id):
    try:
        # Call external PACS system
        response = requests.get(f'https://pacs.hospital.com/patient/{patient_id}')
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        # Retry on failure
        raise self.retry(exc=exc)
```

**2. Exponential backoff (IMPORTANT FOR PRODUCTION)**

Prevents overwhelming a failing service:

```python
@shared_task(
    bind=True,
    max_retries=5,
    autoretry_for=(requests.RequestException,),  # Auto-retry on these exceptions
    retry_backoff=True,  # Enable exponential backoff
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True,  # Add randomness to prevent thundering herd
)
def fetch_patient_from_pacs(self, patient_id):
    """
    Retry schedule with exponential backoff:
    - Attempt 1: Immediate
    - Attempt 2: After 2^1 = 2 seconds (+ jitter)
    - Attempt 3: After 2^2 = 4 seconds (+ jitter)
    - Attempt 4: After 2^3 = 8 seconds (+ jitter)
    - Attempt 5: After 2^4 = 16 seconds (+ jitter)
    - Attempt 6: After 2^5 = 32 seconds (+ jitter)
    """
    response = requests.get(f'https://pacs.hospital.com/patient/{patient_id}', timeout=10)
    response.raise_for_status()
    return response.json()
```

**Manual retry with custom backoff:**

```python
@shared_task(bind=True, max_retries=5)
def custom_backoff_task(self, image_id):
    try:
        # Attempt DICOM processing
        process_dicom(image_id)
    except Exception as exc:
        # Custom backoff: 1min, 5min, 15min, 30min, 60min
        retry_delays = [60, 300, 900, 1800, 3600]
        retry_count = self.request.retries

        if retry_count < len(retry_delays):
            delay = retry_delays[retry_count]
            logger.warning(f"Task failed, retrying in {delay}s (attempt {retry_count + 1})")
            raise self.retry(exc=exc, countdown=delay)
        else:
            # Max retries exceeded
            logger.error(f"Task failed permanently after {retry_count} attempts")
            raise
```

**3. Selective retry (don't retry everything!)**

```python
class NotRetryable(Exception):
    """Exception that should NOT be retried"""
    pass

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(requests.Timeout, requests.ConnectionError),  # Only retry these
    dont_autoretry_for=(NotRetryable, ValidationError),  # Never retry these
)
def process_patient_data(self, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        # Don't retry - patient doesn't exist!
        raise NotRetryable(f"Patient {patient_id} not found")

    try:
        # Call external API (transient failures - should retry)
        data = fetch_from_external_api(patient.medical_record_number)
    except requests.Timeout:
        # Auto-retry (defined in autoretry_for)
        raise

    # Validation error - don't retry
    if not data.get('valid'):
        raise ValidationError("Invalid data received")

    return data
```

**4. Task result expiration and cleanup**

```python
# settings.py
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour

# Per-task configuration
@shared_task(expires=300)  # Task expires after 5 minutes
def time_sensitive_task():
    """
    If this task isn't picked up within 5 minutes, it expires
    (won't execute even if worker becomes available later)
    """
    pass
```

**5. Dead Letter Queue (DLQ) implementation**

```python
# models.py
class FailedTask(models.Model):
    """Store permanently failed tasks for manual review"""
    task_id = models.CharField(max_length=255, unique=True)
    task_name = models.CharField(max_length=255)
    args = models.JSONField(default=list)
    kwargs = models.JSONField(default=dict)
    exception = models.TextField()
    traceback = models.TextField()
    retry_count = models.IntegerField(default=0)
    failed_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-failed_at']
        indexes = [
            models.Index(fields=['resolved', 'failed_at']),
            models.Index(fields=['task_name']),
        ]

# Custom task base class
from celery import Task

class ResilientTask(Task):
    """
    Custom task that stores failures in DLQ
    """
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails after all retries
        """
        logger.error(
            f'Task {self.name} permanently failed',
            extra={
                'task_id': task_id,
                'exception': str(exc),
                'args': args,
                'kwargs': kwargs,
            }
        )

        # Store in Dead Letter Queue
        FailedTask.objects.create(
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            exception=str(exc),
            traceback=str(einfo),
            retry_count=self.max_retries or 0,
        )

        # Send alert to admin
        send_admin_alert(
            subject=f'Task Failed: {self.name}',
            message=f'Task {task_id} failed permanently.\nException: {exc}'
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task is retried
        """
        logger.warning(
            f'Task {self.name} retrying',
            extra={
                'task_id': task_id,
                'retry': self.request.retries,
                'max_retries': self.max_retries,
            }
        )

# Use custom base class
@shared_task(base=ResilientTask, bind=True, max_retries=3)
def critical_dicom_processing(self, image_id):
    # If this fails after 3 retries, it goes to DLQ
    process_dicom_image(image_id)
```

**6. DLQ Admin interface**

```python
# admin.py
from django.contrib import admin
from django.utils.html import format_html

@admin.register(FailedTask)
class FailedTaskAdmin(admin.ModelAdmin):
    list_display = ['task_name', 'failed_at', 'retry_count', 'resolved', 'action_buttons']
    list_filter = ['resolved', 'task_name', 'failed_at']
    search_fields = ['task_id', 'task_name', 'exception']
    readonly_fields = ['task_id', 'task_name', 'args', 'kwargs', 'exception', 'traceback', 'failed_at']

    def action_buttons(self, obj):
        if not obj.resolved:
            return format_html(
                '<a class="button" href="{}">Retry</a>',
                f'/admin/retry-task/{obj.id}/'
            )
        return '-'
    action_buttons.short_description = 'Actions'

# views.py (admin custom view)
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from celery import current_app

@staff_member_required
def retry_failed_task(request, failed_task_id):
    """
    Manually retry a failed task from DLQ
    """
    failed_task = FailedTask.objects.get(pk=failed_task_id)

    # Get the actual task
    task = current_app.tasks.get(failed_task.task_name)

    if task:
        # Retry with original args/kwargs
        task.apply_async(
            args=failed_task.args,
            kwargs=failed_task.kwargs,
        )

        # Mark as resolved
        failed_task.resolved = True
        failed_task.resolved_at = timezone.now()
        failed_task.save()

        messages.success(request, f'Task {failed_task.task_id} requeued')
    else:
        messages.error(request, f'Task {failed_task.task_name} not found')

    return redirect('/admin/medical_imaging/failedtask/')
```

**7. Retry with rate limiting**

```python
@shared_task(
    bind=True,
    max_retries=10,
    rate_limit='10/m',  # Max 10 tasks per minute
)
def rate_limited_api_call(self, patient_id):
    """
    Calls external API with rate limit
    If API returns 429 (rate limit), retry with backoff
    """
    try:
        response = requests.get(f'https://api.external.com/patient/{patient_id}')

        if response.status_code == 429:
            # Rate limited - retry after delay specified in header
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(f'Rate limited, retrying after {retry_after}s')
            raise self.retry(countdown=retry_after)

        response.raise_for_status()
        return response.json()

    except requests.RequestException as exc:
        # Network error - exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

**8. Circuit breaker pattern**

```python
from django.core.cache import cache
from datetime import timedelta

class CircuitBreakerOpen(Exception):
    """Circuit is open, not attempting call"""
    pass

@shared_task(bind=True)
def external_api_with_circuit_breaker(self, endpoint):
    """
    Implements circuit breaker to prevent cascading failures
    """
    circuit_key = f'circuit_breaker:{endpoint}'
    failure_count_key = f'{circuit_key}:failures'
    open_until_key = f'{circuit_key}:open_until'

    # Check if circuit is open
    open_until = cache.get(open_until_key)
    if open_until and timezone.now() < open_until:
        raise CircuitBreakerOpen(f"Circuit open until {open_until}")

    try:
        response = requests.get(endpoint, timeout=5)
        response.raise_for_status()

        # Success - reset failure count
        cache.delete(failure_count_key)
        cache.delete(open_until_key)

        return response.json()

    except requests.RequestException as exc:
        # Increment failure count
        failures = cache.get(failure_count_key, 0) + 1
        cache.set(failure_count_key, failures, timeout=300)

        # Open circuit after 5 failures
        if failures >= 5:
            # Open circuit for 1 minute
            open_until = timezone.now() + timedelta(minutes=1)
            cache.set(open_until_key, open_until, timeout=60)
            logger.error(f"Circuit breaker opened for {endpoint}")

        raise self.retry(exc=exc)
```

**9. Idempotent tasks (CRITICAL CONCEPT)**

**Q: What if a task runs twice?**

```python
# ❌ NON-IDEMPOTENT (dangerous!)
@shared_task
def charge_patient(patient_id, amount):
    """
    If this runs twice, patient is charged twice!
    """
    patient = Patient.objects.get(pk=patient_id)
    patient.balance -= amount
    patient.save()

# ✅ IDEMPOTENT (safe)
from django.db import transaction

@shared_task
def charge_patient_idempotent(patient_id, amount, transaction_id):
    """
    Uses transaction_id to ensure only charged once
    """
    with transaction.atomic():
        # Check if already processed
        if Payment.objects.filter(transaction_id=transaction_id).exists():
            logger.info(f"Payment {transaction_id} already processed, skipping")
            return {'status': 'already_processed'}

        # Create payment record (prevents duplicates)
        payment = Payment.objects.create(
            patient_id=patient_id,
            amount=amount,
            transaction_id=transaction_id,
        )

        # Update balance
        Patient.objects.filter(pk=patient_id).update(
            balance=F('balance') - amount
        )

        return {'status': 'success', 'payment_id': payment.id}
```

**This demonstrates:**
- Advanced retry strategies and exponential backoff
- Dead Letter Queue implementation
- Circuit breaker pattern for resilience
- Idempotency for financial/critical operations
- Production-ready error handling

---

### **Q42: Explain Celery task routing, queues, and worker pools. How would you design a multi-queue architecture for different priority tasks? (EXPERT LEVEL)**

**This is an EXPERT-level question** that tests architectural design skills. Many developers only use the default queue.

**Why multiple queues matter:**

1. **Priority**: Critical tasks shouldn't wait behind bulk operations
2. **Resource allocation**: CPU-heavy vs I/O-heavy tasks need different workers
3. **SLA guarantees**: Different task types have different latency requirements
4. **Isolation**: Prevent one task type from starving others

**Architecture for medical imaging platform:**

```
┌────────────────────────────────────────────────────────────┐
│                       Redis Broker                          │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│   Queue 1   │   Queue 2   │   Queue 3   │    Queue 4      │
│   default   │   high_pri  │   reports   │   email         │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────────┘
       │             │              │              │
   ┌───▼────┐   ┌───▼────┐    ┌───▼────┐    ┌───▼────┐
   │Worker 1│   │Worker 2│    │Worker 3│    │Worker 4│
   │2 cores │   │4 cores │    │2 cores │    │1 core  │
   │General │   │DICOM   │    │Reports │    │Email   │
   └────────┘   └────────┘    └────────┘    └────────┘
```

**1. Queue configuration**

```python
# settings.py
from kombu import Queue, Exchange

# Define exchanges and queues
CELERY_TASK_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
    Queue('dicom_processing', Exchange('dicom'), routing_key='dicom.processing'),
    Queue('reports', Exchange('reports'), routing_key='reports.generate'),
    Queue('email', Exchange('email'), routing_key='email.send'),
    Queue('maintenance', Exchange('maintenance'), routing_key='maintenance.cleanup'),
)

# Default queue
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'

# Route specific tasks to specific queues
CELERY_TASK_ROUTES = {
    # High priority tasks
    'medical_imaging.tasks.process_emergency_scan': {
        'queue': 'high_priority',
        'routing_key': 'high_priority',
    },
    'medical_imaging.tasks.notify_critical_finding': {
        'queue': 'high_priority',
        'routing_key': 'high_priority',
    },

    # DICOM processing (CPU-intensive)
    'medical_imaging.tasks.process_dicom_image': {
        'queue': 'dicom_processing',
        'routing_key': 'dicom.processing',
    },
    'medical_imaging.tasks.generate_dicom_thumbnail': {
        'queue': 'dicom_processing',
        'routing_key': 'dicom.processing',
    },

    # Report generation (memory-intensive)
    'medical_imaging.tasks.generate_patient_report_pdf': {
        'queue': 'reports',
        'routing_key': 'reports.generate',
    },

    # Email sending (I/O-bound)
    'medical_imaging.tasks.send_report_email': {
        'queue': 'email',
        'routing_key': 'email.send',
    },

    # Maintenance tasks (run during off-hours)
    'medical_imaging.tasks.cleanup_old_files': {
        'queue': 'maintenance',
        'routing_key': 'maintenance.cleanup',
    },
}
```

**2. Starting workers for different queues**

```bash
# Worker 1: Default queue (2 workers)
celery -A firstproject worker -Q default --concurrency=2 --loglevel=info -n worker1@%h

# Worker 2: High priority queue (4 workers, lower time limit)
celery -A firstproject worker -Q high_priority --concurrency=4 --loglevel=info -n worker2@%h --time-limit=300

# Worker 3: DICOM processing (CPU-intensive, 4 workers)
celery -A firstproject worker -Q dicom_processing --concurrency=4 --loglevel=info -n worker3@%h --time-limit=600

# Worker 4: Reports (memory-intensive, 2 workers)
celery -A firstproject worker -Q reports --concurrency=2 --loglevel=info -n worker4@%h --time-limit=900

# Worker 5: Email (I/O-bound, 10 workers)
celery -A firstproject worker -Q email --concurrency=10 --loglevel=info -n worker5@%h

# Worker 6: Maintenance (single worker, runs overnight)
celery -A firstproject worker -Q maintenance --concurrency=1 --loglevel=info -n worker6@%h
```

**3. Docker Compose with multiple workers**

```yaml
# docker-compose.yml
services:
  # Default worker
  celery_worker_default:
    build: .
    command: celery -A firstproject worker -Q default --concurrency=2 -n worker_default@%h
    depends_on:
      - redis
      - db
    deploy:
      replicas: 2  # Run 2 instances

  # High priority worker
  celery_worker_high_priority:
    build: .
    command: celery -A firstproject worker -Q high_priority --concurrency=4 -n worker_high_priority@%h --time-limit=300
    depends_on:
      - redis
      - db
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '2.0'
          memory: 2G

  # DICOM processing worker (CPU-intensive)
  celery_worker_dicom:
    build: .
    command: celery -A firstproject worker -Q dicom_processing --concurrency=4 -n worker_dicom@%h --time-limit=600
    depends_on:
      - redis
      - db
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '4.0'
          memory: 4G

  # Report generation worker
  celery_worker_reports:
    build: .
    command: celery -A firstproject worker -Q reports --concurrency=2 -n worker_reports@%h --time-limit=900
    depends_on:
      - redis
      - db
    deploy:
      replicas: 1
      resources:
        limits:
          memory: 4G  # High memory for PDF generation

  # Email worker (I/O-bound)
  celery_worker_email:
    build: .
    command: celery -A firstproject worker -Q email --concurrency=10 -n worker_email@%h
    depends_on:
      - redis
      - db
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

**4. Task priority within a queue**

```python
# Celery supports priorities 0-9 (higher = more priority)
@shared_task
def process_routine_scan(scan_id):
    # Default priority (no arg)
    pass

# Send with priority
process_routine_scan.apply_async(args=[scan_id], priority=3)

# High priority task
@shared_task
def process_emergency_scan(scan_id):
    pass

process_emergency_scan.apply_async(args=[scan_id], priority=9)

# Note: Priorities work WITHIN a queue
# Still better to use separate queues for truly different priorities
```

**5. Dynamic routing based on task arguments**

```python
# Custom router
class MyRouter:
    def route_for_task(self, task, args=None, kwargs=None):
        """
        Route tasks dynamically based on arguments
        """
        if task == 'medical_imaging.tasks.process_scan':
            # Check if emergency scan
            scan_id = args[0] if args else kwargs.get('scan_id')
            scan = ImagingStudy.objects.get(pk=scan_id)

            if scan.priority == 'emergency':
                return {'queue': 'high_priority'}
            elif scan.modality == 'CT':
                return {'queue': 'dicom_processing'}  # CPU-intensive
            else:
                return {'queue': 'default'}

        # Default routing
        return None

# settings.py
CELERY_ROUTES = (MyRouter(),)
```

**6. Worker pools: prefork vs gevent vs threads**

```python
# PREFORK (default) - Multiprocessing, CPU-bound tasks
# Best for: DICOM processing, image manipulation
celery -A firstproject worker --pool=prefork --concurrency=4

# GEVENT - Async I/O, thousands of concurrent connections
# Best for: API calls, email sending, web scraping
celery -A firstproject worker --pool=gevent --concurrency=1000

# THREADS - Thread-based concurrency
# Best for: I/O-bound tasks with GIL-releasing operations
celery -A firstproject worker --pool=threads --concurrency=100

# SOLO - Single-threaded (for debugging)
celery -A firstproject worker --pool=solo
```

**Real-world configuration:**

```bash
# Worker 1: DICOM processing (CPU-intensive, prefork)
celery -A firstproject worker -Q dicom_processing --pool=prefork --concurrency=4

# Worker 2: API calls to external PACS (I/O-intensive, gevent)
celery -A firstproject worker -Q pacs_integration --pool=gevent --concurrency=500

# Worker 3: Email sending (I/O-intensive, gevent)
celery -A firstproject worker -Q email --pool=gevent --concurrency=1000
```

**7. Queue monitoring and autoscaling**

```python
# Autoscale workers based on queue length
celery -A firstproject worker -Q dicom_processing --autoscale=10,2

# Means:
# - Minimum 2 worker processes
# - Maximum 10 worker processes
# - Scale up/down based on queue length

# Monitor queue length
from celery import current_app

def get_queue_length(queue_name='default'):
    with current_app.connection_or_acquire() as conn:
        return conn.default_channel.client.llen(queue_name)

# Management command
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        queues = ['default', 'high_priority', 'dicom_processing', 'reports', 'email']

        for queue in queues:
            length = get_queue_length(queue)
            self.stdout.write(f"{queue}: {length} tasks")

            if length > 100:
                self.stdout.write(self.style.WARNING(f"Queue {queue} is backing up!"))
```

**8. Queue prioritization strategy**

```python
# tasks.py
from enum import IntEnum

class TaskPriority(IntEnum):
    """Task priority levels"""
    CRITICAL = 9  # Life-threatening alerts
    HIGH = 7      # Emergency scans
    NORMAL = 5    # Routine processing
    LOW = 3       # Batch operations
    MAINTENANCE = 1  # Cleanup, archival

@shared_task
def process_scan(scan_id, priority=TaskPriority.NORMAL):
    """
    Process medical scan with priority
    """
    scan = ImagingStudy.objects.get(pk=scan_id)

    # Route based on priority
    if priority >= TaskPriority.HIGH:
        # Use high priority queue
        process_scan_urgent.apply_async(args=[scan_id], queue='high_priority')
    else:
        # Use default queue
        process_scan_routine.apply_async(args=[scan_id], queue='default', priority=priority)
```

**9. Real-world example: Medical imaging workflow**

```python
# Scenario: CT scan arrives
# 1. Immediate: Extract metadata (high priority)
# 2. Fast: Generate thumbnails for preview (normal priority)
# 3. Slow: Full DICOM processing (normal priority, CPU queue)
# 4. Background: Generate PDF report (low priority)
# 5. Optional: Send email notification (low priority, I/O queue)

from celery import chain, group

def handle_ct_scan_upload(scan_id):
    """
    Orchestrate CT scan processing across multiple queues
    """
    workflow = chain(
        # Step 1: Quick metadata extraction (high priority queue)
        extract_metadata.si(scan_id).set(queue='high_priority', priority=9),

        # Step 2: Parallel processing
        group(
            # Generate thumbnail (normal priority, DICOM queue)
            generate_thumbnail.si(scan_id).set(queue='dicom_processing', priority=5),

            # Full processing (normal priority, DICOM queue)
            process_full_dicom.si(scan_id).set(queue='dicom_processing', priority=5),
        ),

        # Step 3: Generate report after processing (reports queue)
        generate_report.si(scan_id).set(queue='reports', priority=3),

        # Step 4: Send notification (email queue)
        send_notification.si(scan_id).set(queue='email', priority=1),
    )

    return workflow.apply_async()
```

**Monitoring dashboard:**

```python
# views.py
from celery.task.control import inspect

class QueueStatsView(APIView):
    """
    API endpoint for queue statistics
    """
    def get(self, request):
        inspector = inspect()

        # Get active tasks per worker
        active = inspector.active()

        # Get registered tasks
        registered = inspector.registered()

        # Get worker stats
        stats = inspector.stats()

        # Get queue lengths
        queue_lengths = {
            'default': get_queue_length('default'),
            'high_priority': get_queue_length('high_priority'),
            'dicom_processing': get_queue_length('dicom_processing'),
            'reports': get_queue_length('reports'),
            'email': get_queue_length('email'),
        }

        return Response({
            'active_tasks': active,
            'worker_stats': stats,
            'queue_lengths': queue_lengths,
        })
```

**This demonstrates:**
- Advanced queue architecture design
- Multi-queue routing strategies
- Worker pool selection (prefork/gevent/threads)
- Resource allocation for different task types
- Priority-based task handling
- Production-ready monitoring and autoscaling

---

### **Q42: How do you prevent duplicate task execution in a distributed Celery environment? Explain idempotent task design. (PRODUCTION CRITICAL)**

**Idempotent tasks** are tasks that can be executed multiple times without changing the result beyond the first execution. This is **critical in distributed systems** where tasks might be retried, duplicated, or executed across multiple workers.

**The Problem:**

In a distributed Celery setup with multiple workers, you can have:
- **Race conditions**: Two workers processing the same study simultaneously
- **Duplicate processing**: Task retries causing duplicate work
- **Worker crashes**: Tasks left in "processing" state forever (zombie tasks)
- **Network issues**: Same task queued multiple times

**Real-world scenario from my project:**

```python
# ❌ NON-IDEMPOTENT (Problem code)
@shared_task
def process_dicom_images(study_id, file_data_list):
    study = ImagingStudy.objects.get(id=study_id)

    # Problem 1: No lock - two workers could process this simultaneously
    study.status = 'in_progress'
    study.save()

    # Problem 2: If this fails and retries, study stays "in_progress" forever
    for file_data in file_data_list:
        process_file(file_data)

    study.status = 'completed'
    study.save()
```

**Solution 1: Redis Distributed Locking**

Code reference: `medical_imaging/tasks.py:25-66`

```python
from django.core.cache import cache
from django.db import transaction

LOCK_TIMEOUT = 600  # 10 minutes

@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def process_dicom_images_async(self, study_id, file_data_list, user_id=None):
    """
    Idempotent DICOM processing with distributed locking
    """
    task_id = self.request.id
    lock_key = f"dicom-processing-{study_id}"

    # IMPROVEMENT 1: Atomic lock acquisition
    # cache.add() returns False if key exists (atomic operation)
    if not cache.add(lock_key, task_id, LOCK_TIMEOUT):
        existing_lock = cache.get(lock_key)
        logger.warning(f"Study {study_id} already being processed by {existing_lock}")
        return {
            'status': 'skipped',
            'reason': 'already_processing',
            'existing_task_id': existing_lock
        }

    try:
        # IMPROVEMENT 2: Database pessimistic locking
        with transaction.atomic():
            study = ImagingStudy.objects.select_for_update().get(id=study_id)

            # IMPROVEMENT 3: Idempotency check
            if study.status == 'completed':
                logger.info(f"Study {study_id} already completed. Skipping.")
                return {'status': 'already_completed'}

            # Mark as in progress
            study.status = 'in_progress'
            study.error_message = ''  # Clear previous errors
            study.save()

        # Process files...
        for file_data in file_data_list:
            process_file(file_data)

        # Mark as completed
        study.status = 'completed'
        study.save()

    except Exception as exc:
        # IMPROVEMENT 4: Explicit failure state BEFORE retry
        ImagingStudy.objects.filter(id=study_id).update(
            status='failed',
            error_message=str(exc)[:500]
        )
        # Retry with exponential backoff
        raise self.retry(exc=exc)

    finally:
        # IMPROVEMENT 5: ALWAYS release lock (even on crash)
        cache.delete(lock_key)
        logger.info(f"Released lock for study {study_id}")
```

**Key Improvements Explained:**

**1. Redis Distributed Lock (`cache.add()`)**
- `cache.add()` is **atomic** - only succeeds if key doesn't exist
- Returns `False` if another worker already has the lock
- Auto-expires after `LOCK_TIMEOUT` (handles worker crashes)
- Works across multiple Celery worker processes/servers

**2. Database Pessimistic Lock (`select_for_update()`)**
```python
with transaction.atomic():
    study = ImagingStudy.objects.select_for_update().get(id=study_id)
    # Database row is locked - other transactions must wait
```
- Locks the database row until transaction commits
- Prevents race conditions at DB level
- Throws exception if row already locked (timeout)

**3. Idempotency Check**
```python
if study.status == 'completed':
    return {'status': 'already_completed'}
```
- If task retries after completion, it skips reprocessing
- Safe to call multiple times

**4. Explicit Failure State**
```python
except Exception as exc:
    # Mark as FAILED before retry
    ImagingStudy.objects.filter(id=study_id).update(
        status='failed',
        error_message=str(exc)[:500]
    )
    raise self.retry(exc=exc)
```
- Prevents "zombie" tasks stuck in "in_progress"
- Users see failure immediately, not stuck processing
- Error message stored for debugging

**5. Lock Release in `finally` Block**
```python
finally:
    cache.delete(lock_key)
```
- **ALWAYS** releases lock, even on exceptions
- Prevents deadlocks
- Allows retries after failures

**Exponential Backoff Configuration:**

```python
@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,           # Enable exponential backoff
    retry_backoff_max=600,         # Max 10 minutes between retries
    retry_jitter=True              # Add randomness to prevent thundering herd
)
```

**Retry Schedule:**
- 1st retry: ~10 seconds
- 2nd retry: ~100 seconds
- 3rd retry: ~600 seconds (10 minutes)

**Jitter** adds randomness (±25%) to prevent all workers retrying simultaneously.

**Alternative: Celery Task Deduplication**

Using `task_track_started`:

```python
# settings.py
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# tasks.py
@shared_task(
    bind=True,
    task_track_started=True,
    acks_late=True
)
def process_dicom(self, study_id):
    # Celery tracks task state in result backend
    # Won't start duplicate tasks with same args
    pass
```

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Redis Lock** | Fast, works across workers, auto-expires | Requires Redis, lock can expire mid-task |
| **DB Lock** | ACID guarantees, no extra infrastructure | Slower, doesn't work across databases |
| **Task Deduplication** | Built into Celery, simple | Requires result backend, complex configuration |
| **Unique Task ID** | Prevents exact duplicates | Doesn't prevent logic-level duplicates |

**This demonstrates:**
- Deep understanding of distributed systems
- Production reliability awareness
- Race condition handling
- Database transaction management
- Celery retry mechanisms
- Trade-off analysis

---

### **Q42a: Explain structured audit logging for system events. Why is it important in healthcare applications? (HIPAA COMPLIANCE)**

**Structured audit logging** tracks **all actions** (user, system, API) in a queryable, filterable format. In healthcare, this is **legally required** by HIPAA for compliance and forensic investigations.

**The Problem:**

Traditional logging only captures user actions:

```python
# ❌ INCOMPLETE AUDIT LOG (Only user actions)
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL)  # Requires user
    action = models.CharField(max_length=20)
    resource_type = models.CharField(max_length=50)
    resource_id = models.IntegerField()
    ip_address = models.GenericIPAddressField()  # Requires IP
    timestamp = models.DateTimeField(auto_now_add=True)
```

**Missing:** System events, API client actions, Celery task actions, multi-tenant filtering.

**Solution: Enhanced Audit Log Model**

Code reference: `medical_imaging/models.py:259-320`

```python
class AuditLog(models.Model):
    """
    HIPAA compliance: Track all data access and modifications
    Enhanced with multi-tenant support and system event tracking
    """
    ACTION_CHOICES = [
        ('view', 'Viewed'),
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('download', 'Downloaded'),
        ('process', 'Processed'),  # ✅ System tasks
        ('failed', 'Failed'),      # ✅ Failed operations
    ]

    ACTOR_TYPE_CHOICES = [
        ('user', 'User'),      # Human user
        ('system', 'System'),  # Celery task, cron job
        ('api', 'API Client'), # External API integration
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # ✅ Optional for system events
        related_name='audit_logs'
    )

    actor_type = models.CharField(
        max_length=20,
        choices=ACTOR_TYPE_CHOICES,
        default='user',
        help_text="Type of actor performing the action"
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50)
    resource_id = models.IntegerField()

    # ✅ Multi-tenant isolation
    tenant_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Hospital ID for multi-tenant isolation"
    )

    # ✅ Optional for system events
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    # ✅ Structured metadata
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['actor_type', '-timestamp']),      # ✅ Filter by actor
            models.Index(fields=['tenant_id', '-timestamp']),       # ✅ Multi-tenant queries
            models.Index(fields=['tenant_id', 'action', '-timestamp']),  # ✅ Tenant actions
        ]
```

**Database Migration:**

`medical_imaging/migrations/0011_auditlog_actor_type_auditlog_tenant_id_and_more.py`

```python
operations = [
    migrations.AddField(
        model_name='auditlog',
        name='actor_type',
        field=models.CharField(choices=[...], default='user', max_length=20),
    ),
    migrations.AddField(
        model_name='auditlog',
        name='tenant_id',
        field=models.IntegerField(blank=True, db_index=True, null=True),
    ),
    # ... more operations
]
```

**Usage in Celery Tasks:**

Code reference: `medical_imaging/tasks.py:103-115`

```python
@shared_task(bind=True, max_retries=3)
def process_dicom_images_async(self, study_id, file_data_list, user_id=None):
    task_id = self.request.id

    with transaction.atomic():
        study = ImagingStudy.objects.select_for_update().get(id=study_id)

        # ✅ Create audit log for SYSTEM event
        AuditLog.objects.create(
            actor_type='system',           # Not a user action
            action='process',
            resource_type='ImagingStudy',
            resource_id=study_id,
            tenant_id=study.patient.hospital_id,  # Multi-tenant filtering
            details={
                'task_id': task_id,
                'total_files': len(file_data_list),
                'initiated_by_user_id': user_id,  # Track who triggered it
            }
        )
```

**Success Audit Log:**

```python
# After successful processing
AuditLog.objects.create(
    actor_type='system',
    action='update',
    resource_type='ImagingStudy',
    resource_id=study_id,
    tenant_id=study.patient.hospital_id,
    details={
        'task_id': task_id,
        'images_created': len(created_images),
        'images_skipped': len(skipped_images),
        'processing_duration_seconds': duration,
    }
)
```

**Failure Audit Log:**

```python
except Exception as exc:
    # Mark as failed
    study.status = 'failed'
    study.error_message = str(exc)[:500]
    study.save()

    # ✅ Audit the failure
    AuditLog.objects.create(
        actor_type='system',
        action='failed',
        resource_type='ImagingStudy',
        resource_id=study_id,
        tenant_id=study.patient.hospital_id,
        details={
            'task_id': task_id,
            'error': str(exc),
            'retry_count': self.request.retries,
        }
    )
```

**Querying Audit Logs:**

**1. All system events:**
```python
system_events = AuditLog.objects.filter(actor_type='system')
```

**2. All actions for a specific patient (across all studies):**
```python
patient_id = 123
audit_trail = AuditLog.objects.filter(
    resource_type='ImagingStudy',
    resource_id__in=patient.imaging_studies.values_list('id', flat=True)
).order_by('-timestamp')
```

**3. All events for a specific hospital (tenant):**
```python
hospital_logs = AuditLog.objects.filter(
    tenant_id=hospital_id
).select_related('user')
```

**4. Failed Celery tasks in the last 24 hours:**
```python
from django.utils import timezone
from datetime import timedelta

failed_tasks = AuditLog.objects.filter(
    actor_type='system',
    action='failed',
    timestamp__gte=timezone.now() - timedelta(days=1)
)
```

**5. Track who initiated a system task:**
```python
# Find which user triggered the Celery task
task_log = AuditLog.objects.get(
    actor_type='system',
    details__task_id='abc-123-def'
)
user_id = task_log.details.get('initiated_by_user_id')
```

**HIPAA Compliance Benefits:**

| Requirement | Implementation |
|-------------|----------------|
| **Track all access** | Log view, create, update, delete, download |
| **Track modifications** | `details` field stores before/after state |
| **Non-repudiation** | `actor_type`, `user`, `ip_address`, `user_agent` |
| **Audit trail** | Immutable logs (no UPDATE/DELETE permissions) |
| **System actions** | Track Celery tasks, cron jobs, API calls |
| **Retention** | Index on `timestamp` for archival queries |
| **Multi-tenant isolation** | `tenant_id` prevents cross-hospital queries |

**This demonstrates:**
- HIPAA compliance expertise
- Production debugging capability
- Multi-tenant architecture understanding
- Forensic investigation readiness
- System observability

---

### **Q42b: What are "zombie tasks" in Celery? How do you prevent tasks from getting stuck in 'processing' state? (RELIABILITY)**

**Zombie tasks** are Celery tasks that remain stuck in "in_progress" or "processing" state indefinitely, usually due to worker crashes, network failures, or unhandled exceptions.

**The Problem:**

```python
# ❌ PROBLEM CODE
@shared_task
def process_dicom(study_id):
    study = ImagingStudy.objects.get(id=study_id)

    # Mark as processing
    study.status = 'in_progress'
    study.save()

    # This might fail (network error, OOM, worker crash)
    process_files(study)

    # If we crash before this line, status = 'in_progress' FOREVER
    study.status = 'completed'
    study.save()
```

**What causes zombie tasks:**

1. **Worker crashes** (OOM, segfault, killed by OS)
2. **Network failures** (can't reach database/S3)
3. **Task timeout** (SIGKILL doesn't run cleanup code)
4. **Unhandled exceptions** in cleanup logic
5. **Redis/Broker failure** (task acknowledged but not completed)

**User Impact:**

- UI shows "Processing..." forever
- Users can't retry (task appears to be running)
- Data stuck in inconsistent state
- No error message to debug

**Solution: Explicit Failure State**

Code reference: `medical_imaging/models.py:87-107`, `tasks.py:305-318`

**Step 1: Add `error_message` field and `failed` status**

```python
class ImagingStudy(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),        # ✅ Explicit failure state
        ('archived', 'Archived'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # ✅ Store error details
    error_message = models.TextField(blank=True, help_text='Error details if processing failed')
```

**Step 2: Mark as failed BEFORE retry**

```python
@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def process_dicom_images_async(self, study_id, file_data_list):
    try:
        # Process files...
        study.status = 'in_progress'
        study.save()

        process_files(file_data_list)

        # Success
        study.status = 'completed'
        study.error_message = ''
        study.save()

    except Exception as exc:
        # ✅ CRITICAL: Mark as failed BEFORE retry
        ImagingStudy.objects.filter(id=study_id).update(
            status='failed',
            error_message=str(exc)[:500]  # Truncate for DB field
        )

        # Update TaskStatus
        task_status.status = 'failed'
        task_status.error_message = str(exc)
        task_status.save()

        # Now retry (next attempt will see status='failed' and can reset)
        raise self.retry(exc=exc)
```

**Why this works:**

1. **Failure visible immediately** - User sees "Failed" not "Processing"
2. **Error message stored** - User/admin knows what went wrong
3. **Retry awareness** - Next retry can check if previously failed
4. **Safe to retry** - Can reset `status` to `'in_progress'` on retry

**Step 3: Use `.update()` not `.save()`**

```python
# ❌ WRONG: Can fail if instance is stale
study.status = 'failed'
study.save()  # Might raise exception if row deleted

# ✅ CORRECT: Atomic update, doesn't fail if row gone
ImagingStudy.objects.filter(id=study_id).update(
    status='failed',
    error_message=str(exc)[:500]
)
```

**Benefits of `.update()`:**
- **Atomic** - Single SQL UPDATE statement
- **No race conditions** - Uses WHERE clause
- **Doesn't fail** - Returns 0 if row not found
- **Faster** - Doesn't load model instance

**Step 4: Timeout Protection**

```python
# settings.py
CELERY_TASK_TIME_LIMIT = 30 * 60        # Hard limit: 30 minutes (SIGKILL)
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # Soft limit: 25 minutes (exception)

# tasks.py
from celery.exceptions import SoftTimeLimitExceeded

@shared_task(bind=True)
def process_dicom(self, study_id):
    try:
        # Process...
        pass

    except SoftTimeLimitExceeded:
        # Task exceeded soft limit - clean up gracefully
        ImagingStudy.objects.filter(id=study_id).update(
            status='failed',
            error_message='Task exceeded time limit (25 minutes)'
        )
        raise  # Re-raise to mark task as failed
```

**Soft vs Hard Time Limit:**

| Limit Type | Behavior | Use Case |
|------------|----------|----------|
| **Soft** | Raises `SoftTimeLimitExceeded` exception | Graceful cleanup, save partial progress |
| **Hard** | Sends SIGKILL (task terminated immediately) | Prevent runaway tasks, last resort |

**Step 5: Monitoring for Zombie Tasks**

```python
from django.utils import timezone
from datetime import timedelta

def detect_zombie_tasks():
    """
    Find studies stuck in 'in_progress' for >1 hour
    """
    one_hour_ago = timezone.now() - timedelta(hours=1)

    zombies = ImagingStudy.objects.filter(
        status='in_progress',
        updated_at__lt=one_hour_ago
    )

    for study in zombies:
        # Mark as failed
        study.status = 'failed'
        study.error_message = 'Task timed out or worker crashed'
        study.save()

        logger.error(f"Detected zombie task for study {study.id}")
```

**Run this as a periodic Celery task:**

```python
from celery import shared_task
from celery.schedules import crontab

# celery.py
app.conf.beat_schedule = {
    'detect-zombies': {
        'task': 'medical_imaging.tasks.detect_zombie_tasks',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}

@shared_task
def detect_zombie_tasks():
    # Implementation above
    pass
```

**Step 6: Task Result Expiration**

```python
# settings.py
CELERY_RESULT_EXPIRES = 60 * 60 * 24  # 24 hours

# tasks.py
@shared_task(expires=3600)  # Task expires after 1 hour
def process_dicom(study_id):
    # If not executed within 1 hour, discard
    pass
```

**Complete Implementation:**

```python
@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    time_limit=30 * 60,      # Hard limit
    soft_time_limit=25 * 60  # Soft limit
)
def process_dicom_images_async(self, study_id, file_data_list):
    try:
        # Set in progress
        study = ImagingStudy.objects.get(id=study_id)
        study.status = 'in_progress'
        study.error_message = ''
        study.save()

        # Process files
        results = process_files(file_data_list)

        # Mark complete
        study.status = 'completed'
        study.save()

        return results

    except SoftTimeLimitExceeded:
        # Graceful timeout
        ImagingStudy.objects.filter(id=study_id).update(
            status='failed',
            error_message='Processing timed out after 25 minutes'
        )
        raise

    except Exception as exc:
        # ANY exception - mark as failed FIRST
        ImagingStudy.objects.filter(id=study_id).update(
            status='failed',
            error_message=str(exc)[:500]
        )

        # Then retry
        raise self.retry(exc=exc)

    finally:
        # ALWAYS release locks
        cache.delete(f"dicom-lock-{study_id}")
```

**This demonstrates:**
- Production reliability awareness
- Error handling expertise
- Database consistency knowledge
- Celery timeout mechanisms
- Monitoring and alerting design

---

### **Q42c: How did you implement distributed tracing with correlation IDs in your medical imaging platform?**

Distributed tracing is critical for debugging issues across microservices, async tasks, and database operations. I implemented a lightweight correlation ID system that traces requests from HTTP → Celery → AuditLog.

**Architecture:**

```
HTTP Request
    ↓ (X-Correlation-ID header or generate UUID)
Middleware sets correlation_id
    ↓ (contextvars.ContextVar - thread-safe)
Django View passes to Celery
    ↓ (correlation_id parameter)
Celery Task sets context
    ↓ (logging + AuditLog)
Database stores correlation_id
```

**Implementation in `firstproject/correlation_middleware.py`:**

```python
import uuid
from contextvars import ContextVar

# Thread-safe context variable (works with async/await)
correlation_id_context: ContextVar[str] = ContextVar('correlation_id', default=None)

def get_correlation_id():
    """Retrieve correlation ID from current context"""
    return correlation_id_context.get(None)

def set_correlation_id(correlation_id):
    """Set correlation ID in current context"""
    correlation_id_context.set(correlation_id)

class CorrelationIdMiddleware:
    """
    Middleware that extracts or generates correlation IDs for distributed tracing.

    Flow:
    1. Check for X-Correlation-ID header (from client or API gateway)
    2. Generate new UUID if not present
    3. Set in context for logging and downstream services
    4. Add to response headers for client-side correlation
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())

        # Set in thread-local context
        set_correlation_id(correlation_id)

        # Attach to request object for easy access
        request.correlation_id = correlation_id

        # Process request
        response = self.get_response(request)

        # Return correlation ID to client
        response['X-Correlation-ID'] = correlation_id

        return response

class CorrelationIdLoggingFilter(logging.Filter):
    """
    Logging filter that automatically adds correlation IDs to all log records.

    Usage in settings.py:
        'filters': {
            'correlation_id': {
                '()': 'firstproject.correlation_middleware.CorrelationIdLoggingFilter',
            },
        },
    """
    def filter(self, record):
        record.correlation_id = get_correlation_id() or 'N/A'
        return True
```

**Propagation to Celery Tasks (`medical_imaging/tasks.py:25-50`):**

```python
from firstproject.correlation_middleware import set_correlation_id, get_correlation_id

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_dicom_images_async(self, study_id, file_data_list, user_id=None, correlation_id=None):
    """
    Process DICOM images asynchronously with correlation ID tracking.

    Args:
        correlation_id: Optional correlation ID from HTTP request (passed from view)
    """
    task_id = self.request.id

    # Set correlation ID in Celery worker context
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)

    # Correlation ID now available in all logs
    logger.info(
        f"Starting DICOM processing for study {study_id}",
        extra={
            'correlation_id': correlation_id,
            'task_id': task_id,
            'study_id': study_id
        }
    )

    # Store in audit log for compliance
    AuditLog.objects.create(
        actor_type='system',
        action='process',
        resource_type='ImagingStudy',
        resource_id=study_id,
        tenant_id=study.patient.hospital_id,
        details={
            'task_id': task_id,
            'correlation_id': correlation_id,  # ← Searchable in DB
            'total_files': len(file_data_list),
            'initiated_by_user_id': user_id,
        }
    )

    # ... processing logic ...
```

**Real-World Debugging Example:**

When a user reports "My upload is stuck", I can:

1. **Find the initial request:**
   ```bash
   grep "correlation_id=abc-123" /var/log/django/app.log
   # 2025-12-28 08:15:23 INFO [abc-123] POST /api/studies/456/upload/ - user_id=789
   ```

2. **Trace to Celery task:**
   ```bash
   grep "abc-123" /var/log/celery/worker.log
   # 2025-12-28 08:15:25 INFO [abc-123] Starting DICOM processing - task_id=xyz-789
   # 2025-12-28 08:15:45 ERROR [abc-123] S3 upload timeout after 30s
   ```

3. **Query audit logs:**
   ```python
   AuditLog.objects.filter(details__correlation_id='abc-123').order_by('timestamp')
   # Shows full request lifecycle, pinpoints failure at S3 upload
   ```

**Why `contextvars.ContextVar` instead of `threading.local`?**

| Feature | `threading.local` | `contextvars.ContextVar` |
|---------|------------------|--------------------------|
| **async/await support** | ❌ Breaks with asyncio | ✅ Works seamlessly |
| **Thread safety** | ✅ Yes | ✅ Yes |
| **Context isolation** | Per thread | Per async context |
| **Memory leaks** | Risk if not cleaned up | Auto-cleanup |
| **Django channels** | ❌ Incompatible | ✅ Compatible |

**Tricky Interview Question: "How do you prevent correlation ID memory leaks?"**

**Answer:**

`contextvars.ContextVar` automatically cleans up when the context exits (end of request/task). However, in long-lived Celery workers, you should explicitly reset:

```python
# In tasks.py - cleanup after task
try:
    # ... task logic ...
finally:
    correlation_id_context.set(None)  # Explicit cleanup
```

**Alternative considered:** Thread-local storage (`threading.local`)
- **Rejected because:** Doesn't work with async views, Django Channels, or asyncio-based Celery workers
- **ContextVars benefits:** Future-proof for async migration, no memory leaks, Django 3.1+ native support

**Interview Talking Points:**

✅ "I implemented distributed tracing without adding a heavy APM tool like Datadog, reducing costs by $500/month while maintaining full request traceability"

✅ "Used `contextvars.ContextVar` instead of `threading.local` to ensure compatibility with async Django views and Celery workers"

✅ "Correlation IDs propagate from HTTP → Celery → AuditLog → Logs, enabling end-to-end debugging of failed DICOM uploads in under 2 minutes"

✅ "Designed for zero-config: middleware auto-generates UUIDs, so even internal requests are traceable"

✅ "Integrated with existing audit logging system, so compliance team can trace HIPAA-relevant operations across distributed systems"

**This demonstrates:**
- Production debugging strategies
- Thread-safe context management
- Cross-service tracing architecture
- Cost-effective observability
- HIPAA audit trail design

---

### **Q42d: How do you implement production-ready health checks for Kubernetes deployments?**

Health checks are critical for Kubernetes orchestration, load balancer routing, and zero-downtime deployments. I implemented 3 health endpoints with component-level health reporting.

**Architecture:**

```
Load Balancer
    ↓ (every 5s)
GET /api/health/readiness/
    ↓ (check all critical services)
┌────────────────────────────┐
│ ✓ Database (SELECT 1)      │
│ ✓ Redis (SET/GET test key) │
│ ✓ Celery (worker ping)     │
│ ✓ S3 (bucket HEAD request) │
└────────────────────────────┘
    ↓
Return 200 OK (healthy) or 503 Service Unavailable (unhealthy)
```

**Implementation in `medical_imaging/health_views.py`:**

```python
from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from celery import current_app as celery_app
from django.conf import settings
import boto3
from botocore.exceptions import ClientError

@api_view(['GET'])
@permission_classes([AllowAny])  # No auth required (called by load balancers)
def health_check(request):
    """
    Comprehensive health check for monitoring systems.

    Returns:
        200 OK: All systems healthy
        503 Service Unavailable: At least one system unhealthy

    Response format:
        {
            "status": "healthy" | "unhealthy",
            "timestamp": "2025-12-28T08:00:00Z",
            "checks": {
                "database": {"status": "healthy", "details": "..."},
                "redis": {"status": "healthy", "latency_ms": 5},
                "celery": {"status": "healthy", "active_workers": 4},
                "storage": {"status": "healthy", "backend": "s3"}
            }
        }
    """
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'celery': check_celery_workers(),
        'storage': check_storage(),
    }

    # System is healthy only if ALL checks pass
    all_healthy = all(check['status'] == 'healthy' for check in checks.values())

    # Use 503 (not 500) - tells load balancers to route traffic elsewhere
    status_code = 200 if all_healthy else 503

    return Response({
        'status': 'healthy' if all_healthy else 'unhealthy',
        'timestamp': timezone.now().isoformat(),
        'checks': checks,
    }, status=status_code)

def check_database():
    """
    Test database connectivity with a simple query.

    Why SELECT 1?
    - Minimal overhead (no table scan)
    - Works on all SQL databases
    - Tests connection pool + authentication
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        return {
            'status': 'healthy',
            'details': 'Database connection successful'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'details': f'Database connection failed: {str(e)}'
        }

def check_redis():
    """
    Test Redis connectivity with SET/GET operations.

    Why not just PING?
    - Tests full read/write cycle (not just connection)
    - Verifies serialization works
    - Measures actual latency
    """
    test_key = '_health_check_test'
    test_value = str(timezone.now().timestamp())

    try:
        import time
        start = time.time()

        # Test write
        cache.set(test_key, test_value, timeout=10)

        # Test read
        retrieved = cache.get(test_key)

        latency_ms = round((time.time() - start) * 1000, 2)

        if retrieved == test_value:
            return {
                'status': 'healthy',
                'details': 'Redis read/write successful',
                'latency_ms': latency_ms
            }
        else:
            return {
                'status': 'unhealthy',
                'details': 'Redis data mismatch (possible serialization issue)'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'details': f'Redis connection failed: {str(e)}'
        }

def check_celery_workers():
    """
    Test Celery worker availability using inspect().ping().

    Returns:
        - healthy: At least 1 active worker
        - unhealthy: No workers responding (tasks will queue indefinitely)
    """
    try:
        # Ping all workers with 5s timeout
        inspector = celery_app.control.inspect(timeout=5.0)
        active_workers = inspector.ping()

        if active_workers:
            worker_count = len(active_workers)
            return {
                'status': 'healthy',
                'details': f'{worker_count} Celery worker(s) active',
                'active_workers': worker_count,
                'workers': list(active_workers.keys())
            }
        else:
            return {
                'status': 'unhealthy',
                'details': 'No Celery workers responding'
            }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'details': f'Celery inspection failed: {str(e)}'
        }

def check_storage():
    """
    Test storage backend (S3 or local filesystem).

    For S3: HEAD request to bucket (lightweight, no data transfer)
    For local: Check media root directory exists and is writable
    """
    try:
        if settings.USE_S3:
            # Test S3 connectivity
            s3_client = boto3.client('s3')
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

            # HEAD request - just checks bucket exists and is accessible
            s3_client.head_bucket(Bucket=bucket_name)

            return {
                'status': 'healthy',
                'details': f'S3 bucket {bucket_name} accessible',
                'backend': 's3'
            }
        else:
            # Test local filesystem
            import os
            media_root = settings.MEDIA_ROOT

            if os.path.exists(media_root) and os.access(media_root, os.W_OK):
                return {
                    'status': 'healthy',
                    'details': 'Local storage writable',
                    'backend': 'local'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'details': f'Media directory not writable: {media_root}',
                    'backend': 'local'
                }
    except ClientError as e:
        return {
            'status': 'unhealthy',
            'details': f'S3 access failed: {str(e)}'
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'details': f'Storage check failed: {str(e)}'
        }

@api_view(['GET'])
@permission_classes([AllowAny])
def liveness_probe(request):
    """
    Kubernetes liveness probe - checks if application is running.

    Purpose: Restart pod if this fails (application crashed)

    Should ONLY fail if:
    - Python process crashed
    - Django can't serve requests
    - Application deadlocked

    Should NOT check external dependencies (DB, Redis, etc.)
    """
    return Response({
        'status': 'alive',
        'timestamp': timezone.now().isoformat()
    }, status=200)

@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_probe(request):
    """
    Kubernetes readiness probe - checks if application can serve traffic.

    Purpose: Remove pod from load balancer if this fails (don't route traffic)

    Should check:
    - Database connectivity
    - Redis connectivity
    - Critical external services

    Difference from liveness:
    - Liveness: "Is the app alive?" → Restart if failing
    - Readiness: "Can the app handle requests?" → Don't route traffic if failing
    """
    checks = {
        'database': check_database(),
        'redis': check_redis(),
    }

    all_ready = all(check['status'] == 'healthy' for check in checks.values())
    status_code = 200 if all_ready else 503

    return Response({
        'status': 'ready' if all_ready else 'not_ready',
        'timestamp': timezone.now().isoformat(),
        'checks': checks,
    }, status=status_code)
```

**Kubernetes Deployment Configuration:**

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: medical-imaging-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: django
        image: medical-imaging:latest
        ports:
        - containerPort: 8000

        # Liveness probe - restart pod if failing
        livenessProbe:
          httpGet:
            path: /api/health/liveness/
            port: 8000
          initialDelaySeconds: 30  # Wait for Django startup
          periodSeconds: 10         # Check every 10s
          timeoutSeconds: 5
          failureThreshold: 3       # Restart after 3 consecutive failures

        # Readiness probe - remove from load balancer if failing
        readinessProbe:
          httpGet:
            path: /api/health/readiness/
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5          # Check every 5s (more frequent)
          timeoutSeconds: 3
          failureThreshold: 2       # Remove after 2 failures
          successThreshold: 1       # Add back after 1 success
```

**Why 503 (Service Unavailable) instead of 500 (Internal Server Error)?**

| Status Code | Meaning | Load Balancer Behavior | Use Case |
|-------------|---------|------------------------|----------|
| **200 OK** | Healthy | Route traffic normally | All systems operational |
| **500 Internal Server Error** | Application bug | May retry (depends on config) | Code crash, unhandled exception |
| **503 Service Unavailable** | Temporary unavailability | Stop routing traffic immediately | DB down, Redis down, maintenance mode |

**Real-World Scenario:**

During a database failover:

1. **Without health checks:**
   - Load balancer keeps sending requests
   - All requests fail with 500 errors
   - Users see error pages for 2-5 minutes

2. **With health checks:**
   ```
   08:00:00 - Database primary fails
   08:00:05 - Health check detects DB down, returns 503
   08:00:10 - Load balancer removes pod from rotation
   08:00:15 - Database failover to replica completes
   08:00:20 - Health check detects DB up, returns 200
   08:00:25 - Load balancer adds pod back to rotation
   ```
   - Zero user-facing errors
   - Automatic recovery

**Tricky Interview Question: "What's the risk of health checks during thundering herd scenarios?"**

**Answer:**

If all pods fail health checks simultaneously (e.g., Redis goes down), load balancer may route traffic to NO pods, causing total outage.

**Mitigation strategies:**

1. **Staggered health checks:**
   ```yaml
   readinessProbe:
     initialDelaySeconds: {{ randInt 5 15 }}  # Random delay
   ```

2. **Partial degradation:**
   ```python
   # Return 200 even if non-critical services are down
   def check_cache():
       try:
           cache.get('test')
           return {'status': 'healthy'}
       except:
           # Degrade gracefully - still serve traffic without cache
           return {'status': 'degraded', 'warning': 'Cache unavailable'}
   ```

3. **Circuit breaker pattern:**
   ```python
   # Don't overwhelm a failing service with health checks
   if redis_failure_count > 5:
       time.sleep(30)  # Back off for 30s before retrying
   ```

**Interview Talking Points:**

✅ "Implemented Kubernetes-native health checks with liveness and readiness probes, enabling zero-downtime deployments"

✅ "Return 503 (not 500) for unhealthy state, ensuring load balancers immediately stop routing traffic to degraded pods"

✅ "Health checks test actual functionality (DB query, cache write) not just connectivity, catching issues like read-only databases or full disks"

✅ "Designed for observability: health endpoint returns component-level status, helping ops team diagnose issues without SSH access"

✅ "No authentication required on health endpoints (load balancers can't authenticate), but limited to GET requests with no side effects"

**This demonstrates:**
- Kubernetes orchestration expertise
- Production monitoring strategies
- Graceful degradation design
- Load balancer integration
- Observability best practices

---

### **Q42e: How do you ensure reproducibility in medical data processing pipelines?**

In medical imaging, **reproducibility** is both a regulatory requirement (FDA) and a clinical necessity (reprocessing historical data with new algorithms). I implemented pipeline versioning to track which algorithm version processed each study.

**Problem:**

```
Scenario: Radiologist notices inconsistent results between studies

Study A (processed 2024-01-15): Shows lesion detection
Study B (processed 2024-03-20): Similar image, but no lesion detected

Question: Is this a real clinical difference, or did the algorithm change?
```

**Without versioning:** Impossible to know if difference is clinical or algorithmic

**With versioning:**
```sql
SELECT study_id, processing_version, created_at, diagnosis
FROM imaging_studies
WHERE patient_id = 12345
ORDER BY study_date;

-- Results:
-- study_id | processing_version | diagnosis
-- 100      | v1.0.0             | "Lesion detected in left lung"
-- 101      | v1.2.0             | "No significant findings"
```

**Ah-ha!** Study 100 used v1.0.0 (higher false positive rate), Study 101 used v1.2.0 (improved specificity). Need to reprocess Study 100 with v1.2.0 for comparison.

**Implementation in `medical_imaging/models.py:55-60`:**

```python
class ImagingStudy(models.Model):
    # ... existing fields ...

    processing_version = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Version of DICOM processing algorithm used (e.g., v1.2.0)'
    )

    class Meta:
        indexes = [
            models.Index(fields=['processing_version']),  # Query by version
        ]
```

**Version Tracking in `medical_imaging/tasks.py:15`:**

```python
# Version constant - increment when algorithm changes
DICOM_PROCESSING_VERSION = "v1.2.0"

@shared_task(bind=True, max_retries=3)
def process_dicom_images_async(self, study_id, file_data_list, user_id=None, correlation_id=None):
    """
    Process DICOM images with version tracking.

    Version history:
    - v1.0.0: Initial implementation (basic window/level adjustment)
    - v1.1.0: Added Hounsfield unit normalization for CT
    - v1.2.0: Improved JPEG compression (quality=95, optimize=True)
    """
    # ... processing logic ...

    # On successful completion
    study.status = 'completed'
    study.processing_version = DICOM_PROCESSING_VERSION  # ← Set version
    study.save(update_fields=['status', 'processing_version', 'updated_at'])

    logger.info(
        f"Study {study_id} processed successfully with version {DICOM_PROCESSING_VERSION}",
        extra={'correlation_id': correlation_id}
    )
```

**FDA Compliance Use Case:**

For FDA 510(k) submissions, you must demonstrate:

1. **Algorithm validation:** "Our AI model v2.1.5 has 95% sensitivity on test dataset"
2. **Traceability:** "All production diagnoses are linked to validated algorithm versions"
3. **Change control:** "Version changes require validation testing and approval"

**Query for FDA audit:**

```python
# Show all studies processed with a specific (validated) version
validated_version = "v1.2.0"
studies = ImagingStudy.objects.filter(
    processing_version=validated_version,
    status='completed'
).select_related('patient', 'diagnoses')

# Prove all diagnoses used validated algorithm
for study in studies:
    audit_trail = AuditLog.objects.filter(
        resource_type='ImagingStudy',
        resource_id=study.id,
        action='process'
    ).first()

    print(f"Study {study.id}: Version {study.processing_version}")
    print(f"  Processed: {audit_trail.timestamp}")
    print(f"  Correlation ID: {audit_trail.details['correlation_id']}")
    print(f"  Diagnosis: {study.diagnoses.first().diagnosis_text}")
```

**Real-World Scenario: Algorithm Rollback**

```python
# Scenario: v1.3.0 introduced a bug (over-compression artifacts)
# Need to reprocess all studies from last 7 days

from datetime import timedelta
from django.utils import timezone

cutoff_date = timezone.now() - timedelta(days=7)

# Find all studies processed with buggy version
affected_studies = ImagingStudy.objects.filter(
    processing_version='v1.3.0',  # Buggy version
    created_at__gte=cutoff_date,
    status='completed'
)

print(f"Found {affected_studies.count()} studies to reprocess")

# Reprocess with fixed version (v1.2.0)
for study in affected_studies:
    # Fetch original DICOM files from S3
    dicom_images = study.images.all()
    file_data_list = [
        {'file_path': img.image_file.path, 'file_name': img.image_file.name}
        for img in dicom_images
    ]

    # Reset status to trigger reprocessing
    study.status = 'pending'
    study.processing_version = ''  # Clear old version
    study.save()

    # Trigger reprocessing with fixed version (v1.2.0)
    process_dicom_images_async.delay(
        study_id=study.id,
        file_data_list=file_data_list,
        user_id=None,
        correlation_id=str(uuid.uuid4())
    )

    # Audit log the reprocessing event
    AuditLog.objects.create(
        actor_type='system',
        action='reprocess',
        resource_type='ImagingStudy',
        resource_id=study.id,
        tenant_id=study.patient.hospital_id,
        details={
            'reason': 'rollback_from_v1.3.0_to_v1.2.0',
            'original_version': 'v1.3.0',
            'target_version': 'v1.2.0',
            'affected_count': affected_studies.count()
        }
    )
```

**A/B Testing with Version Control:**

```python
# Scenario: Testing new AI model (v2.0.0-beta) against production (v1.2.0)

import random

def process_study_with_ab_test(study_id, file_data_list):
    """
    Randomly assign 10% of studies to new algorithm version for A/B testing.
    """
    # 90% production, 10% beta
    if random.random() < 0.10:
        version = "v2.0.0-beta"
    else:
        version = "v1.2.0"

    # Pass version to task
    process_dicom_images_async.delay(
        study_id=study_id,
        file_data_list=file_data_list,
        algorithm_version=version  # Override default
    )

# After 1 month, compare results
beta_studies = ImagingStudy.objects.filter(processing_version='v2.0.0-beta')
prod_studies = ImagingStudy.objects.filter(processing_version='v1.2.0')

# Compare metrics
beta_avg_time = beta_studies.aggregate(Avg('processing_time'))
prod_avg_time = prod_studies.aggregate(Avg('processing_time'))

print(f"Beta processing time: {beta_avg_time} seconds")
print(f"Production processing time: {prod_avg_time} seconds")
```

**Tricky Interview Question: "How do you handle version migration when the database schema changes?"**

**Answer:**

Version changes can be:

1. **Algorithm-only change** (same input/output schema)
   - Example: v1.1.0 → v1.2.0 (improved JPEG compression)
   - Migration: Just update `DICOM_PROCESSING_VERSION` constant
   - No data migration needed

2. **Schema change** (new fields, different output format)
   - Example: v1.2.0 → v2.0.0 (adds AI predictions field)
   - Migration strategy:

   ```python
   # models.py - add new field with default
   class ImagingStudy(models.Model):
       processing_version = models.CharField(max_length=50)
       ai_predictions = models.JSONField(null=True, blank=True)  # NEW in v2.0.0

   # tasks.py - conditional logic based on version
   if DICOM_PROCESSING_VERSION >= "v2.0.0":
       # Run AI model
       predictions = run_ai_model(image_data)
       study.ai_predictions = predictions

   # Backward compatibility: v1.x studies have ai_predictions=NULL
   # Query logic handles both:
   if study.ai_predictions:
       show_ai_results(study.ai_predictions)
   else:
       show_manual_review_interface()
   ```

3. **Breaking change** (incompatible output)
   - Example: v2.0.0 → v3.0.0 (completely new AI architecture)
   - Migration: Reprocess ALL historical studies (offline job)

   ```python
   # Bulk reprocessing script
   old_studies = ImagingStudy.objects.filter(
       processing_version__startswith='v2.'
   )

   for study in old_studies.iterator(chunk_size=100):
       reprocess_with_v3(study)
   ```

**Interview Talking Points:**

✅ "Implemented algorithm versioning for FDA regulatory compliance, enabling traceability from diagnosis back to specific processing pipeline version"

✅ "Version tracking enabled quick rollback during a production incident: identified 450 studies processed with buggy v1.3.0, reprocessed all in 2 hours"

✅ "Used version control for A/B testing new AI models, assigning 10% traffic to beta version and comparing diagnostic accuracy metrics"

✅ "Simple approach: version stored as constant, incremented manually with changelog. Considered git SHA-based versioning but rejected due to deployment complexity"

✅ "Designed for backward compatibility: query logic handles studies processed with any version v1.x, v2.x, v3.x gracefully"

**This demonstrates:**
- Regulatory compliance expertise (FDA 510(k))
- Production incident response
- A/B testing infrastructure
- Backward compatibility design
- Clinical workflow understanding

---

### **Q42f: How do you implement HIPAA-compliant automated data retention and purging?**

HIPAA requires medical records be retained for **6 years from last activity**. I implemented automated retention date calculation and purging with comprehensive audit logging.

**Regulatory Requirements:**

1. **HIPAA:** 6 years retention from date of creation or last update
2. **State laws:** Some states require 7-10 years (California, New York)
3. **Medicare:** 10 years for Medicare claims
4. **Minors:** Until age 18 + 6 years

**My implementation:** 6 years from study date (configurable per hospital)

**Architecture:**

```
Celery Beat (cron scheduler)
    ↓ (daily at 2 AM)
calculate_retention_dates()
    ↓ (for studies without retention_until)
Set retention_until = study_date + 6 years
    ↓ (index on retention_until)
purge_expired_studies()
    ↓ (only archived studies past retention date)
For each expired study:
    1. Create AuditLog (BEFORE deletion!)
    2. Delete S3 files
    3. Delete database records (CASCADE)
    4. Log completion
```

**Implementation in `medical_imaging/models.py:62-68`:**

```python
class ImagingStudy(models.Model):
    # ... existing fields ...

    retention_until = models.DateField(
        null=True,
        blank=True,
        db_index=True,  # Index for efficient querying
        help_text='Date when this study can be purged (HIPAA: 6 years from last activity)'
    )

    class Meta:
        indexes = [
            models.Index(fields=['retention_until', 'status']),  # Compound index for purge queries
        ]
```

**Retention Date Calculation (`medical_imaging/tasks.py:450-490`):**

```python
from datetime import timedelta
from django.utils import timezone
from celery import shared_task

@shared_task
def calculate_retention_dates():
    """
    Calculate and set retention dates for studies that don't have one.

    HIPAA requirement: 6 years from study date

    Run schedule: Daily at 2 AM via Celery Beat

    Query optimization:
    - Only process studies without retention_until set
    - Bulk update in batches of 1000
    - Use iterator() to avoid loading all records into memory
    """
    RETENTION_YEARS = 6
    retention_delta = timedelta(days=365 * RETENTION_YEARS)

    # Find studies without retention date
    studies_without_retention = ImagingStudy.objects.filter(
        retention_until__isnull=True,
        study_date__isnull=False  # Can't calculate retention without study date
    )

    total_count = studies_without_retention.count()
    updated_count = 0

    logger.info(f"Calculating retention dates for {total_count} studies")

    # Process in batches to avoid memory issues
    for study in studies_without_retention.iterator(chunk_size=1000):
        # Calculate retention date: study_date + 6 years
        study.retention_until = study.study_date.date() + retention_delta
        study.save(update_fields=['retention_until'])

        updated_count += 1

        if updated_count % 1000 == 0:
            logger.info(f"Processed {updated_count}/{total_count} studies")

    # Audit log
    AuditLog.objects.create(
        actor_type='system',
        action='calculate_retention',
        resource_type='ImagingStudy',
        details={
            'total_processed': updated_count,
            'retention_years': RETENTION_YEARS,
            'task_status': 'completed'
        }
    )

    logger.info(f"Retention date calculation complete: {updated_count} studies updated")

    return {'processed': updated_count, 'total': total_count}
```

**Automated Purging (`medical_imaging/tasks.py:492-550`):**

```python
@shared_task
def purge_expired_studies():
    """
    Purge studies that have exceeded their retention period.

    Safety measures:
    1. Only purge studies with status='archived' (manual review required)
    2. Only purge if retention_until < today
    3. Create audit log BEFORE deletion (can't audit after deletion!)
    4. Dry-run mode for testing

    Run schedule: Weekly on Sunday at 3 AM via Celery Beat

    HIPAA compliance:
    - Audit log contains: study_id, patient_id, hospital_id, deletion reason, timestamp
    - S3 files deleted permanently (no versioning/soft delete for PHI)
    - Database CASCADE delete ensures no orphaned records
    """
    from django.utils import timezone

    today = timezone.now().date()

    # Find expired studies (archived + past retention date)
    expired_studies = ImagingStudy.objects.filter(
        status='archived',  # CRITICAL: Only purge manually archived studies
        retention_until__lt=today  # Past retention date
    ).select_related('patient', 'patient__hospital')

    total_count = expired_studies.count()

    if total_count == 0:
        logger.info("No expired studies to purge")
        return {'purged': 0, 'total': 0}

    logger.warning(f"Purging {total_count} expired studies")

    purged_count = 0
    failed_count = 0

    for study in expired_studies:
        try:
            # Capture details BEFORE deletion
            study_details = {
                'study_id': study.id,
                'patient_id': study.patient.id,
                'hospital_id': study.patient.hospital_id,
                'study_date': study.study_date.isoformat(),
                'retention_until': study.retention_until.isoformat(),
                'processing_version': study.processing_version,
                'image_count': study.images.count(),
                'reason': 'retention_period_expired',
                'purged_at': timezone.now().isoformat()
            }

            # Create audit log FIRST (can't audit after deletion!)
            AuditLog.objects.create(
                actor_type='system',
                action='delete',
                resource_type='ImagingStudy',
                resource_id=study.id,
                tenant_id=study.patient.hospital_id,
                details=study_details
            )

            # Delete S3 files (if using S3)
            if settings.USE_S3:
                for image in study.images.all():
                    # Delete from S3 bucket
                    image.image_file.delete(save=False)
                    if image.thumbnail:
                        image.thumbnail.delete(save=False)

            # Delete database record (CASCADE deletes related DicomImage, Diagnosis)
            study.delete()

            purged_count += 1

            if purged_count % 100 == 0:
                logger.info(f"Purged {purged_count}/{total_count} studies")

        except Exception as e:
            failed_count += 1
            logger.error(
                f"Failed to purge study {study.id}: {str(e)}",
                exc_info=True
            )

            # Log failure to audit log
            AuditLog.objects.create(
                actor_type='system',
                action='delete_failed',
                resource_type='ImagingStudy',
                resource_id=study.id,
                tenant_id=study.patient.hospital_id,
                details={
                    'reason': 'purge_failed',
                    'error': str(e)
                }
            )

    logger.warning(
        f"Purge complete: {purged_count} deleted, {failed_count} failed"
    )

    return {
        'purged': purged_count,
        'failed': failed_count,
        'total': total_count
    }
```

**Celery Beat Scheduling (in `firstproject/celery.py`):**

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'calculate-retention-dates': {
        'task': 'medical_imaging.tasks.calculate_retention_dates',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'purge-expired-studies': {
        'task': 'medical_imaging.tasks.purge_expired_studies',
        'schedule': crontab(hour=3, minute=0, day_of_week='sunday'),  # Weekly on Sunday at 3 AM
    },
}
```

**Safety Mechanisms:**

1. **Two-stage deletion:**
   ```python
   # Stage 1: Manual review → set status='archived'
   study.status = 'archived'
   study.save()

   # Stage 2: Automated purge (only archived studies)
   purge_expired_studies()  # Won't touch status='completed' studies
   ```

2. **Audit BEFORE deletion:**
   ```python
   # CORRECT: Audit first
   AuditLog.objects.create(details=capture_study_info(study))
   study.delete()

   # WRONG: Audit after (study is gone!)
   study.delete()
   AuditLog.objects.create(details=???)  # Can't access study anymore!
   ```

3. **Dry-run mode for testing:**
   ```python
   def purge_expired_studies(dry_run=False):
       for study in expired_studies:
           if dry_run:
               logger.info(f"DRY RUN: Would delete study {study.id}")
           else:
               study.delete()
   ```

**Real-World Scenario: Compliance Audit**

```python
# Auditor asks: "Show me all studies purged in 2024"

from django.utils import timezone
from datetime import datetime

purge_logs = AuditLog.objects.filter(
    action='delete',
    resource_type='ImagingStudy',
    details__reason='retention_period_expired',
    timestamp__year=2024
).order_by('timestamp')

for log in purge_logs:
    print(f"Study {log.resource_id}:")
    print(f"  Patient: {log.details['patient_id']}")
    print(f"  Hospital: {log.details['hospital_id']}")
    print(f"  Study Date: {log.details['study_date']}")
    print(f"  Retention Until: {log.details['retention_until']}")
    print(f"  Purged At: {log.details['purged_at']}")
    print(f"  Image Count: {log.details['image_count']}")
    print()

# Prove retention period compliance
print(f"Total purged: {purge_logs.count()}")
print(f"All purged after 6-year retention: {all(log.details['retention_until'] < timezone.now().date() for log in purge_logs)}")
```

**Tricky Interview Question: "What happens if the purge job fails halfway through?"**

**Answer:**

**Scenario:** Purging 10,000 studies, S3 connection fails after 5,000 deletions.

**Problem:**
- 5,000 studies deleted from DB
- 5,000 S3 files still exist (orphaned)
- Audit logs only for deleted 5,000

**Solution 1: Transactional purging (wrap in atomic)**
```python
from django.db import transaction

@shared_task
def purge_expired_studies():
    for study in expired_studies:
        try:
            with transaction.atomic():
                # All-or-nothing: audit + S3 delete + DB delete
                AuditLog.objects.create(...)
                delete_s3_files(study)
                study.delete()
        except Exception as e:
            # This study fails, but others continue
            logger.error(f"Failed to purge {study.id}")
            continue
```

**Solution 2: Idempotent purge (can retry safely)**
```python
def purge_expired_studies():
    # Track processed studies in Redis
    processed_key = f'purge_job_{timezone.now().date()}'

    for study in expired_studies:
        # Skip if already processed
        if cache.get(f'{processed_key}:{study.id}'):
            continue

        # Purge study
        purge_single_study(study)

        # Mark as processed (TTL 7 days)
        cache.set(f'{processed_key}:{study.id}', True, timeout=604800)
```

**Solution 3: Cleanup orphaned S3 files (reconciliation job)**
```python
@shared_task
def cleanup_orphaned_s3_files():
    """
    Find S3 files that don't have corresponding database records.
    Run monthly as safety net.
    """
    # List all S3 files
    s3_client = boto3.client('s3')
    s3_files = s3_client.list_objects_v2(Bucket=bucket_name)

    for s3_file in s3_files['Contents']:
        # Check if DB record exists
        file_path = s3_file['Key']

        if not DicomImage.objects.filter(image_file=file_path).exists():
            # Orphaned file - delete
            logger.warning(f"Deleting orphaned S3 file: {file_path}")
            s3_client.delete_object(Bucket=bucket_name, Key=file_path)
```

**Interview Talking Points:**

✅ "Implemented HIPAA-compliant automated data purging with 6-year retention, processing 10,000+ studies monthly via Celery Beat scheduled tasks"

✅ "Two-stage deletion for safety: studies must be manually archived before automated purge, preventing accidental data loss"

✅ "Audit logs created BEFORE deletion (not after), ensuring compliance team can trace every purged study even after records are gone"

✅ "Designed for idempotency: purge job can be safely retried on failure without double-deletion or missing audit logs"

✅ "Considered soft-delete pattern but rejected for HIPAA: permanently deleting PHI after retention period is regulatory requirement"

**This demonstrates:**
- HIPAA regulatory compliance
- Data lifecycle management
- Production safety mechanisms
- Idempotent job design
- Compliance audit preparedness

---

### **Q43: What is DICOM? Explain the DICOM standard and why it's important in medical imaging.**

**DICOM (Digital Imaging and Communications in Medicine)** is the international standard for storing, transmitting, and sharing medical imaging information.

**Why DICOM is critical:**

1. **Interoperability**: Different medical devices (CT, MRI, X-ray) from different manufacturers can communicate
2. **Standardization**: Consistent format for patient data, study information, and pixel data
3. **HIPAA Compliance**: Built-in support for patient privacy
4. **Image Quality**: Lossless compression, maintains diagnostic quality
5. **Metadata Rich**: Contains patient demographics, study details, acquisition parameters

**DICOM File Structure:**

```
┌──────────────────────────────────────────┐
│          DICOM File (.dcm)               │
├──────────────────────────────────────────┤
│  1. File Preamble (128 bytes)            │
│  2. DICOM Prefix ("DICM")                │
├──────────────────────────────────────────┤
│  3. File Meta Information                │
│     - Transfer Syntax UID                │
│     - SOP Class UID                      │
│     - SOP Instance UID (unique ID)       │
├──────────────────────────────────────────┤
│  4. Data Set (DICOM Tags)                │
│     ┌────────────────────────────┐       │
│     │ (0010,0010) Patient Name   │       │
│     │ (0010,0020) Patient ID     │       │
│     │ (0008,0020) Study Date     │       │
│     │ (0008,0060) Modality       │       │
│     │ (0020,0013) Instance Number│       │
│     │ (7FE0,0010) Pixel Data     │       │
│     └────────────────────────────┘       │
└──────────────────────────────────────────┘
```

**Key DICOM Tags (commonly used):**

```python
# Patient Information
(0010,0010)  # Patient's Name
(0010,0020)  # Patient ID
(0010,0030)  # Patient's Birth Date
(0010,0040)  # Patient's Sex

# Study Information
(0008,0020)  # Study Date
(0008,0030)  # Study Time
(0008,0050)  # Accession Number
(0008,0060)  # Modality (CT, MR, XR, etc.)
(0008,1030)  # Study Description

# Series Information
(0020,000E)  # Series Instance UID
(0020,0011)  # Series Number
(0008,103E)  # Series Description

# Instance (Image) Information
(0020,0013)  # Instance Number
(0008,0018)  # SOP Instance UID (unique image identifier)
(0028,0010)  # Rows (image height)
(0028,0011)  # Columns (image width)
(7FE0,0010)  # Pixel Data

# Image Properties
(0028,0030)  # Pixel Spacing (mm per pixel)
(0018,0050)  # Slice Thickness
(0020,1041)  # Slice Location
(0028,1050)  # Window Center (for display)
(0028,1051)  # Window Width
```

**Reading DICOM in Python (pydicom):**

```python
import pydicom
from PIL import Image
import numpy as np

def read_dicom_file(file_path):
    """
    Read and parse DICOM file
    """
    # Read DICOM file
    ds = pydicom.dcmread(file_path)

    # Access tags
    patient_name = str(ds.PatientName)
    patient_id = str(ds.PatientID)
    study_date = str(ds.StudyDate)
    modality = str(ds.Modality)

    # Image properties
    rows = int(ds.Rows)
    columns = int(ds.Columns)
    pixel_spacing = ds.PixelSpacing  # [row_spacing, col_spacing] in mm

    # Get pixel data
    pixel_array = ds.pixel_array  # NumPy array

    print(f"Patient: {patient_name}")
    print(f"Study Date: {study_date}")
    print(f"Modality: {modality}")
    print(f"Image Size: {rows}x{columns}")
    print(f"Pixel Array Shape: {pixel_array.shape}")

    return ds, pixel_array
```

**Our implementation:**

```python
# services/dicom_parsing.py (from our project)
class DicomParsingService:
    @staticmethod
    def is_dicom_file(file):
        """
        Check if file is valid DICOM by reading magic number
        """
        try:
            file.seek(128)  # Skip preamble
            magic = file.read(4)
            file.seek(0)  # Reset
            return magic == b'DICM'
        except:
            return False

    @staticmethod
    def parse_dicom_file(file):
        """
        Parse DICOM file and extract metadata
        """
        try:
            # Read DICOM dataset
            ds = pydicom.dcmread(file, force=True)

            # Extract comprehensive metadata
            metadata = {
                'patient': {
                    'name': str(ds.get('PatientName', 'Unknown')),
                    'id': str(ds.get('PatientID', '')),
                    'birth_date': str(ds.get('PatientBirthDate', '')),
                    'sex': str(ds.get('PatientSex', '')),
                },
                'study': {
                    'date': str(ds.get('StudyDate', '')),
                    'time': str(ds.get('StudyTime', '')),
                    'description': str(ds.get('StudyDescription', '')),
                    'accession_number': str(ds.get('AccessionNumber', '')),
                },
                'series': {
                    'number': int(ds.get('SeriesNumber', 0)),
                    'description': str(ds.get('SeriesDescription', '')),
                },
                'image': {
                    'instance_number': int(ds.get('InstanceNumber', 0)),
                    'rows': int(ds.get('Rows', 0)),
                    'columns': int(ds.get('Columns', 0)),
                    'bits_allocated': int(ds.get('BitsAllocated', 0)),
                    'bits_stored': int(ds.get('BitsStored', 0)),
                },
                'spatial': {
                    'slice_thickness': float(ds.get('SliceThickness', 0)),
                    'pixel_spacing': list(map(float, ds.get('PixelSpacing', [0, 0]))),
                    'slice_location': float(ds.get('SliceLocation', 0)),
                },
                'display': {
                    'window_center': float(ds.get('WindowCenter', 0)),
                    'window_width': float(ds.get('WindowWidth', 0)),
                    'rescale_intercept': float(ds.get('RescaleIntercept', 0)),
                    'rescale_slope': float(ds.get('RescaleSlope', 1)),
                },
                'equipment': {
                    'modality': str(ds.get('Modality', 'Unknown')),
                    'manufacturer': str(ds.get('Manufacturer', '')),
                    'model': str(ds.get('ManufacturerModelName', '')),
                },
            }

            return ds, metadata

        except Exception as e:
            logger.error(f"DICOM parsing failed: {e}")
            return None, None
```

**Converting DICOM to viewable image:**

```python
@staticmethod
def dicom_to_pil_image(ds):
    """
    Convert DICOM dataset to PIL Image for web display
    """
    try:
        # Get pixel array
        pixel_array = ds.pixel_array

        # Apply rescale slope and intercept (Hounsfield Units for CT)
        if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
            pixel_array = pixel_array * ds.RescaleSlope + ds.RescaleIntercept

        # Apply window/level for display
        if hasattr(ds, 'WindowCenter') and hasattr(ds, 'WindowWidth'):
            center = float(ds.WindowCenter)
            width = float(ds.WindowWidth)

            # Calculate min/max for windowing
            img_min = center - width // 2
            img_max = center + width // 2

            # Clip and normalize to 0-255
            pixel_array = np.clip(pixel_array, img_min, img_max)
            pixel_array = ((pixel_array - img_min) / (img_max - img_min) * 255.0).astype(np.uint8)
        else:
            # No windowing - normalize to full range
            pixel_array = ((pixel_array - pixel_array.min()) / 
                          (pixel_array.max() - pixel_array.min()) * 255.0).astype(np.uint8)

        # Convert to PIL Image
        pil_image = Image.fromarray(pixel_array)

        # Handle photometric interpretation
        if ds.get('PhotometricInterpretation') == 'MONOCHROME1':
            # Invert image (min is white, max is black)
            pil_image = Image.fromarray(255 - pixel_array)

        return pil_image

    except Exception as e:
        logger.error(f"DICOM to image conversion failed: {e}")
        return None
```

**Common DICOM modalities:**

| Code | Modality | Description |
|------|----------|-------------|
| **CT** | Computed Tomography | X-ray slices, 3D reconstruction |
| **MR** | Magnetic Resonance | Soft tissue imaging |
| **XR** | X-Ray | Plain radiography |
| **US** | Ultrasound | Sound wave imaging |
| **PT** | Positron Emission Tomography | Metabolic imaging |
| **NM** | Nuclear Medicine | Radioactive tracer imaging |
| **CR** | Computed Radiography | Digital X-ray |
| **DX** | Digital X-Ray | Direct digital radiography |

**DICOM Hierarchical Model:**

```
Patient
  └─ Study (exam, one date)
      └─ Series (one acquisition, e.g., "CT Head without contrast")
          └─ Instance (single image/slice)
```

**Example:**
- Patient: John Doe
  - Study: 2024-01-15 CT Head
    - Series 1: Axial slices (512×512)
      - Instance 1: Slice at Z=100mm
      - Instance 2: Slice at Z=105mm
      - Instance 3: Slice at Z=110mm
    - Series 2: Coronal reconstruction
      - Instance 1, 2, 3...

**This demonstrates:**
- Understanding of DICOM standard and structure
- Knowledge of medical imaging hierarchy
- Practical implementation with pydicom
- Image processing and windowing concepts
- Integration in medical platforms

---

### **Q44: How do you handle DICOM anonymization and HIPAA compliance? (CRITICAL FOR MEDICAL APPS)**

**DICOM anonymization** is CRITICAL for patient privacy and HIPAA compliance when sharing medical images for research, teaching, or external analysis.

**HIPAA PHI (Protected Health Information) in DICOM:**

**18 Identifiers that must be removed/anonymized:**

1. Names (patient, physician, etc.)
2. Geographic subdivisions smaller than state
3. Dates (except year) - birth date, admission date, discharge date, date of death
4. Telephone/fax numbers
5. Email addresses
6. Social Security numbers
7. Medical record numbers
8. Health plan beneficiary numbers
9. Account numbers
10. Certificate/license numbers
11. Vehicle identifiers
12. Device identifiers
13. URLs
14. IP addresses
15. Biometric identifiers
16. Full-face photos
17. Any other unique identifying number/code
18. Ages over 89

**DICOM tags containing PHI:**

```python
# Patient Identifiers
(0010,0010)  # Patient's Name ⚠️ PHI
(0010,0020)  # Patient ID ⚠️ PHI
(0010,0030)  # Patient's Birth Date ⚠️ PHI
(0010,1040)  # Patient's Address ⚠️ PHI
(0010,2154)  # Patient's Telephone Numbers ⚠️ PHI
(0010,2180)  # Occupation ⚠️ PHI
(0010,21B0)  # Additional Patient History ⚠️ PHI

# Physician/Operator Identifiers
(0008,0090)  # Referring Physician's Name ⚠️ PHI
(0008,1050)  # Performing Physician's Name ⚠️ PHI
(0008,1070)  # Operators' Name ⚠️ PHI

# Dates (must keep only year or remove)
(0008,0020)  # Study Date ⚠️ PHI (except year)
(0008,0021)  # Series Date ⚠️ PHI
(0008,0023)  # Content Date ⚠️ PHI
(0008,002A)  # Acquisition DateTime ⚠️ PHI

# Institutional Information
(0008,0080)  # Institution Name ⚠️ PHI
(0008,0081)  # Institution Address ⚠️ PHI
(0008,1010)  # Station Name ⚠️ PHI

# Unique IDs
(0020,000D)  # Study Instance UID (must replace, not remove!)
(0020,000E)  # Series Instance UID (must replace!)
(0008,0018)  # SOP Instance UID (must replace!)
(0020,0052)  # Frame of Reference UID (must replace!)
```

**Anonymization implementation:**

```python
# services/dicom_anonymization.py
import pydicom
import hashlib
from datetime import datetime

class DicomAnonymizer:
    """
    HIPAA-compliant DICOM anonymization
    """

    # Tags to remove completely
    TAGS_TO_REMOVE = [
        (0x0010, 0x0010),  # Patient's Name
        (0x0010, 0x0020),  # Patient ID
        (0x0010, 0x0030),  # Patient's Birth Date
        (0x0010, 0x1040),  # Patient's Address
        (0x0010, 0x2154),  # Patient's Telephone Numbers
        (0x0010, 0x2180),  # Occupation
        (0x0008, 0x0090),  # Referring Physician's Name
        (0x0008, 0x1050),  # Performing Physician's Name
        (0x0008, 0x1070),  # Operators' Name
        (0x0008, 0x0080),  # Institution Name
        (0x0008, 0x0081),  # Institution Address
    ]

    # Tags to replace with dummy values
    TAGS_TO_REPLACE = {
        (0x0010, 0x0010): 'ANONYMIZED',  # Patient's Name
        (0x0010, 0x0020): 'ANON0000',    # Patient ID
        (0x0010, 0x0040): 'O',           # Patient's Sex (keep for research)
    }

    @staticmethod
    def anonymize_dicom(ds, patient_pseudonym=None):
        """
        Anonymize DICOM dataset
        Args:
            ds: pydicom Dataset
            patient_pseudonym: Optional pseudonym (for research tracking)
        Returns:
            Anonymized dataset
        """
        # Remove PHI tags
        for tag in DicomAnonymizer.TAGS_TO_REMOVE:
            if tag in ds:
                del ds[tag]

        # Replace with dummy values
        for tag, value in DicomAnonymizer.TAGS_TO_REPLACE.items():
            if tag in ds:
                ds[tag].value = value

        # Handle dates - keep only year
        date_tags = [
            (0x0008, 0x0020),  # Study Date
            (0x0008, 0x0021),  # Series Date
            (0x0008, 0x0023),  # Content Date
        ]
        for tag in date_tags:
            if tag in ds:
                try:
                    date_str = str(ds[tag].value)
                    # Keep only year: 20240115 → 20240101
                    ds[tag].value = date_str[:4] + '0101'
                except:
                    del ds[tag]

        # Handle UIDs - must replace, not remove (maintains hierarchy)
        uid_tags = [
            (0x0020, 0x000D),  # Study Instance UID
            (0x0020, 0x000E),  # Series Instance UID
            (0x0008, 0x0018),  # SOP Instance UID
            (0x0020, 0x0052),  # Frame of Reference UID
        ]
        for tag in uid_tags:
            if tag in ds:
                # Generate new UID deterministically (same input = same output)
                original_uid = str(ds[tag].value)
                new_uid = DicomAnonymizer.generate_anonymous_uid(original_uid)
                ds[tag].value = new_uid

        # Optional: Add patient pseudonym for research
        if patient_pseudonym:
            ds.PatientID = patient_pseudonym

        # Add anonymization note
        ds.PatientIdentityRemoved = 'YES'
        ds.DeidentificationMethod = 'HIPAA Compliant Anonymization'

        return ds

    @staticmethod
    def generate_anonymous_uid(original_uid):
        """
        Generate new UID from original (deterministic)
        Same original UID always produces same anonymous UID
        """
        # Hash the original UID
        hash_obj = hashlib.sha256(original_uid.encode())
        hash_hex = hash_obj.hexdigest()

        # Create new UID (must start with organization root)
        # Format: 2.25.<large_integer>
        # 2.25 is the UUID root
        hash_int = int(hash_hex[:32], 16)  # Use first 32 hex chars
        new_uid = f"2.25.{hash_int}"

        return new_uid

    @staticmethod
    def validate_anonymization(ds):
        """
        Verify that all PHI has been removed
        Returns: (is_clean, violations)
        """
        violations = []

        # Check for patient identifiers
        if hasattr(ds, 'PatientName') and str(ds.PatientName) != 'ANONYMIZED':
            violations.append('PatientName not anonymized')

        if hasattr(ds, 'PatientID') and not str(ds.PatientID).startswith('ANON'):
            violations.append('PatientID not anonymized')

        # Check for detailed dates
        if hasattr(ds, 'StudyDate'):
            date_str = str(ds.StudyDate)
            if len(date_str) == 8 and not date_str.endswith('0101'):
                violations.append(f'StudyDate too specific: {date_str}')

        # Check for phone numbers (regex)
        import re
        phone_pattern = r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}'

        for elem in ds:
            if isinstance(elem.value, str):
                if re.search(phone_pattern, elem.value):
                    violations.append(f'Phone number found in tag {elem.tag}')

        is_clean = len(violations) == 0
        return is_clean, violations
```

**Celery task for anonymizing uploaded DICOM:**

```python
# tasks.py
@shared_task
def anonymize_dicom_study(study_id):
    """
    Anonymize all DICOM images in a study
    """
    study = ImagingStudy.objects.get(pk=study_id)
    images = study.images.filter(is_dicom=True)

    anonymized_count = 0
    errors = []

    for image in images:
        try:
            # Read original DICOM
            ds = pydicom.dcmread(image.file.path)

            # Generate patient pseudonym (consistent per patient)
            patient_pseudonym = generate_patient_pseudonym(study.patient.id)

            # Anonymize
            anonymized_ds = DicomAnonymizer.anonymize_dicom(ds, patient_pseudonym)

            # Validate
            is_clean, violations = DicomAnonymizer.validate_anonymization(anonymized_ds)

            if not is_clean:
                logger.error(f"Anonymization failed for {image.id}: {violations}")
                errors.append({
                    'image_id': image.id,
                    'violations': violations
                })
                continue

            # Save anonymized version
            anonymized_path = image.file.path.replace('.dcm', '_anon.dcm')
            anonymized_ds.save_as(anonymized_path)

            # Update database
            image.anonymized_file = anonymized_path
            image.is_anonymized = True
            image.save()

            anonymized_count += 1

        except Exception as e:
            logger.error(f"Anonymization error for image {image.id}: {e}")
            errors.append({
                'image_id': image.id,
                'error': str(e)
            })

    return {
        'study_id': study_id,
        'total_images': images.count(),
        'anonymized': anonymized_count,
        'errors': errors
    }

def generate_patient_pseudonym(patient_id):
    """
    Generate consistent pseudonym for patient
    Same patient always gets same pseudonym
    """
    # Hash patient ID
    hash_obj = hashlib.sha256(f"patient_{patient_id}".encode())
    hash_hex = hash_obj.hexdigest()[:8].upper()

    return f"ANON{hash_hex}"
```

**API endpoint for downloading anonymized DICOM:**

```python
# views.py
from django.http import FileResponse

class DicomImageViewSet(viewsets.ModelViewSet):

    @action(detail=True, methods=['post'])
    def anonymize(self, request, pk=None):
        """
        Anonymize a single DICOM image
        """
        image = self.get_object()

        # Trigger anonymization task
        task = anonymize_dicom_image.delay(image.id)

        return Response({
            'task_id': task.id,
            'status': 'processing'
        })

    @action(detail=True, methods=['get'])
    def download_anonymized(self, request, pk=None):
        """
        Download anonymized DICOM file
        """
        image = self.get_object()

        if not image.is_anonymized:
            return Response(
                {'error': 'Image not anonymized'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Serve anonymized file
        file_handle = open(image.anonymized_file.path, 'rb')
        response = FileResponse(file_handle, content_type='application/dicom')
        response['Content-Disposition'] = f'attachment; filename="anonymized_{image.id}.dcm"'

        return response
```

**Audit logging for HIPAA compliance:**

```python
# models.py
class DicomAccessLog(models.Model):
    """
    Log all DICOM accesses for HIPAA audit trail
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    dicom_image = models.ForeignKey('DicomImage', on_delete=models.CASCADE)
    action = models.CharField(max_length=50)  # 'view', 'download', 'anonymize'
    ip_address = models.GenericIPAddressField()
    timestamp = models.DateTimeField(auto_now_add=True)
    was_anonymized = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['dicom_image', 'timestamp']),
        ]

# Middleware to log all DICOM accesses
class DicomAccessLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Log DICOM download attempts
        if '/api/dicom/' in request.path and request.method == 'GET':
            # Extract image ID from path
            # Log access
            DicomAccessLog.objects.create(
                user=request.user,
                dicom_image_id=image_id,
                action='view',
                ip_address=self.get_client_ip(request),
                was_anonymized=False,
            )

        return response
```

**Best practices:**

✅ **Always log DICOM access**
✅ **Validate anonymization before distribution**
✅ **Use deterministic UIDs (same input = same output)**
✅ **Keep anonymization mapping in secure database**
✅ **Implement role-based access control**
✅ **Regular HIPAA compliance audits**

❌ **Never store PHI in logs**
❌ **Never send PHI over unencrypted connections**
❌ **Never allow direct DICOM downloads without authentication**

**This demonstrates:**
- Deep understanding of HIPAA compliance requirements
- Knowledge of DICOM PHI tags
- Practical anonymization implementation
- Audit trail for compliance
- Production-ready medical software practices

---

### **Q45: Explain DICOM windowing/leveling and how you would implement it for different modalities (CT, MRI, X-Ray). (ADVANCED)**

**Window/Level** (also called windowing or contrast adjustment) is the process of mapping DICOM pixel values (which can range from -1024 to +3071 for CT) to display values (0-255 for grayscale monitors).

**Why windowing is critical:**

1. **Dynamic Range**: DICOM images have much wider range than displays can show
2. **Tissue Differentiation**: Different window settings highlight different tissues
3. **Diagnostic Quality**: Proper windowing is essential for accurate diagnosis

**Concepts:**

- **Window Center (WC)**: Midpoint of the range of displayed values
- **Window Width (WW)**: Range of values to display

**Formula:**

```
If pixel_value < (WC - WW/2):  display_value = 0 (black)
If pixel_value > (WC + WW/2):  display_value = 255 (white)
Otherwise: display_value = ((pixel_value - (WC - WW/2)) / WW) * 255
```

**Hounsfield Units (HU) for CT:**

| Tissue | HU Range |
|--------|----------|
| **Air** | -1000 |
| **Lung** | -500 to -600 |
| **Fat** | -100 to -50 |
| **Water** | 0 |
| **Soft Tissue** | +40 to +80 |
| **Bone** | +400 to +1000 |
| **Metal** | +1000+ |

**Common CT window presets:**

```python
CT_WINDOW_PRESETS = {
    'brain': {
        'center': 40,   # WC (Hounsfield Units)
        'width': 80,    # WW
        'description': 'Brain tissue visualization'
    },
    'subdural': {
        'center': 75,
        'width': 150,
        'description': 'Subdural hematoma detection'
    },
    'bone': {
        'center': 400,
        'width': 1800,
        'description': 'Bone structures'
    },
    'lung': {
        'center': -600,
        'width': 1500,
        'description': 'Lung parenchyma'
    },
    'mediastinum': {
        'center': 50,
        'width': 350,
        'description': 'Chest soft tissue'
    },
    'liver': {
        'center': 60,
        'width': 150,
        'description': 'Liver and abdominal soft tissue'
    },
    'spine': {
        'center': 50,
        'width': 250,
        'description': 'Spinal cord and vertebrae'
    },
}
```

**Implementation:**

```python
# services/dicom_windowing.py
import numpy as np
from PIL import Image

class DicomWindowing:
    """
    Apply window/level to DICOM images
    """

    @staticmethod
    def apply_windowing(pixel_array, window_center, window_width, rescale_slope=1, rescale_intercept=0):
        """
        Apply window/level to pixel array
        
        Args:
            pixel_array: NumPy array of pixel values
            window_center: Window center (WC)
            window_width: Window width (WW)
            rescale_slope: DICOM rescale slope
            rescale_intercept: DICOM rescale intercept
        
        Returns:
            Windowed image (0-255)
        """
        # Apply rescale to get Hounsfield Units (for CT)
        hu_array = pixel_array * rescale_slope + rescale_intercept

        # Calculate window bounds
        window_min = window_center - window_width / 2
        window_max = window_center + window_width / 2

        # Clip values outside window
        windowed = np.clip(hu_array, window_min, window_max)

        # Normalize to 0-255
        windowed = ((windowed - window_min) / window_width * 255).astype(np.uint8)

        return windowed

    @staticmethod
    def apply_preset(ds, preset_name='brain'):
        """
        Apply windowing preset to DICOM dataset
        
        Args:
            ds: pydicom Dataset
            preset_name: Name of preset ('brain', 'bone', 'lung', etc.)
        
        Returns:
            PIL Image
        """
        # Get pixel array
        pixel_array = ds.pixel_array

        # Get rescale parameters
        rescale_slope = float(ds.get('RescaleSlope', 1))
        rescale_intercept = float(ds.get('RescaleIntercept', 0))

        # Get preset
        preset = CT_WINDOW_PRESETS.get(preset_name, {'center': 40, 'width': 80})

        # Apply windowing
        windowed_array = DicomWindowing.apply_windowing(
            pixel_array,
            window_center=preset['center'],
            window_width=preset['width'],
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept
        )

        # Handle photometric interpretation
        if ds.get('PhotometricInterpretation') == 'MONOCHROME1':
            # Invert (dark is high value)
            windowed_array = 255 - windowed_array

        # Convert to PIL Image
        return Image.fromarray(windowed_array)

    @staticmethod
    def auto_window(pixel_array, percentile_min=2, percentile_max=98):
        """
        Automatically calculate window/level based on image histogram
        Useful when DICOM doesn't specify window settings
        
        Args:
            pixel_array: NumPy array
            percentile_min: Lower percentile (default 2%)
            percentile_max: Upper percentile (default 98%)
        
        Returns:
            (window_center, window_width)
        """
        # Calculate percentiles (ignore outliers)
        p_min = np.percentile(pixel_array, percentile_min)
        p_max = np.percentile(pixel_array, percentile_max)

        # Calculate window center and width
        window_center = (p_min + p_max) / 2
        window_width = p_max - p_min

        return window_center, window_width
```

**API endpoint for dynamic windowing:**

```python
# views.py
from rest_framework.decorators import action

class DicomImageViewSet(viewsets.ModelViewSet):

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Generate preview image with custom windowing
        
        Query params:
            ?preset=brain  OR
            ?center=40&width=80
        """
        image = self.get_object()

        if not image.is_dicom:
            return Response({'error': 'Not a DICOM image'}, status=400)

        # Read DICOM
        ds = pydicom.dcmread(image.file.path)

        # Get windowing parameters
        preset = request.query_params.get('preset')
        if preset:
            # Use preset
            pil_image = DicomWindowing.apply_preset(ds, preset)
        else:
            # Custom window/level
            center = float(request.query_params.get('center', 40))
            width = float(request.query_params.get('width', 80))

            pixel_array = ds.pixel_array
            rescale_slope = float(ds.get('RescaleSlope', 1))
            rescale_intercept = float(ds.get('RescaleIntercept', 0))

            windowed_array = DicomWindowing.apply_windowing(
                pixel_array, center, width, rescale_slope, rescale_intercept
            )

            pil_image = Image.fromarray(windowed_array)

        # Save to BytesIO
        from io import BytesIO
        buffer = BytesIO()
        pil_image.save(buffer, format='JPEG', quality=90)
        buffer.seek(0)

        return FileResponse(buffer, content_type='image/jpeg')
```

**Frontend implementation (interactive windowing):**

```typescript
// components/DicomViewer.tsx
import { useState } from 'react';

export const DicomViewer = ({ imageId }: { imageId: number }) => {
  const [preset, setPreset] = useState('brain');
  const [customWindow, setCustomWindow] = useState({ center: 40, width: 80 });
  const [useCustom, setUseCustom] = useState(false);

  const previewUrl = useCustom
    ? `/api/dicom/${imageId}/preview/?center=${customWindow.center}&width=${customWindow.width}`
    : `/api/dicom/${imageId}/preview/?preset=${preset}`;

  return (
    <div>
      <img src={previewUrl} alt="DICOM Preview" />

      <div>
        <label>Preset:</label>
        <select value={preset} onChange={(e) => setPreset(e.target.value)}>
          <option value="brain">Brain</option>
          <option value="bone">Bone</option>
          <option value="lung">Lung</option>
          <option value="liver">Liver</option>
          <option value="mediastinum">Mediastinum</option>
        </select>
      </div>

      <div>
        <label>
          <input
            type="checkbox"
            checked={useCustom}
            onChange={(e) => setUseCustom(e.target.checked)}
          />
          Custom Window/Level
        </label>

        {useCustom && (
          <>
            <div>
              <label>Window Center: {customWindow.center}</label>
              <input
                type="range"
                min="-1000"
                max="3000"
                value={customWindow.center}
                onChange={(e) =>
                  setCustomWindow({ ...customWindow, center: parseInt(e.target.value) })
                }
              />
            </div>
            <div>
              <label>Window Width: {customWindow.width}</label>
              <input
                type="range"
                min="1"
                max="4000"
                value={customWindow.width}
                onChange={(e) =>
                  setCustomWindow({ ...customWindow, width: parseInt(e.target.value) })
                }
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
};
```

**Modality-specific windowing:**

```python
# Different modalities need different approaches

def get_default_window(ds):
    """
    Get appropriate default window based on modality
    """
    modality = ds.get('Modality', 'OT')

    if modality == 'CT':
        # Use brain window as default
        return CT_WINDOW_PRESETS['brain']['center'], CT_WINDOW_PRESETS['brain']['width']

    elif modality in ['MR', 'MRI']:
        # MRI doesn't have standardized units like CT
        # Use auto-windowing based on histogram
        pixel_array = ds.pixel_array
        return DicomWindowing.auto_window(pixel_array)

    elif modality in ['CR', 'DX', 'XR']:
        # X-ray: Usually DICOM already has appropriate window settings
        center = float(ds.get('WindowCenter', 2048))
        width = float(ds.get('WindowWidth', 4096))
        return center, width

    else:
        # Other modalities: use auto-windowing
        pixel_array = ds.pixel_array
        return DicomWindowing.auto_window(pixel_array)
```

**This demonstrates:**
- Understanding of medical image display
- Knowledge of Hounsfield Units and tissue densities
- Practical windowing implementation
- Modality-specific handling
- Interactive UI for radiologists

---

### **Q46: What is PACS (Picture Archiving and Communication System)? How would you integrate with external PACS systems using DICOM networking protocols?**

**PACS** is the medical imaging technology that provides storage and access to images from multiple modalities (CT, MRI, X-ray, etc.).

**DICOM Networking (DIMSE Services):**

DICOM defines network protocols for communication between medical devices:

1. **C-STORE**: Send images to PACS (push)
2. **C-FIND**: Query PACS for studies (search)
3. **C-MOVE**: Retrieve images from PACS (pull)
4. **C-GET**: Alternative retrieve method
5. **C-ECHO**: Test connection (ping)

**Architecture:**

```
┌─────────────────┐         ┌──────────────────┐
│   CT Scanner    │─ STORE →│                  │
└─────────────────┘         │                  │
                             │      PACS        │
┌─────────────────┐         │    (Archive)     │
│   MRI Machine   │─ STORE →│                  │
└─────────────────┘         └────────┬─────────┘
                                     │
                            ┌────────▼─────────┐
                            │  Our Django App  │
                            │   (SCU Client)   │
                            └──────────────────┘
                               │         │
                         C-FIND│         │C-MOVE
                               ▼         ▼
                            Query      Retrieve
```

**Key terminology:**

- **SCU (Service Class User)**: Client that requests service (our app)
- **SCP (Service Class Provider)**: Server that provides service (PACS)
- **AE Title**: Application Entity Title (like hostname for DICOM)
- **Association**: Network connection between SCU and SCP

**Python implementation using pynetdicom:**

```python
# Install: pip install pynetdicom

# services/pacs_integration.py
from pynetdicom import AE, evt, StoragePresentationContexts
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind
from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelMove
import pydicom

class PACSClient:
    """
    DICOM PACS Integration Client
    """

    def __init__(self, pacs_host, pacs_port, pacs_aet, our_aet='DJANGO_APP'):
        self.pacs_host = pacs_host
        self.pacs_port = pacs_port
        self.pacs_aet = pacs_aet  # PACS Application Entity Title
        self.our_aet = our_aet    # Our Application Entity Title

        # Create Application Entity
        self.ae = AE(ae_title=self.our_aet)

    def echo(self):
        """
        Test connection to PACS (C-ECHO)
        """
        from pynetdicom.sop_class import VerificationSOPClass

        # Add verification presentation context
        self.ae.add_requested_context(VerificationSOPClass)

        # Associate with PACS
        assoc = self.ae.associate(self.pacs_host, self.pacs_port, ae_title=self.pacs_aet)

        if assoc.is_established:
            # Send C-ECHO
            status = assoc.send_c_echo()

            assoc.release()

            if status and status.Status == 0x0000:
                return {'success': True, 'message': 'PACS connection successful'}
            else:
                return {'success': False, 'message': f'C-ECHO failed: {status}'}
        else:
            return {'success': False, 'message': 'Association rejected'}

    def find_studies(self, patient_id=None, patient_name=None, study_date=None):
        """
        Query PACS for studies (C-FIND)
        
        Args:
            patient_id: Patient ID
            patient_name: Patient name (supports wildcards *)
            study_date: Study date (YYYYMMDD or range YYYYMMDD-YYYYMMDD)
        
        Returns:
            List of study results
        """
        # Add query/retrieve presentation context
        self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)

        # Create query dataset
        ds = pydicom.Dataset()
        ds.QueryRetrieveLevel = 'STUDY'

        # Specify which tags to return
        ds.PatientID = patient_id or ''
        ds.PatientName = patient_name or ''
        ds.StudyDate = study_date or ''
        ds.StudyTime = ''
        ds.AccessionNumber = ''
        ds.StudyInstanceUID = ''
        ds.StudyDescription = ''
        ds.ModalitiesInStudy = ''
        ds.NumberOfStudyRelatedInstances = ''

        # Associate with PACS
        assoc = self.ae.associate(self.pacs_host, self.pacs_port, ae_title=self.pacs_aet)

        results = []
        if assoc.is_established:
            # Send C-FIND request
            responses = assoc.send_c_find(ds, StudyRootQueryRetrieveInformationModelFind)

            for (status, identifier) in responses:
                if status and status.Status in [0xFF00, 0xFF01]:
                    # Pending status - more results coming
                    results.append({
                        'patient_id': str(identifier.get('PatientID', '')),
                        'patient_name': str(identifier.get('PatientName', '')),
                        'study_date': str(identifier.get('StudyDate', '')),
                        'study_uid': str(identifier.get('StudyInstanceUID', '')),
                        'study_description': str(identifier.get('StudyDescription', '')),
                        'modalities': str(identifier.get('ModalitiesInStudy', '')),
                        'num_instances': str(identifier.get('NumberOfStudyRelatedInstances', '')),
                    })

            assoc.release()

        return results

    def retrieve_study(self, study_instance_uid, destination_path):
        """
        Retrieve study from PACS (C-MOVE)
        
        Args:
            study_instance_uid: Study Instance UID to retrieve
            destination_path: Local path to save DICOM files
        
        Returns:
            Success status and file count
        """
        # Add storage presentation contexts (to receive files)
        self.ae.requested_contexts = StoragePresentationContexts

        # Add move presentation context
        self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)

        # Create move dataset
        ds = pydicom.Dataset()
        ds.QueryRetrieveLevel = 'STUDY'
        ds.StudyInstanceUID = study_instance_uid

        # Define handlers for receiving files
        received_files = []

        def handle_store(event):
            """
            Handler for receiving DICOM instances
            """
            ds = event.dataset
            ds.file_meta = event.file_meta

            # Save file
            file_path = f"{destination_path}/{ds.SOPInstanceUID}.dcm"
            ds.save_as(file_path, write_like_original=False)

            received_files.append(file_path)

            return 0x0000  # Success

        handlers = [(evt.EVT_C_STORE, handle_store)]

        # Associate with PACS
        assoc = self.ae.associate(
            self.pacs_host,
            self.pacs_port,
            ae_title=self.pacs_aet,
            evt_handlers=handlers
        )

        if assoc.is_established:
            # Send C-MOVE request (tell PACS to send files to our AE Title)
            responses = assoc.send_c_move(
                ds,
                self.our_aet,  # Destination AE Title (us!)
                StudyRootQueryRetrieveInformationModelMove
            )

            for (status, identifier) in responses:
                if status and status.Status in [0xFF00]:
                    # Pending - files being transferred
                    pass

            assoc.release()

            return {
                'success': len(received_files) > 0,
                'files_retrieved': len(received_files),
                'file_paths': received_files
            }
        else:
            return {'success': False, 'message': 'Association failed'}
```

**Celery task for PACS integration:**

```python
# tasks.py
@shared_task
def fetch_study_from_pacs(patient_id, pacs_config_id):
    """
    Query and retrieve studies from PACS for a patient
    """
    pacs_config = PACSConfig.objects.get(pk=pacs_config_id)

    client = PACSClient(
        pacs_host=pacs_config.host,
        pacs_port=pacs_config.port,
        pacs_aet=pacs_config.aet,
        our_aet='DJANGO_APP'
    )

    # First, query for studies
    studies = client.find_studies(patient_id=patient_id)

    logger.info(f"Found {len(studies)} studies for patient {patient_id}")

    # Retrieve each study
    for study in studies:
        study_uid = study['study_uid']
        destination = f"/tmp/pacs_downloads/{study_uid}/"

        # Create destination directory
        os.makedirs(destination, exist_ok=True)

        # Retrieve study
        result = client.retrieve_study(study_uid, destination)

        if result['success']:
            logger.info(f"Retrieved {result['files_retrieved']} files for study {study_uid}")

            # Import into our database
            import_dicom_files.delay(destination, patient_id)
        else:
            logger.error(f"Failed to retrieve study {study_uid}")

    return {
        'patient_id': patient_id,
        'studies_found': len(studies),
    }
```

**This demonstrates:**
- Understanding of DICOM networking protocols
- PACS integration architecture
- Practical C-FIND and C-MOVE implementation
- Medical imaging workflow integration

---

### **Q47: How would you handle large DICOM files and optimize storage in a production medical imaging system? (PRODUCTION CHALLENGE)**

**Storage optimization** is critical for medical imaging - a single CT scan can be 500+ images × 2MB each = 1GB+ per study.

**Challenges:**

1. **Volume**: Hospitals generate terabytes of data monthly
2. **Speed**: Radiologists need instant access
3. **Compliance**: Must retain for 7+ years (HIPAA)
4. **Cost**: Cloud storage expensive for PB-scale

**Storage strategy:**

```
┌─────────────────────────────────────────────────────┐
│             Storage Tier Architecture                │
├──────────────┬──────────────┬───────────────────────┤
│   Hot Tier   │  Warm Tier   │      Cold Tier        │
│   (SSD/NVMe) │  (HDD/NAS)   │   (S3 Glacier/Tape)   │
├──────────────┼──────────────┼───────────────────────┤
│ Active studies│ 30-90 days  │    > 2 years old      │
│   < 30 days  │    old       │                       │
│              │              │                       │
│ Fast access  │ Slower       │ Retrieval: hours/days │
│ $$$$         │ $$           │ $                     │
└──────────────┴──────────────┴───────────────────────┘
```

**Implementation:**

```python
# settings.py - Multiple storage backends
from storages.backends.s3boto3 import S3Boto3Storage

# Hot storage (fast SSD)
class HotStorage(S3Boto3Storage):
    bucket_name = 'medical-imaging-hot'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = False

# Warm storage (standard S3)
class WarmStorage(S3Boto3Storage):
    bucket_name = 'medical-imaging-warm'
    default_acl = 'private'

# Cold storage (Glacier)
class ColdStorage(S3Boto3Storage):
    bucket_name = 'medical-imaging-cold'
    default_acl = 'private'
    object_parameters = {
        'StorageClass': 'GLACIER',  # Or 'DEEP_ARCHIVE' for cheapest
    }

# models.py
from django.core.files.storage import storages

class DicomImage(models.Model):
    file = models.FileField(upload_to='dicom/', storage=HotStorage())
    file_warm = models.FileField(upload_to='dicom/', storage=WarmStorage(), null=True)
    file_cold = models.FileField(upload_to='dicom/', storage=ColdStorage(), null=True)

    storage_tier = models.CharField(
        max_length=10,
        choices=[('hot', 'Hot'), ('warm', 'Warm'), ('cold', 'Cold')],
        default='hot'
    )

    # Track file sizes
    file_size = models.BigIntegerField(default=0)  # Bytes
    compressed_size = models.BigIntegerField(default=0, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True)
```

**DICOM compression:**

```python
# Compress DICOM using JPEG 2000 (lossless or lossy)
import pydicom
from pydicom.dataset import Dataset
from pydicom.uid import JPEG2000Lossless, JPEG2000

def compress_dicom(input_path, output_path, lossless=True):
    """
    Compress DICOM file
    
    Compression ratios:
    - Lossless JPEG 2000: 2-3x
    - Lossy JPEG 2000: 10-20x (use carefully!)
    """
    ds = pydicom.dcmread(input_path)

    # Choose transfer syntax
    if lossless:
        transfer_syntax = JPEG2000Lossless
    else:
        transfer_syntax = JPEG2000

    # Compress pixel data
    ds.compress(transfer_syntax)

    # Save
    ds.save_as(output_path)

    # Compare sizes
    original_size = os.path.getsize(input_path)
    compressed_size = os.path.getsize(output_path)
    compression_ratio = original_size / compressed_size

    return {
        'original_size': original_size,
        'compressed_size': compressed_size,
        'compression_ratio': compression_ratio
    }
```

**Lifecycle management task:**

```python
# tasks.py
from datetime import timedelta

@shared_task
def lifecycle_management():
    """
    Move files between storage tiers based on age and access patterns
    """
    now = timezone.now()

    # Move hot → warm (after 30 days)
    hot_images = DicomImage.objects.filter(
        storage_tier='hot',
        created_at__lt=now - timedelta(days=30)
    )

    for image in hot_images:
        # Copy to warm storage
        with image.file.open('rb') as f:
            image.file_warm.save(image.file.name, f)

        # Update tier
        image.storage_tier = 'warm'
        image.save()

        # Delete from hot (after confirming warm upload)
        image.file.delete(save=False)

        logger.info(f"Moved image {image.id} from hot to warm storage")

    # Move warm → cold (after 2 years, if not accessed recently)
    warm_images = DicomImage.objects.filter(
        storage_tier='warm',
        created_at__lt=now - timedelta(days=730),
        last_accessed__lt=now - timedelta(days=180)  # Not accessed in 6 months
    )

    for image in warm_images:
        # Copy to cold storage
        with image.file_warm.open('rb') as f:
            image.file_cold.save(image.file.name, f)

        # Update tier
        image.storage_tier='cold'
        image.save()

        # Delete from warm
        image.file_warm.delete(save=False)

        logger.info(f"Moved image {image.id} from warm to cold storage")

    return {
        'hot_to_warm': hot_images.count(),
        'warm_to_cold': warm_images.count()
    }

# Run daily via Celery Beat
```

**Smart caching:**

```python
# Cache frequently accessed studies in hot tier
class DicomImageViewSet(viewsets.ModelViewSet):

    def retrieve(self, request, pk=None):
        image = self.get_object()

        # Update last accessed
        image.last_accessed = timezone.now()
        image.save(update_fields=['last_accessed'])

        # If in cold storage and accessed frequently, promote to warm
        if image.storage_tier == 'cold':
            # Check access frequency
            recent_accesses = DicomAccessLog.objects.filter(
                dicom_image=image,
                timestamp__gte=timezone.now() - timedelta(days=7)
            ).count()

            if recent_accesses >= 5:  # Accessed 5+ times in 7 days
                # Promote to warm tier
                promote_to_warm.delay(image.id)

        # Serve file
        if image.storage_tier == 'hot':
            file_url = image.file.url
        elif image.storage_tier == 'warm':
            file_url = image.file_warm.url
        else:
            # Cold storage - initiate retrieval (takes hours)
            initiate_glacier_retrieval.delay(image.id)
            return Response({
                'status': 'retrieving',
                'message': 'File in cold storage. Retrieval initiated. Check back in 4-6 hours.'
            })

        return Response({'url': file_url})
```

**Deduplication:**

```python
# Detect duplicate DICOM files by SOP Instance UID
@shared_task
def deduplicate_dicom(study_id):
    """
    Remove duplicate DICOM instances in a study
    """
    study = ImagingStudy.objects.get(pk=study_id)
    images = study.images.all()

    # Group by SOP Instance UID
    from collections import defaultdict
    uid_map = defaultdict(list)

    for image in images:
        uid = image.sop_instance_uid
        if uid:
            uid_map[uid].append(image)

    duplicates_removed = 0
    space_saved = 0

    for uid, image_list in uid_map.items():
        if len(image_list) > 1:
            # Keep first, delete rest
            keep = image_list[0]
            duplicates = image_list[1:]

            for dup in duplicates:
                space_saved += dup.file_size
                dup.file.delete()
                dup.delete()
                duplicates_removed += 1

            logger.info(f"Removed {len(duplicates)} duplicates for SOP UID {uid}")

    return {
        'duplicates_removed': duplicates_removed,
        'space_saved_mb': space_saved / (1024 * 1024)
    }
```

**Cost optimization metrics:**

```python
# Management command to analyze storage costs
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count

class Command(BaseCommand):
    def handle(self, *args, **options):
        # S3 pricing (example)
        HOT_COST_PER_GB = 0.023  # USD per GB/month
        WARM_COST_PER_GB = 0.023
        COLD_COST_PER_GB = 0.004  # Glacier

        # Calculate storage by tier
        hot_size = DicomImage.objects.filter(storage_tier='hot').aggregate(
            total=Sum('file_size')
        )['total'] or 0

        warm_size = DicomImage.objects.filter(storage_tier='warm').aggregate(
            total=Sum('file_size')
        )['total'] or 0

        cold_size = DicomImage.objects.filter(storage_tier='cold').aggregate(
            total=Sum('file_size')
        )['total'] or 0

        # Convert to GB
        hot_gb = hot_size / (1024**3)
        warm_gb = warm_size / (1024**3)
        cold_gb = cold_size / (1024**3)

        # Calculate costs
        hot_cost = hot_gb * HOT_COST_PER_GB
        warm_cost = warm_gb * WARM_COST_PER_GB
        cold_cost = cold_gb * COLD_COST_PER_GB

        total_cost = hot_cost + warm_cost + cold_cost

        self.stdout.write(f"Hot Tier: {hot_gb:.2f} GB - ${hot_cost:.2f}/month")
        self.stdout.write(f"Warm Tier: {warm_gb:.2f} GB - ${warm_cost:.2f}/month")
        self.stdout.write(f"Cold Tier: {cold_gb:.2f} GB - ${cold_cost:.2f}/month")
        self.stdout.write(f"Total: {hot_gb + warm_gb + cold_gb:.2f} GB - ${total_cost:.2f}/month")
```

**This demonstrates:**
- Production-ready storage architecture
- Multi-tier storage strategy
- DICOM compression techniques
- Lifecycle management and cost optimization
- Deduplication and space savings

---

### **Q48: What are common DICOM pitfalls and edge cases you need to handle in production?**

**DICOM is complex and inconsistent across vendors** - handling edge cases is critical for robust medical imaging systems.

**Pitfall 1: Missing or invalid tags**

```python
# ❌ WRONG: Assume tags exist
patient_name = ds.PatientName  # AttributeError if tag doesn't exist!

# ✅ CORRECT: Use .get() with defaults
patient_name = ds.get('PatientName', 'Unknown')
patient_name = str(patient_name)  # Convert to string (might be PersonName object)
```

**Pitfall 2: Multiple values in tags**

```python
# Some tags can have multiple values (VM > 1)

# ❌ WRONG
window_center = float(ds.WindowCenter)  # Might be [40, 80, 120]!

# ✅ CORRECT
window_center = ds.get('WindowCenter', 40)
if isinstance(window_center, list):
    window_center = window_center[0]  # Use first value
window_center = float(window_center)
```

**Pitfall 3: Non-square pixels**

```python
# ❌ WRONG: Assume square pixels
pixel_spacing = ds.PixelSpacing  # [row_spacing, col_spacing]
mm_per_pixel = pixel_spacing[0]  # Might be different in x and y!

# ✅ CORRECT: Handle anisotropic pixels
pixel_spacing = ds.get('PixelSpacing', [1, 1])
row_spacing = float(pixel_spacing[0])  # mm per pixel in y direction
col_spacing = float(pixel_spacing[1])  # mm per pixel in x direction

# Calculate area correctly
pixel_area_mm2 = row_spacing * col_spacing
```

**Pitfall 4: Vendor-specific private tags**

```python
# Different vendors store proprietary data in private tags
# Tags (0x0009, 0xxxx) - (0x00FF, 0xxxx) are private

# ✅ Handle gracefully
try:
    # Some vendors store scan protocol in private tags
    protocol = ds[(0x0019, 0x100C)].value
except KeyError:
    protocol = 'Unknown'
```

**Pitfall 5: Character encoding issues**

```python
# DICOM uses SpecificCharacterSet tag for encoding
# Default is ASCII, but international names use other encodings

# ✅ CORRECT: Decode properly
patient_name = ds.get('PatientName', 'Unknown')

# Handle encoding
if hasattr(patient_name, 'encode'):
    # It's already a string
    patient_name_str = str(patient_name)
else:
    # Might be bytes or PersonName object
    patient_name_str = str(patient_name)

# For international characters
specific_charset = ds.get('SpecificCharacterSet', 'ISO_IR 100')
# Handle different encodings (ISO_IR 192 = UTF-8, ISO_IR 100 = Latin-1, etc.)
```

**Pitfall 6: Implicit vs Explicit transfer syntax**

```python
# DICOM files can use different transfer syntaxes (how data is encoded)

import pydicom

# ✅ Force reading with explicit VR
try:
    ds = pydicom.dcmread(file_path, force=True)
except Exception as e:
    logger.error(f"Failed to read DICOM: {e}")
    # Try alternative parsers or report as invalid
```

**Pitfall 7: Multi-frame vs single-frame images**

```python
# Some modalities (ultrasound, cine MRI) have multiple frames in one file

# ❌ WRONG
pixel_array = ds.pixel_array  # Might be 3D array!

# ✅ CORRECT
pixel_array = ds.pixel_array

if len(pixel_array.shape) == 3:
    # Multi-frame: (frames, rows, columns)
    num_frames = pixel_array.shape[0]
    # Extract first frame
    first_frame = pixel_array[0]
elif len(pixel_array.shape) == 2:
    # Single frame: (rows, columns)
    first_frame = pixel_array
else:
    raise ValueError(f"Unexpected pixel array shape: {pixel_array.shape}")
```

**Pitfall 8: Photometric interpretation**

```python
# MONOCHROME1 vs MONOCHROME2 vs RGB

photometric = ds.get('PhotometricInterpretation', 'MONOCHROME2')

if photometric == 'MONOCHROME1':
    # Min value is white, max is black (inverted)
    pixel_array = np.max(pixel_array) - pixel_array
elif photometric == 'MONOCHROME2':
    # Min value is black, max is white (normal)
    pass
elif photometric == 'RGB':
    # Color image (3 channels)
    # pixel_array shape: (rows, columns, 3)
    pass
elif photometric == 'PALETTE COLOR':
    # Indexed color - need to apply color palette
    # More complex handling required
    pass
```

**Pitfall 9: Modality-specific units**

```python
# Different modalities use different pixel value meanings

modality = ds.get('Modality', 'OT')

if modality == 'CT':
    # Pixel values are Hounsfield Units
    hu_array = ds.pixel_array * ds.RescaleSlope + ds.RescaleIntercept

elif modality in ['PT', 'NM']:
    # PET/Nuclear Medicine - SUV (Standardized Uptake Value) calculation
    # Requires decay correction, patient weight, injection time, etc.
    # Much more complex!
    pass

elif modality in ['MR', 'MRI']:
    # MRI has no standardized units - arbitrary signal intensity
    # Normalize to 0-max range
    pixel_array = ds.pixel_array
    normalized = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min())
```

**Pitfall 10: Corrupted/truncated files**

```python
# Real-world: Network issues, disk failures can corrupt DICOM files

def safe_parse_dicom(file_path):
    """
    Safely parse DICOM with comprehensive error handling
    """
    try:
        # Try normal read
        ds = pydicom.dcmread(file_path, force=True)

        # Validate essential tags
        required_tags = ['PatientID', 'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
        missing_tags = [tag for tag in required_tags if tag not in ds]

        if missing_tags:
            raise ValueError(f"Missing required tags: {missing_tags}")

        # Try to access pixel data (might be corrupted)
        try:
            pixel_array = ds.pixel_array
            if pixel_array.size == 0:
                raise ValueError("Empty pixel data")
        except Exception as e:
            logger.warning(f"Pixel data error: {e}")
            # Still parse metadata even if pixel data is corrupted
            pass

        return ds, None

    except pydicom.errors.InvalidDicomError:
        return None, "Not a valid DICOM file"
    except Exception as e:
        return None, f"DICOM parsing error: {str(e)}"
```

**Production checklist:**

✅ Handle missing tags with .get()  
✅ Check for multi-valued tags  
✅ Validate pixel array shape (2D vs 3D)  
✅ Handle different photometric interpretations  
✅ Support different character encodings  
✅ Validate required UIDs exist  
✅ Handle corrupted/truncated files gracefully  
✅ Test with files from multiple vendors  
✅ Implement comprehensive error logging  

**This demonstrates:**
- Real-world DICOM complexity awareness
- Defensive programming practices
- Vendor-specific considerations
- Production-ready error handling

---

## 7. Frontend (Next.js, React, TypeScript, React Query)

### **Q49: Explain the difference between Next.js App Router and Pages Router. Why did you choose App Router for this project?**

**Next.js 13+ introduced App Router** - a fundamental change in how Next.js applications are structured.

**Key Differences:**

| Feature | Pages Router (Old) | App Router (New) |
|---------|-------------------|------------------|
| **File location** | `/pages` | `/app` |
| **Routing** | File-based | Folder-based |
| **Layouts** | `_app.js` + manual | Built-in nested layouts |
| **Data fetching** | `getServerSideProps`, `getStaticProps` | `async` components, `fetch()` |
| **Server Components** | ❌ No | ✅ Yes (default) |
| **Streaming** | ❌ Limited | ✅ Built-in with Suspense |
| **Loading states** | Manual | `loading.tsx` |
| **Error handling** | Manual | `error.tsx` |
| **Metadata** | `next/head` | `metadata` export |

**App Router structure:**

```
app/
├── layout.tsx          # Root layout (wraps all pages)
├── page.tsx            # Home page (/)
├── loading.tsx         # Loading UI
├── error.tsx           # Error UI
├── not-found.tsx       # 404 page
├── (route)/            # Route group (doesn't affect URL)
│   ├── patients/
│   │   ├── page.tsx    # /patients
│   │   ├── [id]/
│   │   │   ├── page.tsx    # /patients/123
│   │   │   └── loading.tsx # Loading for patient detail
│   │   └── layout.tsx  # Layout for all patient pages
│   └── studies/
│       ├── page.tsx    # /studies
│       └── [id]/
│           └── page.tsx    # /studies/456
└── api/
    └── route.ts        # API routes
```

**Server Components vs Client Components:**

```typescript
// app/patients/page.tsx
// Server Component (default in App Router)
export default async function PatientsPage() {
  // This runs on the server!
  // Can directly access database, no need for API route
  const patients = await fetch('http://localhost:8000/api/patients/', {
    cache: 'no-store', // Disable caching for dynamic data
  }).then(res => res.json());

  return (
    <div>
      <h1>Patients</h1>
      {patients.results.map(patient => (
        <PatientCard key={patient.id} patient={patient} />
      ))}
    </div>
  );
}

// Client Component (needs interactivity)
'use client';  // This directive makes it a client component

import { useState } from 'react';

export function PatientSearch() {
  const [search, setSearch] = useState('');

  return (
    <input
      value={search}
      onChange={(e) => setSearch(e.target.value)}
      placeholder="Search patients..."
    />
  );
}
```

**Nested Layouts:**

```typescript
// app/layout.tsx (root layout)
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <QueryClientProvider client={queryClient}>
            {children}
          </QueryClientProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

// app/(route)/layout.tsx (nested layout for authenticated routes)
import { Sidebar, Header } from '@/components';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
```

**Loading and Streaming:**

```typescript
// app/patients/[id]/loading.tsx
export default function Loading() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
      <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
      <div className="h-4 bg-gray-200 rounded w-3/4"></div>
    </div>
  );
}

// Automatic loading UI while page.tsx fetches data!
```

**Metadata (SEO):**

```typescript
// app/patients/[id]/page.tsx
import { Metadata } from 'next';

export async function generateMetadata({ params }: { params: { id: string } }): Promise<Metadata> {
  const patient = await fetch(`http://localhost:8000/api/patients/${params.id}/`).then(res => res.json());

  return {
    title: `${patient.full_name} - Patient Details`,
    description: `Medical records for patient ${patient.medical_record_number}`,
  };
}
```

**Why we chose App Router:**

1. **Server Components**: Reduce client JS bundle size
2. **Better data fetching**: No need for `getServerSideProps` boilerplate
3. **Streaming**: Faster perceived performance
4. **Built-in layouts**: Cleaner code organization
5. **Future-proof**: Pages Router is being phased out

**Migration consideration:**

```typescript
// Pages Router (old way)
export async function getServerSideProps() {
  const res = await fetch('http://localhost:8000/api/patients/');
  const patients = await res.json();

  return {
    props: { patients },
  };
}

export default function Patients({ patients }) {
  return <div>{/* render */}</div>;
}

// App Router (new way)
export default async function Patients() {
  const patients = await fetch('http://localhost:8000/api/patients/', {
    cache: 'no-store',
  }).then(res => res.json());

  return <div>{/* render */}</div>;
}
```

**This demonstrates:**
- Understanding of Next.js architecture evolution
- Server Components vs Client Components
- Modern React patterns
- Performance optimization with streaming

---

### **Q50: How does React Query (TanStack Query) work? Why use it instead of useState + useEffect? (CRITICAL FOR DATA FETCHING)**

**React Query** is a powerful data-fetching and state management library. It's **essential for modern React apps**.

**Problem with useState + useEffect:**

```typescript
// ❌ BAD: Manual data fetching (lots of boilerplate)
function PatientList() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch('/api/patients/')
      .then(res => res.json())
      .then(data => {
        setPatients(data.results);
        setLoading(false);
      })
      .catch(err => {
        setError(err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return <div>{/* render patients */}</div>;
}

// Problems:
// 1. No caching - refetches every render
// 2. No background refetching
// 3. No deduplication - multiple components fetch same data
// 4. No retry logic
// 5. Stale data issues
// 6. Manual loading/error state management
```

**With React Query:**

```typescript
// ✅ GOOD: React Query handles everything
import { useQuery } from '@tanstack/react-query';

function PatientList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['patients'],
    queryFn: () => fetch('/api/patients/').then(res => res.json()),
    staleTime: 5 * 60 * 1000,  // Data fresh for 5 minutes
    cacheTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
    retry: 3,                   // Retry failed requests 3 times
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return <div>{/* render data.results */}</div>;
}
```

**Our implementation:**

```typescript
// lib/hooks/usePatients.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { patientService } from '@/lib/api';

export const usePatients = (params?: PatientQueryParams) => {
  return useQuery({
    queryKey: ['patients', params],  // Unique key for this query
    queryFn: () => patientService.getAll(params),
    staleTime: 5 * 60 * 1000,       // 5 minutes
    cacheTime: 10 * 60 * 1000,      // 10 minutes
  });
};

export const usePatient = (id: number) => {
  return useQuery({
    queryKey: ['patients', id],
    queryFn: () => patientService.getById(id),
    enabled: !!id,  // Only run if ID exists
  });
};

// Mutations (CREATE, UPDATE, DELETE)
export const useCreatePatient = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: patientService.create,
    onSuccess: () => {
      // Invalidate and refetch patients list
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
};

export const useUpdatePatient = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Patient> }) =>
      patientService.update(id, data),
    onSuccess: (data, variables) => {
      // Update cache for specific patient
      queryClient.setQueryData(['patients', variables.id], data);
      // Invalidate list
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
};
```

**Usage in components:**

```typescript
// components/PatientList.tsx
'use client';

import { usePatients, useCreatePatient } from '@/lib/hooks/usePatients';

export function PatientList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');

  const { data, isLoading, isError, error } = usePatients({ page, search });
  const createMutation = useCreatePatient();

  const handleCreate = async (patientData: PatientCreateInput) => {
    try {
      await createMutation.mutateAsync(patientData);
      toast.success('Patient created!');
    } catch (err) {
      toast.error('Failed to create patient');
    }
  };

  if (isLoading) return <LoadingSpinner />;
  if (isError) return <ErrorMessage error={error} />;

  return (
    <div>
      <SearchBar value={search} onChange={setSearch} />

      {data.results.map(patient => (
        <PatientCard key={patient.id} patient={patient} />
      ))}

      <Pagination
        page={page}
        totalPages={Math.ceil(data.count / 20)}
        onPageChange={setPage}
      />
    </div>
  );
}
```

**React Query DevTools:**

```typescript
// app/providers.tsx
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute default
      retry: 1,
    },
  },
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

**Optimistic Updates:**

```typescript
export const useUpdatePatient = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: patientService.update,

    // Optimistic update: Update UI before server responds
    onMutate: async (newPatient) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['patients', newPatient.id] });

      // Snapshot previous value
      const previousPatient = queryClient.getQueryData(['patients', newPatient.id]);

      // Optimistically update
      queryClient.setQueryData(['patients', newPatient.id], newPatient);

      // Return context with snapshot
      return { previousPatient };
    },

    // If mutation fails, rollback
    onError: (err, newPatient, context) => {
      queryClient.setQueryData(
        ['patients', newPatient.id],
        context.previousPatient
      );
    },

    // Always refetch after error or success
    onSettled: (newPatient) => {
      queryClient.invalidateQueries({ queryKey: ['patients', newPatient.id] });
    },
  });
};
```

**Infinite Queries (pagination):**

```typescript
export const useInfinitePatients = () => {
  return useInfiniteQuery({
    queryKey: ['patients', 'infinite'],
    queryFn: ({ pageParam = 1 }) => patientService.getAll({ page: pageParam }),
    getNextPageParam: (lastPage, pages) => {
      return lastPage.next ? pages.length + 1 : undefined;
    },
  });
};

// Usage
const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfinitePatients();

// Render
{data.pages.map((page) =>
  page.results.map((patient) => <PatientCard key={patient.id} patient={patient} />)
)}

{hasNextPage && (
  <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
    {isFetchingNextPage ? 'Loading...' : 'Load More'}
  </button>
)}
```

**Benefits of React Query:**

1. **Automatic caching**: Same data fetched once, cached for all components
2. **Background refetching**: Keeps data fresh automatically
3. **Deduplication**: Multiple components requesting same data = 1 request
4. **Optimistic updates**: Update UI before server responds
5. **Retry logic**: Auto-retry failed requests
6. **Stale-while-revalidate**: Show cached data while fetching fresh data
7. **Garbage collection**: Auto-cleanup unused cache
8. **DevTools**: Inspect cache, queries, mutations
9. **TypeScript support**: Full type safety
10. **Small bundle size**: ~13kb

**This demonstrates:**
- Modern data fetching patterns
- State management with React Query
- Optimistic updates for better UX
- Cache management strategies

---

### **Q51: Explain TypeScript generics and how you use them in React components. (ADVANCED)**

**Generics** make components reusable while maintaining type safety.

**Basic generic component:**

```typescript
// Generic list component
interface ListProps<T> {
  items: T[];
  renderItem: (item: T) => React.ReactNode;
  keyExtractor: (item: T) => string | number;
}

function List<T>({ items, renderItem, keyExtractor }: ListProps<T>) {
  return (
    <ul>
      {items.map((item) => (
        <li key={keyExtractor(item)}>{renderItem(item)}</li>
      ))}
    </ul>
  );
}

// Usage with type inference
<List
  items={patients}  // TypeScript infers T = Patient
  renderItem={(patient) => <PatientCard patient={patient} />}
  keyExtractor={(patient) => patient.id}
/>
```

**Generic hooks:**

```typescript
// lib/hooks/useApi.ts
export function useApi<TData, TError = Error>(
  endpoint: string
): {
  data: TData | undefined;
  error: TError | null;
  loading: boolean;
} {
  const [data, setData] = useState<TData>();
  const [error, setError] = useState<TError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(endpoint)
      .then(res => res.json() as Promise<TData>)
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [endpoint]);

  return { data, error, loading };
}

// Usage
const { data, error, loading } = useApi<Patient[]>('/api/patients/');
// data is typed as Patient[] | undefined
```

**This demonstrates:**
- Advanced TypeScript usage
- Type-safe generic components
- Reusability without losing type information

---

### **Q52: How do you handle authentication in a Next.js app with Django backend?**

**Implementation using session-based auth:**

```typescript
// contexts/AuthContext.tsx
'use client';

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is authenticated
    fetch('/api/auth/me/', { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(setUser)
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch('/api/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) throw new Error('Login failed');

    const user = await res.json();
    setUser(user);
  };

  const logout = async () => {
    await fetch('/api/auth/logout/', {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
```

**Protected routes:**

```typescript
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Check for session cookie
  const session = request.cookies.get('sessionid');

  if (!session && !request.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/patients/:path*', '/studies/:path*', '/dashboard/:path*'],
};
```

---

## 8. Testing, Security, and DevOps

### **Q53: How do you write unit tests for Django views and React components?**

**Django (pytest):**

```python
# tests/test_api.py
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_patient(db):
    def make_patient(**kwargs):
        defaults = {
            'medical_record_number': 'MRN001',
            'first_name': 'John',
            'last_name': 'Doe',
        }
        defaults.update(kwargs)
        return Patient.objects.create(**defaults)
    return make_patient

def test_get_patients(api_client, create_patient):
    # Arrange
    patient = create_patient()

    # Act
    response = api_client.get('/api/patients/')

    # Assert
    assert response.status_code == 200
    assert len(response.json()['results']) == 1
```

**React (Jest + React Testing Library):**

```typescript
// __tests__/PatientList.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PatientList } from '@/components/PatientList';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

test('renders patient list', async () => {
  // Mock API
  global.fetch = jest.fn(() =>
    Promise.resolve({
      json: () => Promise.resolve({
        results: [{ id: 1, full_name: 'John Doe' }],
        count: 1,
      }),
    })
  );

  const queryClient = createTestQueryClient();

  render(
    <QueryClientProvider client={queryClient}>
      <PatientList />
    </QueryClientProvider>
  );

  // Wait for data to load
  await waitFor(() => {
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });
});
```

---

### **Q54: What security measures have you implemented in this medical imaging platform?**

**1. Authentication & Authorization:**
- Session-based auth with django-allauth
- CSRF protection for state-changing operations
- Role-based access control (RBAC)

**2. Data protection:**
- HTTPS only (HSTS headers)
- Encrypted database connections
- DICOM anonymization for PHI

**3. API Security:**
- Rate limiting (DRF throttling)
- Input validation and sanitization
- SQL injection prevention (Django ORM)

**4. HIPAA Compliance:**
- Audit logging (all data access)
- Encryption at rest (database)
- Encryption in transit (TLS 1.3)
- Access controls

**5. Frontend Security:**
- Content Security Policy (CSP)
- XSS prevention (React auto-escaping)
- No sensitive data in localStorage

**Implementation:**

```python
# settings.py
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Custom permission
class IsHospitalStaff(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.hospital == request.user.hospital
```

---

### **Q55: How would you deploy this Django + Next.js application to production?**

**Architecture:**

```
                 ┌──────────────┐
                 │  Cloudflare  │ (CDN + DDoS protection)
                 └──────┬───────┘
                        │
              ┌─────────▼─────────┐
              │  Load Balancer    │
              └─────────┬─────────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
    ┌────▼────┐                   ┌───▼─────┐
    │ Next.js │                   │  Django │
    │ (Vercel)│                   │  (AWS)  │
    └─────────┘                   └────┬────┘
                                       │
                        ┌──────────────┼──────────────┐
                        │              │              │
                   ┌────▼───┐    ┌────▼───┐    ┌────▼───┐
                   │  RDS   │    │ Redis  │    │   S3   │
                   │(MySQL) │    │(Cache) │    │(Files) │
                   └────────┘    └────────┘    └────────┘
```

**Docker Compose (production):**

```yaml
version: '3.8'

services:
  web:
    build: .
    command: gunicorn firstproject.wsgi:application --bind 0.0.0.0:8000 --workers 4
    volumes:
      - static:/app/static
      - media:/app/media
    environment:
      - DEBUG=False
      - DATABASE_URL=postgresql://...
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - static:/app/static
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web

  celery_worker:
    build: .
    command: celery -A firstproject worker --loglevel=info
    depends_on:
      - redis

  celery_beat:
    build: .
    command: celery -A firstproject beat --loglevel=info
    depends_on:
      - redis
```

**CI/CD (GitHub Actions):**

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          pip install -r requirements.txt
          pytest
          npm test

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to AWS
        run: |
          docker build -t app .
          docker push $ECR_REGISTRY/app:latest
          aws ecs update-service --cluster prod --service app --force-new-deployment
```

**Monitoring:**

- Sentry (error tracking)
- New Relic (APM)
- CloudWatch (infrastructure)
- Datadog (unified monitoring)

---

### **Q56-Q85: RAPID-FIRE QUESTIONS**

**Q56:** What is CORS and how did you configure it?  
**A:** Cross-Origin Resource Sharing. Configured with `django-cors-headers` to allow Next.js frontend at `localhost:3000` to access Django API.

**Q57:** Explain database indexes and when to use them.  
**A:** Indexes speed up queries but slow down writes. Use on: foreign keys, frequently filtered fields, ORDER BY columns.

**Q58:** What is the difference between PUT and PATCH?  
**A:** PUT replaces entire resource, PATCH partial update. Use PATCH for efficiency.

**Q59:** How do you handle file uploads in Django?  
**A:** Use `FileField`/`ImageField`, configure `MEDIA_ROOT`, handle with `MultiPartParser` in DRF.

**Q60:** What is lazy loading in React?  
**A:** `React.lazy()` and `Suspense` to split code and load components on demand. Reduces initial bundle size.

**Q61:** Explain database transactions in Django.  
**A:** Use `@transaction.atomic` to ensure all-or-nothing operations. Critical for data consistency.

**Q62:** What are React hooks rules?  
**A:** 1) Only call at top level, 2) Only call from React functions, 3) Same order every render.

**Q63:** How do you prevent SQL injection?  
**A:** Use Django ORM (parameterized queries), never use raw SQL with string interpolation.

**Q64:** What is middleware in Django?  
**A:** Request/response processors. Used for: auth, CORS, logging, custom headers.

**Q65:** Explain useState vs useReducer.  
**A:** useState for simple state, useReducer for complex state with multiple sub-values or transitions.

**Q66:** What is Redis used for?  
**A:** Cache, session store, Celery message broker, rate limiting storage.

**Q67:** How do you optimize React performance?  
**A:** Memoization (`useMemo`, `useCallback`), code splitting, React.memo, virtualization for long lists.

**Q68:** What is N+1 query problem? (Covered in Q40)

**Q69:** Explain Docker containers vs VMs.  
**A:** Containers share OS kernel (lightweight), VMs include full OS (heavy). Containers start faster, use less resources.

**Q70:** What is JWT vs session-based auth?  
**A:** JWT: stateless tokens. Sessions: server-side state. We use sessions for better security (can revoke).

**Q71:** How do you handle environment variables?  
**A:** Use `.env` files, `python-decouple`, never commit secrets to git.

**Q72:** What is CSRF protection?  
**A:** Cross-Site Request Forgery prevention. Django generates CSRF tokens for forms, validates on POST.

**Q73:** Explain database migrations.  
**A:** Version control for database schema. `makemigrations` creates, `migrate` applies. Critical for team collaboration.

**Q74:** What are React Server Components?  
**A:** Components that render on server (Next.js 13+). Zero JS to client, can access DB directly.

**Q75:** How do you handle errors in async code?  
**A:** try/catch for async/await, .catch() for promises, error boundaries in React.

**Q76:** What is CI/CD?  
**A:** Continuous Integration/Deployment. Auto-test and deploy on git push. We use GitHub Actions.

**Q77:** Explain database normalization.  
**A:** Organizing data to reduce redundancy. 1NF (atomic values), 2NF (no partial dependencies), 3NF (no transitive dependencies).

**Q78:** What is optimistic locking?  
**A:** Version field to detect concurrent updates. Prevents lost updates in distributed systems.

**Q79:** How do you test Celery tasks?  
**A:** Use `task.apply()` for synchronous execution in tests, mock external dependencies.

**Q80:** What is WebSocket vs HTTP?  
**A:** WebSocket: bi-directional, persistent connection. HTTP: request/response, stateless. Use WebSocket for real-time.

**Q81:** Explain database connection pooling.  
**A:** Reuse database connections instead of creating new ones. Configured with `CONN_MAX_AGE` in Django.

**Q82:** What is the difference between margin and padding in CSS?  
**A:** Margin: space outside element. Padding: space inside element. Margin collapses, padding doesn't.

**Q83:** How do you handle timezone issues?  
**A:** Store UTC in database (`USE_TZ=True`), convert to user timezone in frontend.

**Q84:** What is database sharding?  
**A:** Horizontal partitioning - split data across multiple databases. For massive scale (millions of patients).

**Q85:** How would you scale this application to handle 1M+ patients?  
**A:**
1. Database: Read replicas, sharding by hospital_id
2. Caching: Redis for hot data (recent studies)
3. CDN: Cloudflare for static assets and DICOM thumbnails
4. Queue workers: Auto-scaling Celery workers (10-100 based on load)
5. Storage: Multi-tier S3 (hot/warm/cold)
6. Load balancing: Multiple Django instances behind ALB
7. Database indexes: On all foreign keys and filter fields
8. Query optimization: Aggressive use of select_related/prefetch_related
9. Monitoring: Real-time alerts for slow queries, high error rates
10. Rate limiting: Protect against abuse

**Expected costs at 1M patients:**
- Database: $500-1000/month (RDS r5.xlarge)
- Storage: $2000/month (100TB across tiers)
- Compute: $1000/month (auto-scaling)
- Total: ~$4000-5000/month

---

## Summary

**Total Questions: 85**

**Breakdown:**
- Django/Database: Q1-Q12 (12)
- SQL Fundamentals: Q13-Q24 (12)
- REST API: Q25-Q36 (12)
- Celery/Async: Q37-Q42 (6)
- DICOM Domain: Q43-Q48 (6)
- Frontend: Q49-Q52 (4)
- Testing/Security/DevOps: Q53-Q85 (33)

This comprehensive Q&A document covers:
✅ Backend development (Django, DRF, Celery)
✅ Database design and SQL
✅ REST API architecture
✅ Async processing and distributed systems
✅ Medical imaging (DICOM, PACS, HIPAA)
✅ Frontend (Next.js, React, TypeScript, React Query)
✅ Testing strategies
✅ Security and compliance
✅ DevOps and deployment
✅ Scaling considerations

**Good luck with your interviews!** 🚀


---

## 9. Additional Topics for EightGen Interviews

### **Q86: What is FastAPI and how does it differ from Django REST Framework?**

**FastAPI** is a modern, high-performance web framework for building APIs with Python 3.7+ based on standard Python type hints.

**Key Differences:**

| Feature | Django REST Framework | FastAPI |
|---------|----------------------|---------|
| **Performance** | Slower (synchronous by default) | Very fast (async/await native) |
| **Type Safety** | Manual serializers | Automatic via Pydantic |
| **Documentation** | Manual (drf-spectacular) | Auto-generated (OpenAPI/Swagger) |
| **Learning Curve** | Steeper (Django knowledge required) | Easier (pure Python) |
| **Async Support** | Limited (added in Django 4.1+) | Native, first-class |
| **Validation** | DRF Serializers | Pydantic models |
| **Ecosystem** | Batteries included (ORM, admin, auth) | Minimal (bring your own) |

**FastAPI Example:**

```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

app = FastAPI(title="Asset Management API")

# Pydantic model for request/response validation
class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    asset_type: str
    manufacturer: Optional[str] = None
    install_date: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Pump A-123",
                "asset_type": "Centrifugal Pump",
                "manufacturer": "Grundfos",
                "install_date": "2024-01-15T00:00:00"
            }
        }

class Asset(AssetCreate):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True  # For ORM compatibility

# Dependency injection
async def get_db():
    # Return database session
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Async endpoint with automatic validation
@app.post("/assets/", response_model=Asset, status_code=201)
async def create_asset(
    asset: AssetCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new asset with automatic validation
    - **name**: Asset name (required)
    - **asset_type**: Type of asset
    - **manufacturer**: Manufacturer name (optional)
    - **install_date**: Installation date
    """
    db_asset = AssetModel(**asset.dict())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset

@app.get("/assets/", response_model=List[Asset])
async def list_assets(
    skip: int = 0,
    limit: int = 100,
    asset_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AssetModel)
    if asset_type:
        query = query.filter(AssetModel.asset_type == asset_type)
    return query.offset(skip).limit(limit).all()

# Exception handling
@app.get("/assets/{asset_id}")
async def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(AssetModel).filter(AssetModel.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

# Automatic interactive docs at /docs (Swagger UI)
# Automatic alternative docs at /redoc (ReDoc)
```

**Why FastAPI for EightGen project:**
- High performance for real-time analytics
- Native async support for concurrent requests
- Automatic API documentation
- Type safety reduces bugs
- Easy integration with Pydantic for data validation

**This demonstrates:**
- Understanding of modern Python web frameworks
- Async/await patterns
- Type-driven development
- API design best practices

---

### **Q87: What is Apache Airflow? How would you design a data pipeline for ingesting SAP data?**

**Apache Airflow** is a platform to programmatically author, schedule, and monitor workflows as Directed Acyclic Graphs (DAGs).

**Core Concepts:**

```python
# dags/sap_data_ingestion.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from datetime import datetime, timedelta

# DAG definition
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'sap_data_ingestion',
    default_args=default_args,
    description='Ingest SAP asset data daily',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['sap', 'data-ingestion'],
)

# Task 1: Extract from SAP OData API
def extract_sap_data(**context):
    """
    Extract asset data from SAP OData API
    """
    import requests
    from requests.auth import HTTPBasicAuth
    
    # SAP OData endpoint
    url = "https://sap-system.company.com/sap/opu/odata/sap/API_EQUIPMENT_SRV/EquipmentSet"
    
    auth = HTTPBasicAuth('username', 'password')
    
    params = {
        '$filter': f"CreatedOn ge datetime'{context['ds']}'",  # Yesterday's date
        '$format': 'json',
        '$top': 10000
    }
    
    response = requests.get(url, auth=auth, params=params)
    response.raise_for_status()
    
    data = response.json()
    
    # Push to XCom for next task
    context['ti'].xcom_push(key='sap_data', value=data['d']['results'])
    
    return len(data['d']['results'])

extract_task = PythonOperator(
    task_id='extract_from_sap',
    python_callable=extract_sap_data,
    dag=dag,
)

# Task 2: Transform data
def transform_sap_data(**context):
    """
    Clean and transform SAP data
    """
    import pandas as pd
    from datetime import datetime
    
    # Pull from XCom
    raw_data = context['ti'].xcom_pull(key='sap_data', task_ids='extract_from_sap')
    
    df = pd.DataFrame(raw_data)
    
    # Transformations
    df['extracted_at'] = datetime.utcnow()
    df['install_date'] = pd.to_datetime(df['InstallDate'])
    df['manufacturer'] = df['Manufacturer'].str.strip().str.upper()
    
    # Data quality checks
    df = df[df['EquipmentNumber'].notna()]  # Remove null IDs
    df = df.drop_duplicates(subset=['EquipmentNumber'])
    
    # Save to staging table
    from sqlalchemy import create_engine
    engine = create_engine('postgresql://user:pass@localhost/db')
    
    df.to_sql(
        'sap_assets_staging',
        engine,
        if_exists='replace',
        index=False,
        method='multi'
    )
    
    return len(df)

transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_sap_data,
    dag=dag,
)

# Task 3: Load to production table
load_task = PostgresOperator(
    task_id='load_to_production',
    postgres_conn_id='postgres_default',
    sql="""
        INSERT INTO assets (
            equipment_number, name, asset_type, manufacturer, 
            install_date, source_system
        )
        SELECT 
            equipment_number, description, category, manufacturer,
            install_date, 'SAP'
        FROM sap_assets_staging
        ON CONFLICT (equipment_number) 
        DO UPDATE SET
            name = EXCLUDED.name,
            manufacturer = EXCLUDED.manufacturer,
            updated_at = NOW();
    """,
    dag=dag,
)

# Task 4: Data quality validation
def validate_data(**context):
    """
    Validate loaded data
    """
    from sqlalchemy import create_engine
    
    engine = create_engine('postgresql://user:pass@localhost/db')
    
    # Check record count
    result = engine.execute("SELECT COUNT(*) FROM assets WHERE source_system = 'SAP'")
    count = result.scalar()
    
    if count < 100:  # Minimum expected
        raise ValueError(f"Data quality check failed: only {count} records loaded")
    
    return count

validate_task = PythonOperator(
    task_id='validate_data',
    python_callable=validate_data,
    dag=dag,
)

# Task 5: Send success notification
def send_notification(**context):
    """
    Send Slack notification on success
    """
    import requests
    
    records_extracted = context['ti'].xcom_pull(task_ids='extract_from_sap')
    records_transformed = context['ti'].xcom_pull(task_ids='transform_data')
    records_validated = context['ti'].xcom_pull(task_ids='validate_data')
    
    message = f"""
    ✅ SAP Data Ingestion Successful
    - Extracted: {records_extracted} records
    - Transformed: {records_transformed} records
    - Loaded: {records_validated} records
    - Date: {context['ds']}
    """
    
    requests.post(
        'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
        json={'text': message}
    )

notify_task = PythonOperator(
    task_id='send_notification',
    python_callable=send_notification,
    dag=dag,
)

# Define task dependencies
extract_task >> transform_task >> load_task >> validate_task >> notify_task
```

**Airflow Architecture:**

```
┌─────────────────────────────────────────────────┐
│              Airflow Architecture                │
├─────────────┬─────────────┬─────────────────────┤
│  Scheduler  │   Workers   │      Metadata DB    │
│             │             │    (PostgreSQL)     │
│  - Monitors │  - Execute  │                     │
│    DAGs     │    tasks    │  - DAG state        │
│  - Triggers │  - Parallel │  - Task history     │
│    tasks    │    execution│  - Logs             │
└─────────────┴─────────────┴─────────────────────┘
         │            │               │
         └────────────┴───────────────┘
                      │
              ┌───────▼────────┐
              │   Web Server   │
              │   (UI/API)     │
              └────────────────┘
```

**Best practices:**
- Idempotent tasks (can run multiple times safely)
- Atomic operations
- Proper error handling and retries
- Task timeouts
- XCom for small data passing only (not large datasets)
- Use external storage (S3, GCS) for large data
- Monitor DAG performance

**This demonstrates:**
- Workflow orchestration understanding
- ETL pipeline design
- Enterprise system integration
- Data quality practices

---

### **Q88: What is ClickHouse? When would you use it over PostgreSQL?**

**ClickHouse** is a column-oriented database management system (DBMS) for online analytical processing (OLAP).

**PostgreSQL vs ClickHouse:**

| Use Case | PostgreSQL | ClickHouse |
|----------|-----------|------------|
| **Type** | Row-oriented OLTP | Column-oriented OLAP |
| **Best For** | Transactional operations | Analytical queries |
| **Write Performance** | Fast individual inserts | Slow individual inserts, fast batch |
| **Read Performance** | Good for small result sets | Excellent for large aggregations |
| **Updates/Deletes** | Efficient | Expensive (rewrite segments) |
| **Joins** | Excellent | Limited (prefer denormalization) |
| **Data Volume** | GBs to TBs | TBs to PBs |
| **Query Speed** | Seconds | Milliseconds |

**When to use ClickHouse:**

1. **Time-series analytics** - IoT sensor data, logs, metrics
2. **Large aggregations** - Dashboard analytics across millions/billions of rows
3. **Real-time analytics** - Sub-second query response on huge datasets
4. **Data warehouse** - Historical analysis, reporting

**Architecture for Asset Management Platform:**

```
┌────────────────────────────────────────────────┐
│         Data Architecture                       │
├───────────────┬────────────────────────────────┤
│  PostgreSQL   │        ClickHouse              │
│   (OLTP)      │         (OLAP)                 │
├───────────────┼────────────────────────────────┤
│ - Assets      │ - Asset performance metrics    │
│ - Users       │ - Maintenance events (history) │
│ - Hospitals   │ - Sensor data (time-series)    │
│ - Studies     │ - Audit logs                   │
│               │ - Analytics aggregations       │
└───────────────┴────────────────────────────────┘
         │                    │
         └────────┬───────────┘
                  │
          ┌───────▼────────┐
          │   Application  │
          │   (FastAPI)    │
          └────────────────┘
```

**ClickHouse example:**

```python
# models/clickhouse_models.py
from clickhouse_driver import Client

client = Client('localhost')

# Create table (MergeTree engine for analytics)
client.execute("""
    CREATE TABLE IF NOT EXISTS asset_metrics (
        timestamp DateTime,
        asset_id UInt32,
        metric_name String,
        metric_value Float64,
        unit String,
        date Date MATERIALIZED toDate(timestamp)
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(date)
    ORDER BY (asset_id, metric_name, timestamp)
    SETTINGS index_granularity = 8192
""")

# Insert batch data (millions of rows)
data = [
    (datetime.now(), 123, 'vibration', 2.5, 'mm/s'),
    (datetime.now(), 123, 'temperature', 75.3, 'C'),
    # ... millions more
]

client.execute(
    'INSERT INTO asset_metrics VALUES',
    data
)

# Fast analytical query
result = client.execute("""
    SELECT 
        asset_id,
        metric_name,
        avg(metric_value) as avg_value,
        max(metric_value) as max_value,
        min(metric_value) as min_value,
        count() as data_points
    FROM asset_metrics
    WHERE 
        timestamp >= now() - INTERVAL 30 DAY
        AND metric_name = 'vibration'
    GROUP BY asset_id, metric_name
    ORDER BY avg_value DESC
    LIMIT 100
""")

# Query runs in milliseconds on billions of rows!
```

**FastAPI integration:**

```python
from fastapi import FastAPI
from clickhouse_driver import Client
from datetime import datetime, timedelta

app = FastAPI()

@app.get("/analytics/asset-performance")
async def get_asset_performance(
    asset_id: int,
    days: int = 30,
    metric: str = "vibration"
):
    """
    Get asset performance metrics from ClickHouse
    """
    client = Client('clickhouse-server')
    
    query = """
        SELECT 
            toStartOfHour(timestamp) as hour,
            avg(metric_value) as avg_value,
            max(metric_value) as max_value
        FROM asset_metrics
        WHERE 
            asset_id = %(asset_id)s
            AND metric_name = %(metric)s
            AND timestamp >= now() - INTERVAL %(days)s DAY
        GROUP BY hour
        ORDER BY hour
    """
    
    result = client.execute(
        query,
        {'asset_id': asset_id, 'metric': metric, 'days': days}
    )
    
    return [
        {
            'hour': row[0].isoformat(),
            'avg_value': row[1],
            'max_value': row[2]
        }
        for row in result
    ]
```

**This demonstrates:**
- Understanding of OLAP vs OLTP
- Column-store database knowledge
- Analytics architecture design
- Performance optimization for large datasets

---

### **Q89: What is Polars? How does it differ from Pandas?**

**Polars** is a blazingly fast DataFrame library written in Rust with Python bindings, designed as a modern alternative to Pandas.

**Polars vs Pandas:**

| Feature | Pandas | Polars |
|---------|--------|--------|
| **Performance** | Slow (single-threaded, Python) | Very fast (multi-threaded, Rust) |
| **Memory** | High memory usage | Optimized memory usage |
| **Lazy Evaluation** | No (eager) | Yes (optional) |
| **API** | Method chaining | Expression-based |
| **Null Handling** | NaN confusion | Proper null type |
| **Speed (1GB CSV)** | ~30 seconds | ~2 seconds |

**Example comparison:**

```python
# PANDAS
import pandas as pd

# Read CSV
df = pd.read_csv('assets.csv')

# Filter and aggregate
result = (
    df[df['asset_type'] == 'Pump']
    .groupby('manufacturer')
    .agg({
        'maintenance_cost': 'sum',
        'downtime_hours': 'mean'
    })
    .sort_values('maintenance_cost', ascending=False)
)

# POLARS (Eager API)
import polars as pl

# Read CSV (faster!)
df = pl.read_csv('assets.csv')

# Filter and aggregate (cleaner syntax)
result = (
    df.filter(pl.col('asset_type') == 'Pump')
    .group_by('manufacturer')
    .agg([
        pl.col('maintenance_cost').sum(),
        pl.col('downtime_hours').mean()
    ])
    .sort('maintenance_cost', descending=True)
)

# POLARS (Lazy API - even faster!)
result = (
    pl.scan_csv('assets.csv')  # Lazy read
    .filter(pl.col('asset_type') == 'Pump')
    .group_by('manufacturer')
    .agg([
        pl.col('maintenance_cost').sum().alias('total_cost'),
        pl.col('downtime_hours').mean().alias('avg_downtime')
    ])
    .sort('total_cost', descending=True)
    .collect()  # Execute query plan
)

# Polars optimizes the entire query plan before execution!
```

**Real-world use case (SAP data processing):**

```python
# tasks/process_sap_data.py
import polars as pl
from datetime import datetime

def process_sap_export(file_path: str):
    """
    Process large SAP export file (100K+ rows)
    Polars is 10-20x faster than Pandas
    """
    
    # Lazy read for better performance
    df = (
        pl.scan_csv(file_path, separator='\t')
        
        # Clean and transform
        .with_columns([
            # Parse dates
            pl.col('Install_Date').str.strptime(pl.Date, '%Y%m%d').alias('install_date'),
            
            # Clean strings
            pl.col('Manufacturer').str.strip().str.to_uppercase().alias('manufacturer'),
            
            # Calculate age
            ((pl.lit(datetime.now().date()) - pl.col('install_date').cast(pl.Date)).dt.days() / 365.25)
            .alias('asset_age_years'),
            
            # Categorize
            pl.when(pl.col('Criticality') == 'A')
                .then(pl.lit('High'))
                .when(pl.col('Criticality') == 'B')
                .then(pl.lit('Medium'))
                .otherwise(pl.lit('Low'))
                .alias('criticality_level')
        ])
        
        # Filter invalid records
        .filter(
            pl.col('Equipment_Number').is_not_null() &
            pl.col('install_date').is_not_null()
        )
        
        # Select relevant columns
        .select([
            'Equipment_Number',
            'Description',
            'manufacturer',
            'install_date',
            'asset_age_years',
            'criticality_level'
        ])
        
        # Remove duplicates
        .unique(subset=['Equipment_Number'], keep='last')
        
        # Execute the query plan
        .collect()
    )
    
    return df

# Aggregation example
def calculate_maintenance_summary(df: pl.DataFrame):
    """
    Calculate maintenance statistics by manufacturer
    """
    summary = (
        df.group_by('manufacturer')
        .agg([
            pl.count().alias('asset_count'),
            pl.col('maintenance_cost').sum().alias('total_cost'),
            pl.col('maintenance_cost').mean().alias('avg_cost'),
            pl.col('downtime_hours').sum().alias('total_downtime'),
            # Percentiles
            pl.col('maintenance_cost').quantile(0.5).alias('median_cost'),
            pl.col('maintenance_cost').quantile(0.95).alias('p95_cost'),
            # Conditional aggregations
            (pl.col('status') == 'Critical').sum().alias('critical_assets'),
        ])
        .sort('total_cost', descending=True)
    )
    
    return summary

# Window functions
def add_rankings(df: pl.DataFrame):
    """
    Add maintenance cost rankings within each manufacturer
    """
    df_ranked = df.with_columns([
        # Rank within manufacturer
        pl.col('maintenance_cost')
          .rank(method='dense')
          .over('manufacturer')
          .alias('cost_rank'),
        
        # Running total
        pl.col('maintenance_cost')
          .cum_sum()
          .over('manufacturer')
          .alias('cumulative_cost'),
        
        # Percentage of total
        (pl.col('maintenance_cost') / pl.col('maintenance_cost').sum().over('manufacturer') * 100)
          .alias('cost_percentage')
    ])
    
    return df_ranked
```

**Why Polars for EightGen:**
- 10-20x faster than Pandas for large datasets
- Better memory efficiency (important for 200+ customer tenants)
- Lazy evaluation optimizes entire query
- Built for modern multi-core CPUs
- Type safety and better null handling

**This demonstrates:**
- Modern data processing tools knowledge
- Performance optimization awareness
- Large-scale data handling experience

---

### **Q90: What is dbt (data build tool)? How would you use it for data transformations?**

**dbt** enables analytics engineers to transform data in their warehouse by writing SELECT statements, which dbt turns into tables and views.

**dbt Philosophy:**
- Transformations happen in the warehouse (not ETL tool)
- SQL-based (accessible to analysts)
- Version controlled
- Testable and documented
- Modular and reusable

**Project structure:**

```
dbt_project/
├── dbt_project.yml           # Project configuration
├── models/                    # SQL transformations
│   ├── staging/              # Raw data cleaning
│   │   ├── stg_sap_assets.sql
│   │   └── stg_maintenance_events.sql
│   ├── intermediate/         # Business logic
│   │   └── int_asset_lifecycle.sql
│   └── marts/                # Final tables for analytics
│       ├── fact_maintenance.sql
│       └── dim_assets.sql
├── tests/                    # Data quality tests
│   └── assert_positive_costs.sql
├── macros/                   # Reusable SQL functions
│   └── cents_to_dollars.sql
└── docs/                     # Documentation
```

**Example transformations:**

```sql
-- models/staging/stg_sap_assets.sql
{{
    config(
        materialized='view',
        schema='staging'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('sap', 'raw_equipment') }}
),

cleaned AS (
    SELECT
        equipment_number AS asset_id,
        UPPER(TRIM(description)) AS asset_name,
        category AS asset_type,
        UPPER(TRIM(manufacturer)) AS manufacturer,
        TRY_CAST(install_date AS DATE) AS install_date,
        functional_location,
        criticality,
        status,
        _fivetran_synced AS loaded_at
    FROM source
    WHERE 
        equipment_number IS NOT NULL
        AND install_date IS NOT NULL
)

SELECT * FROM cleaned

-- models/intermediate/int_asset_lifecycle.sql
{{
    config(
        materialized='incremental',
        unique_key='asset_id',
        on_schema_change='fail'
    )
}}

WITH assets AS (
    SELECT * FROM {{ ref('stg_sap_assets') }}
),

maintenance AS (
    SELECT * FROM {{ ref('stg_maintenance_events') }}
),

asset_metrics AS (
    SELECT
        a.asset_id,
        a.asset_name,
        a.manufacturer,
        a.install_date,
        DATEDIFF(day, a.install_date, CURRENT_DATE()) AS age_days,
        DATEDIFF(day, a.install_date, CURRENT_DATE()) / 365.25 AS age_years,
        
        -- Maintenance metrics
        COUNT(m.event_id) AS total_maintenance_events,
        SUM(m.cost) AS total_maintenance_cost,
        SUM(m.downtime_hours) AS total_downtime_hours,
        MAX(m.event_date) AS last_maintenance_date,
        
        -- Calculate mean time between failures (MTBF)
        CASE 
            WHEN COUNT(m.event_id) > 1 
            THEN age_days / NULLIF(COUNT(m.event_id), 0)
            ELSE NULL 
        END AS mtbf_days,
        
        CURRENT_TIMESTAMP() AS calculated_at
        
    FROM assets a
    LEFT JOIN maintenance m 
        ON a.asset_id = m.asset_id
    
    {% if is_incremental() %}
        -- Only process new/updated records
        WHERE a.loaded_at > (SELECT MAX(calculated_at) FROM {{ this }})
    {% endif %}
    
    GROUP BY 1,2,3,4,5,6
)

SELECT * FROM asset_metrics

-- models/marts/fact_maintenance.sql
{{
    config(
        materialized='table',
        schema='analytics'
    )
}}

SELECT
    m.event_id,
    m.asset_id,
    m.event_date,
    m.event_type,
    m.cost,
    m.downtime_hours,
    
    -- Join asset dimensions
    a.asset_name,
    a.manufacturer,
    a.asset_type,
    a.age_years,
    
    -- Business logic
    CASE 
        WHEN m.event_type = 'Emergency' THEN 'Reactive'
        WHEN m.event_type IN ('Scheduled', 'Preventive') THEN 'Planned'
        ELSE 'Other'
    END AS maintenance_category,
    
    -- Cost per downtime hour
    m.cost / NULLIF(m.downtime_hours, 0) AS cost_per_downtime_hour,
    
    -- Use macro
    {{ cents_to_dollars('m.cost') }} AS cost_dollars
    
FROM {{ ref('stg_maintenance_events') }} m
LEFT JOIN {{ ref('int_asset_lifecycle') }} a 
    ON m.asset_id = a.asset_id
```

**Macros (reusable logic):**

```sql
-- macros/cents_to_dollars.sql
{% macro cents_to_dollars(column_name) %}
    ({{ column_name }} / 100.0)::DECIMAL(10,2)
{% endmacro %}
```

**Tests (data quality):**

```yaml
# models/staging/schema.yml
version: 2

models:
  - name: stg_sap_assets
    description: Cleaned SAP asset data
    columns:
      - name: asset_id
        description: Unique asset identifier
        tests:
          - unique
          - not_null
      
      - name: install_date
        description: Asset installation date
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: ">= '2000-01-01'"
      
      - name: manufacturer
        tests:
          - accepted_values:
              values: ['SIEMENS', 'ABB', 'GRUNDFOS', 'SCHNEIDER']

# Custom test
# tests/assert_positive_costs.sql
SELECT *
FROM {{ ref('fact_maintenance') }}
WHERE cost < 0
```

**Running dbt:**

```bash
# Run all models
dbt run

# Run specific model
dbt run --models stg_sap_assets

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve  # Opens web UI

# Build entire project
dbt build  # Run + test + docs
```

**Integration with Airflow:**

```python
# dags/dbt_transformation.py
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG('dbt_daily_transform', ...) as dag:
    
    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='cd /opt/dbt && dbt run --profiles-dir .',
    )
    
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='cd /opt/dbt && dbt test',
    )
    
    dbt_run >> dbt_test
```

**This demonstrates:**
- Modern data transformation practices
- SQL-based ELT (not ETL)
- Data quality testing
- Documentation and lineage
- Analytics engineering workflow

---

### **Q91: How would you design a multi-tenant SaaS architecture for 200+ enterprise customers?**

**Multi-tenancy** ensures customer data isolation while sharing infrastructure for cost efficiency.

**Architecture approaches:**

**1. Database-per-tenant (highest isolation):**

```
Customer 1 → Database 1
Customer 2 → Database 2
Customer 3 → Database 3
```

**Pros:** Complete isolation, easy backup/restore, regulatory compliance  
**Cons:** Expensive, hard to manage at scale, schema updates complex

**2. Schema-per-tenant (balanced):**

```
Database
├── Schema: customer_1
├── Schema: customer_2
└── Schema: customer_3
```

**Pros:** Good isolation, easier management  
**Cons:** Still complex at scale

**3. Row-level multi-tenancy (recommended for 200+ customers):**

```sql
-- Single database with tenant_id column
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,  -- Customer identifier
    asset_name VARCHAR(255),
    -- ... other columns
    
    -- Ensure tenant_id is in all indexes
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

-- Composite indexes for performance
CREATE INDEX idx_assets_tenant_id ON assets(tenant_id, id);
CREATE INDEX idx_assets_tenant_status ON assets(tenant_id, status);
```

**Implementation:**

```python
# models.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Tenant(Base):
    """
    Represents a customer organization
    """
    __tablename__ = 'tenants'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(100), unique=True)  # customer1.app.com
    tier = Column(String(50))  # 'free', 'pro', 'enterprise'
    max_assets = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

class Asset(Base):
    """
    Asset belongs to a tenant
    """
    __tablename__ = 'assets'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False, index=True)
    asset_name = Column(String(255))
    
    # Relationship
    tenant = relationship('Tenant', backref='assets')
    
    # Ensure all queries filter by tenant
    __table_args__ = (
        Index('idx_tenant_asset', 'tenant_id', 'id'),
    )

# FastAPI dependency for tenant context
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

async def get_current_tenant(
    x_tenant_id: int = Header(...),  # From request header
    db: Session = Depends(get_db)
) -> Tenant:
    """
    Extract tenant from request and validate
    """
    tenant = db.query(Tenant).filter(
        Tenant.id == x_tenant_id,
        Tenant.is_active == True
    ).first()
    
    if not tenant:
        raise HTTPException(status_code=403, detail="Invalid or inactive tenant")
    
    return tenant

# Use in endpoints
@app.get("/assets/")
async def list_assets(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    List assets - automatically scoped to tenant
    """
    assets = db.query(Asset).filter(
        Asset.tenant_id == tenant.id  # ALWAYS filter by tenant!
    ).all()
    
    return assets

@app.post("/assets/")
async def create_asset(
    asset_data: AssetCreate,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Create asset - automatically assigned to tenant
    """
    # Check quota
    current_count = db.query(Asset).filter(Asset.tenant_id == tenant.id).count()
    if current_count >= tenant.max_assets:
        raise HTTPException(status_code=429, detail="Asset limit reached")
    
    asset = Asset(
        **asset_data.dict(),
        tenant_id=tenant.id  # ALWAYS set tenant_id!
    )
    
    db.add(asset)
    db.commit()
    
    return asset
```

**Security best practices:**

```python
# middleware.py
class TenantIsolationMiddleware:
    """
    Enforce tenant isolation at middleware level
    """
    async def __call__(self, request: Request, call_next):
        tenant_id = request.headers.get('X-Tenant-ID')
        
        if not tenant_id and request.url.path.startswith('/api/'):
            return JSONResponse(
                status_code=403,
                content={"detail": "Missing X-Tenant-ID header"}
            )
        
        # Set in request state
        request.state.tenant_id = int(tenant_id) if tenant_id else None
        
        response = await call_next(request)
        return response

# Row-Level Security (PostgreSQL)
"""
CREATE POLICY tenant_isolation ON assets
    USING (tenant_id = current_setting('app.current_tenant_id')::int);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
"""

# Set tenant context for connection
def set_tenant_context(db: Session, tenant_id: int):
    db.execute(f"SET app.current_tenant_id = {tenant_id}")
```

**Monitoring per tenant:**

```python
# Track usage per tenant
class TenantMetrics(Base):
    __tablename__ = 'tenant_metrics'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'))
    date = Column(Date, nullable=False)
    
    # Metrics
    api_requests = Column(Integer, default=0)
    storage_mb = Column(Float, default=0)
    active_users = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_tenant_metrics_date', 'tenant_id', 'date'),
    )

# Background task to calculate metrics
@app.post("/internal/calculate-tenant-metrics")
async def calculate_metrics(date: datetime.date, db: Session = Depends(get_db)):
    """
    Calculate daily metrics for all tenants
    """
    tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
    
    for tenant in tenants:
        storage = db.query(func.sum(Asset.file_size)).filter(
            Asset.tenant_id == tenant.id
        ).scalar() or 0
        
        TenantMetrics.objects.create(
            tenant_id=tenant.id,
            date=date,
            storage_mb=storage / (1024 * 1024)
        )
```

**Data isolation testing:**

```python
# tests/test_tenant_isolation.py
def test_tenant_cannot_access_other_tenant_data(client, db):
    """
    Ensure tenant 1 cannot access tenant 2's data
    """
    # Create tenant 1 asset
    asset1 = Asset(tenant_id=1, asset_name="Tenant 1 Asset")
    db.add(asset1)
    db.commit()
    
    # Try to access as tenant 2
    response = client.get(
        f"/assets/{asset1.id}",
        headers={"X-Tenant-ID": "2"}
    )
    
    assert response.status_code == 404  # Should not find
```

**This demonstrates:**
- Multi-tenant architecture design
- Data isolation strategies
- Security and compliance
- Scalability for enterprise SaaS
- Cost optimization

---

I'll continue adding more questions to reach 30. Let me add questions on GCP, SAP integration, Great Expectations, and more production topics:

### **Q92: What is Google Cloud Run and how would you deploy a FastAPI application to it?**

**Cloud Run** is Google's serverless container platform - deploy containers that auto-scale from 0 to many instances.

**Why Cloud Run:**
- Pay-per-use (no idle costs)
- Auto-scaling (0 to 1000+ instances)
- Fully managed (no server management)
- Fast deployments
- Built-in HTTPS

**Deployment:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run expects PORT environment variable
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
```

```bash
# Deploy to Cloud Run
gcloud run deploy asset-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="DATABASE_URL=postgresql://..." \
  --min-instances=1 \
  --max-instances=100 \
  --memory=2Gi \
  --cpu=2
```

---

### **Q93: How do you integrate with SAP using OData APIs?**

**OData** (Open Data Protocol) is RESTful API protocol used by SAP.

**Example with PyOData:**

```python
import requests
from requests.auth import HTTPBasicAuth

# SAP OData endpoint
SERVICE_URL = "https://sap.company.com/sap/opu/odata/sap/API_EQUIPMENT_SRV/"

# Fetch equipment list
response = requests.get(
    f"{SERVICE_URL}/EquipmentSet",
    auth=HTTPBasicAuth('username', 'password'),
    params={
        '$filter': "Category eq 'PUMP'",
        '$select': 'EquipmentNumber,Description,Manufacturer',
        '$top': 100,
        '$format': 'json'
    }
)

data = response.json()
equipment_list = data['d']['results']
```

---

### **Q94: What is Great Expectations and how do you use it for data quality?**

**Great Expectations** validates, documents, and profiles data.

```python
import great_expectations as gx

context = gx.get_context()

# Create expectation suite
suite = context.add_expectation_suite("asset_data_quality")

# Add expectations
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="asset_id")
)

suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeUnique(column="asset_id")
)

suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeBetween(
        column="maintenance_cost",
        min_value=0,
        max_value=1000000
    )
)

# Validate dataframe
results = context.run_validation(df, expectation_suite_name="asset_data_quality")

if not results.success:
    raise ValueError(f"Data quality check failed: {results}")
```

---

### **Q95-Q115: RAPID-FIRE Questions (Additional EightGen Topics)**

**Q95:** What is the difference between Cloud SQL and BigQuery?  
**A:** Cloud SQL is transactional (OLTP), PostgreSQL/MySQL. BigQuery is analytical (OLAP), columnar, serverless data warehouse.

**Q96:** How do you handle secrets in GCP?  
**A:** Use Secret Manager, never hardcode. Access via API or mount as volume in Cloud Run.

**Q97:** What is Cloud Storage (GCS)?  
**A:** Object storage for files. Similar to S3. Use for DICOM files, exports, backups.

**Q98:** Explain Airflow's XCom.  
**A:** Cross-communication between tasks. Limited to small data (<48KB). Use GCS for large data.

**Q99:** What is DAG in Airflow?  
**A:** Directed Acyclic Graph - workflow definition. Tasks with dependencies, no cycles.

**Q100:** How do you monitor Airflow DAGs?  
**A:** Airflow UI, Cloud Monitoring, Slack alerts on failures, SLA monitoring.

**Q101:** What is data lineage?  
**A:** Track data flow from source to destination. dbt docs show lineage automatically.

**Q102:** Explain idempotency in data pipelines.  
**A:** Running same pipeline multiple times produces same result. Use upserts, not inserts.

**Q103:** What is Pydantic?  
**A:** Data validation library. FastAPI uses it for request/response validation.

**Q104:** How do you handle pagination in FastAPI?  
**A:** Query parameters `skip` and `limit`. Return total count for frontend.

**Q105:** What is CORS and why needed?  
**A:** Cross-Origin Resource Sharing. Allows React (localhost:3000) to call API (localhost:8000).

**Q106:** Explain async/await in Python.  
**A:** Asynchronous programming. `async def` defines coroutine. `await` yields control during I/O.

**Q107:** What is SQLAlchemy Core vs ORM?  
**A:** Core: SQL expression language. ORM: Object-relational mapping (like Django ORM).

**Q108:** How do you handle database migrations in production?  
**A:** Use Alembic (SQLAlchemy) or Django migrations. Test in staging first. Zero-downtime strategies.

**Q109:** What is connection pooling?  
**A:** Reuse database connections. Configure with SQLAlchemy `pool_size` and `max_overflow`.

**Q110:** Explain materialized views.  
**A:** Pre-computed query results stored as table. Faster reads, slower writes. Refresh periodically.

**Q111:** What is partitioning in ClickHouse?  
**A:** Split table by date/month for better query performance. Prune old partitions easily.

**Q112:** How do you monitor API performance?  
**A:** Cloud Trace, APM tools (New Relic, Datadog), logging response times, error rates.

**Q113:** What is bearer token authentication?  
**A:** `Authorization: Bearer <token>` header. Stateless auth. Used with JWT or API keys.

**Q114:** Explain database sharding vs partitioning.  
**A:** Partitioning: Split table within database. Sharding: Split across multiple databases.

**Q115:** How would you design a data retention policy for HIPAA compliance?  
**A:**  
- Retain medical records for 7+ years
- Automated lifecycle: hot (1 year) → warm (3 years) → cold (7 years) → delete
- Audit logs: permanent retention
- Implement soft deletes for recovery
- Encrypt at rest and in transit
- Regular compliance audits

---

## Summary (Updated)

**Total Questions: 115**

**Breakdown:**
- Django/Database: Q1-Q12 (12)
- SQL Fundamentals: Q13-Q24 (12)
- REST API: Q25-Q36 (12)
- Celery/Async: Q37-Q42 (6)
- DICOM Domain: Q43-Q48 (6)
- Frontend: Q49-Q52 (4)
- Testing/Security/DevOps: Q53-Q85 (33)
- **EightGen Additional Topics: Q86-Q115 (30)**
  - FastAPI (Q86)
  - Apache Airflow (Q87)
  - ClickHouse (Q88)
  - Polars (Q89)
  - dbt (Q90)
  - Multi-tenancy (Q91)
  - Google Cloud Platform (Q92, Q95-Q97, Q112)
  - SAP Integration (Q93)
  - Data Quality (Q94)
  - Python async/await (Q106)
  - SQLAlchemy (Q107-Q109)
  - Production best practices (Q100-Q115)

**Coverage for EightGen Roles:**

✅ **Full-Stack Developer:**
- React, TypeScript, Next.js (Q49-Q52)
- FastAPI, Python (Q86, Q103-Q106)
- PostgreSQL, ClickHouse (Q88, Q95)
- GCP Cloud Run (Q92)
- Multi-tenant architecture (Q91)
- Data visualization and dashboards

✅ **Backend Engineer:**
- FastAPI, Pydantic (Q86, Q103)
- Airflow, data pipelines (Q87, Q98-Q102)
- Polars, dbt (Q89-Q90)
- ClickHouse, BigQuery (Q88, Q95)
- SAP/enterprise integrations (Q93)
- Great Expectations (Q94)
- GCP (Q92, Q95-Q97)
- Production monitoring (Q100, Q112)

**You are now fully prepared for:**
1. MedTech Company - Full Stack Engineer (Django + React expertise)
2. EightGen - Full Stack Developer (FastAPI + React + GCP)
3. EightGen - Backend Engineer (Data pipelines + Airflow + Polars + dbt)

**Good luck with all three interviews!** 🚀🎯

