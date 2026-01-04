"""
Test script for AI chat functionality.
Run this after adding your OpenAI API key to .env
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from medical_imaging.ai_tools import (
    get_patients,
    get_hospitals,
    get_studies,
    get_statistics,
    GetPatientsToolInput,
    GetHospitalsToolInput,
    GetStudiesToolInput,
    GetStatisticsToolInput,
)


def test_tools():
    """Test each tool function"""
    print("=" * 60)
    print("Testing AI Chat Tools")
    print("=" * 60)

    # Test get_statistics
    print("\n1. Testing get_statistics (all)...")
    result = get_statistics(GetStatisticsToolInput(entity="all"))
    print(f"Result: {result}")

    # Test get_patients
    print("\n2. Testing get_patients (no filters)...")
    result = get_patients(GetPatientsToolInput(limit=5))
    print(f"Result: {result}")

    # Test get_patients with gender filter
    print("\n3. Testing get_patients (female only)...")
    result = get_patients(GetPatientsToolInput(gender="F", limit=5))
    print(f"Result: {result}")

    # Test get_hospitals
    print("\n4. Testing get_hospitals...")
    result = get_hospitals(GetHospitalsToolInput(limit=5))
    print(f"Result: {result}")

    # Test get_studies
    print("\n5. Testing get_studies...")
    result = get_studies(GetStudiesToolInput(limit=5))
    print(f"Result: {result}")

    # Test get_studies with filters
    print("\n6. Testing get_studies (CT scans only)...")
    result = get_studies(GetStudiesToolInput(modality="CT", limit=5))
    print(f"Result: {result}")

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_tools()
