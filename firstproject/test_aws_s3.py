#!/usr/bin/env python
"""
Test AWS S3 Connection and Credentials
"""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from decouple import config

# Load credentials from .env
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
REGION = config('AWS_S3_REGION_NAME')

print("=" * 60)
print("AWS S3 Connection Test")
print("=" * 60)
print(f"\nBucket Name: {BUCKET_NAME}")
print(f"Region: {REGION}")
print(f"Access Key ID: {AWS_ACCESS_KEY_ID[:10]}... (hidden)")
print(f"Secret Key: {'*' * 20} (hidden)")
print()

try:
    # Create S3 client
    print("1. Creating S3 client...")
    s3 = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=REGION
    )
    print("   ✅ S3 client created successfully")

    # Test 1: List all buckets
    print("\n2. Testing credentials - listing buckets...")
    response = s3.list_buckets()
    print(f"   ✅ Found {len(response['Buckets'])} bucket(s):")
    for bucket in response['Buckets']:
        marker = "👉" if bucket['Name'] == BUCKET_NAME else "  "
        print(f"   {marker} {bucket['Name']}")

    # Test 2: Check if target bucket exists
    print(f"\n3. Checking if bucket '{BUCKET_NAME}' exists...")
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"   ✅ Bucket '{BUCKET_NAME}' exists and is accessible")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"   ❌ Bucket '{BUCKET_NAME}' does not exist")
        elif error_code == '403':
            print(f"   ❌ Access denied to bucket '{BUCKET_NAME}'")
        else:
            print(f"   ❌ Error: {e}")
        raise

    # Test 3: List objects in bucket
    print(f"\n4. Listing objects in bucket '{BUCKET_NAME}'...")
    try:
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, MaxKeys=10)
        if 'Contents' in response:
            print(f"   ✅ Found {len(response['Contents'])} object(s):")
            for obj in response['Contents']:
                size_kb = obj['Size'] / 1024
                print(f"      - {obj['Key']} ({size_kb:.2f} KB)")
        else:
            print("   ℹ️  Bucket is empty (no objects)")
    except ClientError as e:
        print(f"   ❌ Error listing objects: {e}")
        raise

    # Test 4: Upload a test file
    print(f"\n5. Uploading test file to S3...")
    test_key = 'test/connection_test.txt'
    test_content = f'AWS S3 connection test successful!\nTimestamp: {REGION}\nBucket: {BUCKET_NAME}'

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=test_key,
            Body=test_content.encode('utf-8'),
            ContentType='text/plain'
        )
        print(f"   ✅ Test file uploaded successfully!")
        print(f"   📄 File location: s3://{BUCKET_NAME}/{test_key}")
        print(f"   🌐 URL: https://{BUCKET_NAME}.s3.amazonaws.com/{test_key}")
    except ClientError as e:
        print(f"   ❌ Upload failed: {e}")
        raise

    # Test 5: Verify upload
    print(f"\n6. Verifying uploaded file...")
    try:
        response = s3.get_object(Bucket=BUCKET_NAME, Key=test_key)
        content = response['Body'].read().decode('utf-8')
        print(f"   ✅ File retrieved successfully!")
        print(f"   📝 Content: {content[:50]}...")
    except ClientError as e:
        print(f"   ❌ Retrieval failed: {e}")
        raise

    # Test 6: Clean up test file
    print(f"\n7. Cleaning up test file...")
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=test_key)
        print(f"   ✅ Test file deleted")
    except ClientError as e:
        print(f"   ⚠️  Cleanup failed (file may remain): {e}")

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\nYour AWS credentials are working correctly.")
    print("Django should be able to upload files to S3.")
    print()

except NoCredentialsError:
    print("\n❌ ERROR: No AWS credentials found")
    print("   Make sure .env file exists with AWS credentials")

except ClientError as e:
    print(f"\n❌ AWS Error: {e}")
    error_code = e.response['Error']['Code']

    if error_code == 'InvalidAccessKeyId':
        print("\n💡 The Access Key ID is invalid")
        print("   - Check if AWS_ACCESS_KEY_ID in .env is correct")

    elif error_code == 'SignatureDoesNotMatch':
        print("\n💡 The Secret Access Key is invalid")
        print("   - Check if AWS_SECRET_ACCESS_KEY in .env is correct")

    elif error_code == 'AccessDenied':
        print("\n💡 Access denied - check IAM permissions")
        print("   - User needs S3 permissions (read, write, list)")

    else:
        print(f"\n💡 Error code: {error_code}")

except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print()
