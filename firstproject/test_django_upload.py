#!/usr/bin/env python
"""
Test Django file upload to S3
Run from project root: python test_django_upload.py
"""
import os
import sys
import django
from io import BytesIO
from PIL import Image

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from medical_imaging.models import ImagingStudy, DicomImage

print("=" * 60)
print("Django S3 Upload Test")
print("=" * 60)

# Check Django settings
from django.conf import settings
print(f"\n✓ USE_S3: {settings.USE_S3}")
storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', 'Not configured')
print(f"✓ Storage Backend: {storage_backend}")
print(f"✓ Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
print(f"✓ Region: {settings.AWS_S3_REGION_NAME}")

# Get or create a study
print("\n1. Getting imaging study...")
study = ImagingStudy.objects.first()
if not study:
    print("   ❌ No imaging studies found!")
    print("   Please create a study in admin first.")
    sys.exit(1)
print(f"   ✓ Using study: {study}")

# Create a test image in memory
print("\n2. Creating test image...")
img = Image.new('RGB', (100, 100), color='red')
img_io = BytesIO()
img.save(img_io, format='PNG')
img_io.seek(0)

# Create uploaded file
uploaded_file = SimpleUploadedFile(
    "test_django_upload.png",
    img_io.read(),
    content_type="image/png"
)
print(f"   ✓ Test image created: {len(uploaded_file.read())} bytes")
uploaded_file.seek(0)  # Reset file pointer

# Upload via Django ORM
print("\n3. Uploading to S3 via Django...")
try:
    dicom_image = DicomImage.objects.create(
        study=study,
        instance_number=999,  # Test instance number
        image_file=uploaded_file,
        slice_thickness=2.5
    )
    print(f"   ✓ DicomImage created with ID: {dicom_image.id}")
    print(f"   ✓ File field value: {dicom_image.image_file.name}")
    print(f"   ✓ File URL: {dicom_image.image_file.url}")
    print(f"   ✓ File size: {dicom_image.file_size_bytes} bytes")

    # Verify the file exists in storage
    print("\n4. Verifying file in storage...")
    if dicom_image.image_file.storage.exists(dicom_image.image_file.name):
        print(f"   ✓ File exists in storage!")

        # Try to get file size from storage
        size = dicom_image.image_file.storage.size(dicom_image.image_file.name)
        print(f"   ✓ Storage confirms size: {size} bytes")
    else:
        print(f"   ❌ File NOT found in storage!")

    print("\n" + "=" * 60)
    print("🎉 SUCCESS!")
    print("=" * 60)
    print(f"\nImage uploaded to S3!")
    print(f"URL: {dicom_image.image_file.url}")
    print(f"\nCheck S3 bucket at:")
    print(f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{dicom_image.image_file.name}")
    print()

    # Clean up test record (optional)
    response = input("Delete test record? (y/n): ")
    if response.lower() == 'y':
        dicom_image.delete()
        print("✓ Test record deleted")

except Exception as e:
    print(f"\n❌ ERROR during upload:")
    print(f"   {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
