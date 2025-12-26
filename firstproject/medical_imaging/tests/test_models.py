import pytest
from decimal import Decimal
from datetime import date, datetime
from django.contrib.auth.models import User
from medical_imaging.models import (
    Hospital, Patient, ImagingStudy, DicomImage, Diagnosis
)


@pytest.mark.django_db
class TestHospitalModel:
    """Test Hospital model functionality"""

    def test_create_hospital(self):
        """Test creating a hospital instance"""
        hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )
        assert hospital.name == "Test Hospital"
        assert hospital.contact_email == "test@hospital.com"
        assert str(hospital) == "Test Hospital"

    def test_hospital_patient_count_property(self):
        """Test that hospital correctly counts patients"""
        hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )

        # Create patients
        Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        Patient.objects.create(
            medical_record_number="MRN002",
            first_name="Jane",
            last_name="Doe",
            date_of_birth=date(1992, 1, 1),
            gender="F",
            hospital=hospital
        )

        assert hospital.patient_count == 2


@pytest.mark.django_db
class TestPatientModel:
    """Test Patient model functionality"""

    @pytest.fixture
    def hospital(self):
        """Create a test hospital"""
        return Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )

    def test_create_patient(self, hospital):
        """Test creating a patient instance"""
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            email="john@example.com",
            phone="1234567890",
            hospital=hospital
        )
        assert patient.medical_record_number == "MRN001"
        assert patient.full_name == "John Doe"
        assert patient.gender == "M"

    def test_patient_full_name_property(self, hospital):
        """Test patient full_name property"""
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        assert patient.full_name == "John Doe"

    def test_patient_age_calculation(self, hospital):
        """Test patient age calculation"""
        # Create patient born 30 years ago
        birth_year = datetime.now().year - 30
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(birth_year, 1, 1),
            gender="M",
            hospital=hospital
        )
        # Age should be 30 or 29 depending on current date
        assert patient.age in [29, 30]

    def test_patient_string_representation(self, hospital):
        """Test patient __str__ method"""
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        assert str(patient) == "John Doe (MRN001)"


@pytest.mark.django_db
class TestImagingStudyModel:
    """Test ImagingStudy model functionality"""

    @pytest.fixture
    def setup_data(self):
        """Create test data"""
        hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        return {'hospital': hospital, 'patient': patient}

    def test_create_imaging_study(self, setup_data):
        """Test creating an imaging study"""
        study = ImagingStudy.objects.create(
            patient=setup_data['patient'],
            study_date=date.today(),
            modality="CT",
            body_part="Chest",
            status="pending",
            description="Chest CT scan"
        )
        assert study.modality == "CT"
        assert study.status == "pending"
        assert study.body_part == "Chest"

    def test_imaging_study_status_choices(self, setup_data):
        """Test all valid status choices"""
        statuses = ['pending', 'in_progress', 'completed', 'archived']
        for status in statuses:
            study = ImagingStudy.objects.create(
                patient=setup_data['patient'],
                study_date=date.today(),
                modality="CT",
                body_part="Chest",
                status=status
            )
            assert study.status == status

    def test_imaging_study_modality_choices(self, setup_data):
        """Test all valid modality choices"""
        modalities = ['CT', 'MRI', 'XRAY', 'ULTRASOUND']
        for modality in modalities:
            study = ImagingStudy.objects.create(
                patient=setup_data['patient'],
                study_date=date.today(),
                modality=modality,
                body_part="Chest",
                status="pending"
            )
            assert study.modality == modality


@pytest.mark.django_db
class TestDicomImageModel:
    """Test DicomImage model functionality"""

    @pytest.fixture
    def setup_study(self):
        """Create test study"""
        hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        study = ImagingStudy.objects.create(
            patient=patient,
            study_date=date.today(),
            modality="CT",
            body_part="Chest",
            status="pending"
        )
        return study

    def test_create_dicom_image_minimal(self, setup_study):
        """Test creating a minimal DICOM image"""
        image = DicomImage.objects.create(
            study=setup_study,
            instance_number=1,
            is_dicom=False
        )
        assert image.instance_number == 1
        assert image.is_dicom is False

    def test_create_dicom_image_with_metadata(self, setup_study):
        """Test creating DICOM image with full metadata"""
        image = DicomImage.objects.create(
            study=setup_study,
            instance_number=1,
            is_dicom=True,
            slice_thickness=5.0,
            slice_location=123.456789,
            pixel_spacing="0.5\\0.5",
            rows=512,
            columns=512,
            bits_allocated=16,
            bits_stored=12,
            window_center="40",
            window_width="400",
            rescale_intercept=-1024,
            rescale_slope=1,
            manufacturer="Test Manufacturer",
            manufacturer_model="Test Model",
            sop_instance_uid="1.2.3.4.5.6.7.8.9",
            dicom_metadata={"test": "data"}
        )
        assert image.is_dicom is True
        assert image.slice_location == 123.456789
        assert image.rows == 512
        assert image.columns == 512
        assert image.sop_instance_uid == "1.2.3.4.5.6.7.8.9"

    def test_dicom_image_sop_uid_unique(self, setup_study):
        """Test that SOP Instance UID is unique"""
        DicomImage.objects.create(
            study=setup_study,
            instance_number=1,
            is_dicom=True,
            sop_instance_uid="1.2.3.4.5"
        )

        # Creating another with same UID should fail
        with pytest.raises(Exception):
            DicomImage.objects.create(
                study=setup_study,
                instance_number=2,
                is_dicom=True,
                sop_instance_uid="1.2.3.4.5"
            )

    def test_slice_location_float_precision(self, setup_study):
        """Test that slice_location accepts high precision floats"""
        high_precision_value = 123.456789012345
        image = DicomImage.objects.create(
            study=setup_study,
            instance_number=1,
            is_dicom=True,
            slice_location=high_precision_value
        )
        # FloatField should preserve reasonable precision
        assert abs(image.slice_location - high_precision_value) < 0.000001


@pytest.mark.django_db
class TestDiagnosisModel:
    """Test Diagnosis model functionality"""

    @pytest.fixture
    def setup_data(self):
        """Create test data"""
        hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        study = ImagingStudy.objects.create(
            patient=patient,
            study_date=date.today(),
            modality="CT",
            body_part="Chest",
            status="completed"
        )
        radiologist = User.objects.create_user(
            username="radiologist",
            email="radiologist@hospital.com"
        )
        return {'study': study, 'radiologist': radiologist}

    def test_create_diagnosis(self, setup_data):
        """Test creating a diagnosis"""
        diagnosis = Diagnosis.objects.create(
            study=setup_data['study'],
            radiologist=setup_data['radiologist'],
            findings="No abnormalities detected",
            impression="Normal study",
            severity="normal",
            recommendations="No follow-up needed"
        )
        assert diagnosis.findings == "No abnormalities detected"
        assert diagnosis.severity == "normal"

    def test_diagnosis_severity_choices(self, setup_data):
        """Test all valid severity choices"""
        severities = ['normal', 'minor', 'moderate', 'severe']
        for severity in severities:
            diagnosis = Diagnosis.objects.create(
                study=setup_data['study'],
                radiologist=setup_data['radiologist'],
                findings="Test findings",
                impression="Test impression",
                severity=severity,
                recommendations="Test recommendations"
            )
            assert diagnosis.severity == severity
