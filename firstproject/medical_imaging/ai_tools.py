"""
AI Tools for querying the medical imaging database.
These functions are callable by the OpenAI model through function calling.
"""
from typing import Literal
from pydantic import BaseModel, Field
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Patient, Hospital, ImagingStudy, Diagnosis


class GetPatientsToolInput(BaseModel):
    """Get a list of patients with optional filters"""
    # Gender filter - optional (can be None)
    gender: Literal["M", "F", "O"] | None = Field(
        None,
        description="Filter by gender. M=Male, F=Female, O=Other"
    )
    # Hospital filter - optional (can be None)
    hospital_id: int | None = Field(
        None,
        description="Filter by hospital ID"
    )
    # Maximum number of results to return
    # ge=1 means "greater than or equal to 1" (minimum value)
    # le=100 means "less than or equal to 100" (maximum value)
    limit: int = Field(
        10,  # Default value is 10
        description="Maximum number of results to return",
        ge=1,   # Must be at least 1
        le=100  # Cannot exceed 100
    )


class GetHospitalsToolInput(BaseModel):
    """Get a list of hospitals with optional filters"""
    # Search filter for hospital names - optional (can be None)
    name_contains: str | None = Field(
        None,
        description="Filter hospitals whose name contains this text (case-insensitive)"
    )
    # Maximum number of results to return
    # ge=1: minimum value is 1
    # le=100: maximum value is 100
    limit: int = Field(
        10,  # Default: return 10 results
        description="Maximum number of results to return",
        ge=1,   # At least 1
        le=100  # At most 100
    )


class GetStudiesToolInput(BaseModel):
    """Get a list of imaging studies with optional filters"""
    # Filter by specific patient - optional
    patient_id: int | None = Field(
        None,
        description="Filter by patient ID"
    )
    # Filter by imaging type - optional (CT scan, MRI, X-ray, or Ultrasound)
    modality: Literal["CT", "MRI", "XRAY", "ULTRASOUND"] | None = Field(
        None,
        description="Filter by imaging modality type"
    )
    # Filter by current status - optional
    status: Literal["pending", "in_progress", "completed", "archived"] | None = Field(
        None,
        description="Filter by study status"
    )
    # Time-based filter: get studies from last N days - optional
    # ge=1: minimum 1 day ago
    # le=365: maximum 365 days ago (1 year)
    days_ago: int | None = Field(
        None,
        description="Filter studies from the last N days",
        ge=1,    # At least 1 day
        le=365   # At most 365 days (1 year)
    )
    # Maximum number of results to return
    # ge=1: minimum 1 result
    # le=100: maximum 100 results
    limit: int = Field(
        10,  # Default: return 10 results
        description="Maximum number of results to return",
        ge=1,   # At least 1
        le=100  # At most 100
    )


class GetStatisticsToolInput(BaseModel):
    """Get database statistics"""
    entity: Literal["patients", "hospitals", "studies", "all"] = Field(
        "all",
        description="Which entity to get statistics for"
    )


def get_patients(input_data: GetPatientsToolInput) -> dict:
    """
    Retrieve patients from the database with optional filters.

    Args:
        input_data: Validated input containing optional gender, hospital_id, and limit

    Returns:
        dict: Contains 'total_count', 'returned_count', 'limit', and 'patients' list
    """
    try:
        # Start with base queryset, pre-load hospital data to avoid N+1 queries
        # select_related() performs a SQL JOIN to fetch related hospital in one query
        queryset = Patient.objects.select_related('hospital')

        # Apply gender filter if provided
        if input_data.gender:
            queryset = queryset.filter(gender=input_data.gender)

        # Apply hospital filter if provided
        if input_data.hospital_id:
            queryset = queryset.filter(hospital_id=input_data.hospital_id)

        # Get total count BEFORE applying limit
        # This tells us how many patients match the filters
        total_count = queryset.count()

        # Apply limit to restrict number of returned results
        # [:limit] is Django's way of doing SQL LIMIT
        patients = queryset[:input_data.limit]

        # Convert Django model instances to plain dictionaries
        # This makes the data JSON-serializable for the API response
        patient_list = [
            {
                "id": p.id,
                "mrn": p.medical_record_number,  # Medical Record Number
                "full_name": p.full_name,
                "gender": p.get_gender_display(),  # Converts 'M' to 'Male', etc.
                "date_of_birth": p.date_of_birth.isoformat(),  # Convert date to ISO string
                "hospital": p.hospital.name,  # Access related hospital name
                "email": p.email or None,  # None if empty string
                "phone": p.phone or None,
            }
            for p in patients
        ]

        # Return structured response with metadata
        return {
            "total_count": total_count,  # Total matching patients (before limit)
            "returned_count": len(patient_list),  # Actually returned (after limit)
            "limit": input_data.limit,  # What limit was used
            "patients": patient_list
        }

    except Exception as e:
        # Return error in consistent format
        return {"error": f"Error querying patients: {str(e)}"}


def get_hospitals(input_data: GetHospitalsToolInput) -> dict:
    """
    Retrieve hospitals from the database with optional filters.

    Returns:
        dict: Contains 'count' and 'hospitals' list
    """
    try:
        queryset = Hospital.objects.annotate(
            patient_count=Count('patients')
        )

        if input_data.name_contains:
            queryset = queryset.filter(
                name__icontains=input_data.name_contains
            )

        # Get count before limit
        total_count = queryset.count()

        # Apply limit
        hospitals = queryset[:input_data.limit]

        # Serialize data
        hospital_list = [
            {
                "id": h.id,
                "name": h.name,
                "address": h.address,
                "contact_email": h.contact_email,
                "contact_phone": h.contact_phone,
                "patient_count": h.patient_count,
            }
            for h in hospitals
        ]

        return {
            "total_count": total_count,
            "returned_count": len(hospital_list),
            "limit": input_data.limit,
            "hospitals": hospital_list
        }

    except Exception as e:
        return {"error": f"Error querying hospitals: {str(e)}"}


def get_studies(input_data: GetStudiesToolInput) -> dict:
    """
    Retrieve imaging studies from the database with optional filters.

    Args:
        input_data: Validated input with filters for patient, modality, status, date, and limit

    Returns:
        dict: Contains 'total_count', 'returned_count', 'limit', and 'studies' list
    """
    try:
        # Start with base queryset
        # select_related() pre-loads patient and hospital data (JOIN operation)
        # annotate() adds a computed field counting related images
        queryset = ImagingStudy.objects.select_related(
            'patient',  # Load patient data
            'patient__hospital'  # Load hospital data through patient (double underscore for nested relation)
        ).annotate(
            image_count=Count('images')  # Count number of related images
        )

        # Apply patient filter if provided
        if input_data.patient_id:
            queryset = queryset.filter(patient_id=input_data.patient_id)

        # Apply modality filter if provided (CT, MRI, XRAY, ULTRASOUND)
        if input_data.modality:
            queryset = queryset.filter(modality=input_data.modality)

        # Apply status filter if provided (pending, in_progress, completed, archived)
        if input_data.status:
            queryset = queryset.filter(status=input_data.status)

        # Apply date range filter if provided
        if input_data.days_ago:
            # Calculate the cutoff date (e.g., if days_ago=7, get studies from last week)
            cutoff_date = timezone.now() - timedelta(days=input_data.days_ago)
            # Filter for studies on or after the cutoff date (gte = greater than or equal)
            queryset = queryset.filter(study_date__gte=cutoff_date)

        # Get total count BEFORE applying limit
        total_count = queryset.count()

        # Apply limit to restrict number of results
        studies = queryset[:input_data.limit]

        # Convert to JSON-serializable format
        study_list = [
            {
                "id": s.id,
                "patient_name": s.patient.full_name,
                "patient_mrn": s.patient.medical_record_number,
                "hospital": s.patient.hospital.name,  # Traverse through patient to hospital
                "study_date": s.study_date.isoformat(),  # Convert to ISO date string
                "modality": s.get_modality_display(),  # 'CT' -> 'CT Scan', etc.
                "body_part": s.body_part,
                "status": s.get_status_display(),  # 'pending' -> 'Pending', etc.
                "image_count": s.image_count,  # From annotate() above
                "clinical_notes": s.clinical_notes[:200] if s.clinical_notes else None,  # Truncate to 200 chars
            }
            for s in studies
        ]

        return {
            "total_count": total_count,
            "returned_count": len(study_list),
            "limit": input_data.limit,
            "studies": study_list
        }

    except Exception as e:
        return {"error": f"Error querying studies: {str(e)}"}


def get_statistics(input_data: GetStatisticsToolInput) -> dict:
    """
    Get aggregate statistics from the database.

    Returns:
        dict: Various statistics based on the entity parameter
    """
    try:
        stats = {}

        if input_data.entity in ["patients", "all"]:
            patient_stats = {
                "total": Patient.objects.count(),
                "by_gender": {
                    "male": Patient.objects.filter(gender='M').count(),
                    "female": Patient.objects.filter(gender='F').count(),
                    "other": Patient.objects.filter(gender='O').count(),
                }
            }
            stats["patients"] = patient_stats

        if input_data.entity in ["hospitals", "all"]:
            hospital_stats = {
                "total": Hospital.objects.count(),
                "with_patients": Hospital.objects.annotate(
                    pc=Count('patients')
                ).filter(pc__gt=0).count()
            }
            stats["hospitals"] = hospital_stats

        if input_data.entity in ["studies", "all"]:
            study_stats = {
                "total": ImagingStudy.objects.count(),
                "by_modality": {
                    "CT": ImagingStudy.objects.filter(modality='CT').count(),
                    "MRI": ImagingStudy.objects.filter(modality='MRI').count(),
                    "XRAY": ImagingStudy.objects.filter(modality='XRAY').count(),
                    "ULTRASOUND": ImagingStudy.objects.filter(modality='ULTRASOUND').count(),
                },
                "by_status": {
                    "pending": ImagingStudy.objects.filter(status='pending').count(),
                    "in_progress": ImagingStudy.objects.filter(status='in_progress').count(),
                    "completed": ImagingStudy.objects.filter(status='completed').count(),
                    "archived": ImagingStudy.objects.filter(status='archived').count(),
                }
            }
            stats["studies"] = study_stats

        return stats

    except Exception as e:
        return {"error": f"Error getting statistics: {str(e)}"}


# Tool dispatch table
# Maps function names (strings) to handler functions
# Lambda functions validate input data using Pydantic models before calling the actual function
# **args unpacks dictionary into keyword arguments
TOOL_HANDLERS = {
    "get_patients": lambda args: get_patients(GetPatientsToolInput(**args)),
    "get_hospitals": lambda args: get_hospitals(GetHospitalsToolInput(**args)),
    "get_studies": lambda args: get_studies(GetStudiesToolInput(**args)),
    "get_statistics": lambda args: get_statistics(GetStatisticsToolInput(**args)),
}


# Tool definitions for OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_patients",
            "description": "Retrieve patients from the database with optional filters for gender, hospital, etc.",
            "parameters": GetPatientsToolInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_hospitals",
            "description": "Retrieve hospitals from the database. Can filter by name.",
            "parameters": GetHospitalsToolInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_studies",
            "description": "Retrieve imaging studies from the database with filters for patient, modality, status, date range, etc.",
            "parameters": GetStudiesToolInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "Get aggregate statistics like total counts, breakdowns by gender/modality/status, etc.",
            "parameters": GetStatisticsToolInput.model_json_schema(),
        }
    },
]
