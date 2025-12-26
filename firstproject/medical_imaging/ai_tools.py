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
    gender: Literal["M", "F", "O"] | None = Field(
        None,
        description="Filter by gender. M=Male, F=Female, O=Other"
    )
    hospital_id: int | None = Field(
        None,
        description="Filter by hospital ID"
    )
    limit: int = Field(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )


class GetHospitalsToolInput(BaseModel):
    """Get a list of hospitals with optional filters"""
    name_contains: str | None = Field(
        None,
        description="Filter hospitals whose name contains this text (case-insensitive)"
    )
    limit: int = Field(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=100
    )


class GetStudiesToolInput(BaseModel):
    """Get a list of imaging studies with optional filters"""
    patient_id: int | None = Field(
        None,
        description="Filter by patient ID"
    )
    modality: Literal["CT", "MRI", "XRAY", "ULTRASOUND"] | None = Field(
        None,
        description="Filter by imaging modality type"
    )
    status: Literal["pending", "in_progress", "completed", "archived"] | None = Field(
        None,
        description="Filter by study status"
    )
    days_ago: int | None = Field(
        None,
        description="Filter studies from the last N days",
        ge=1,
        le=365
    )
    limit: int = Field(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=100
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

    Returns:
        dict: Contains 'count' and 'patients' list
    """
    try:
        queryset = Patient.objects.select_related('hospital')

        if input_data.gender:
            queryset = queryset.filter(gender=input_data.gender)

        if input_data.hospital_id:
            queryset = queryset.filter(hospital_id=input_data.hospital_id)

        # Get count before limit
        total_count = queryset.count()

        # Apply limit
        patients = queryset[:input_data.limit]

        # Serialize data
        patient_list = [
            {
                "id": p.id,
                "mrn": p.medical_record_number,
                "full_name": p.full_name,
                "gender": p.get_gender_display(),
                "date_of_birth": p.date_of_birth.isoformat(),
                "hospital": p.hospital.name,
                "email": p.email or None,
                "phone": p.phone or None,
            }
            for p in patients
        ]

        return {
            "total_count": total_count,
            "returned_count": len(patient_list),
            "limit": input_data.limit,
            "patients": patient_list
        }

    except Exception as e:
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

    Returns:
        dict: Contains 'count' and 'studies' list
    """
    try:
        queryset = ImagingStudy.objects.select_related(
            'patient',
            'patient__hospital'
        ).annotate(
            image_count=Count('images')
        )

        if input_data.patient_id:
            queryset = queryset.filter(patient_id=input_data.patient_id)

        if input_data.modality:
            queryset = queryset.filter(modality=input_data.modality)

        if input_data.status:
            queryset = queryset.filter(status=input_data.status)

        if input_data.days_ago:
            cutoff_date = timezone.now() - timedelta(days=input_data.days_ago)
            queryset = queryset.filter(study_date__gte=cutoff_date)

        # Get count before limit
        total_count = queryset.count()

        # Apply limit
        studies = queryset[:input_data.limit]

        # Serialize data
        study_list = [
            {
                "id": s.id,
                "patient_name": s.patient.full_name,
                "patient_mrn": s.patient.medical_record_number,
                "hospital": s.patient.hospital.name,
                "study_date": s.study_date.isoformat(),
                "modality": s.get_modality_display(),
                "body_part": s.body_part,
                "status": s.get_status_display(),
                "image_count": s.image_count,
                "clinical_notes": s.clinical_notes[:200] if s.clinical_notes else None,
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
