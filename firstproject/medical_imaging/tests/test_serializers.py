import pytest
from datetime import date
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory
from medical_imaging.models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis
from medical_imaging.serializers import (
    HospitalSerializer,
    PatientListSerializer,
    PatientDetailSerializer,
    ImagingStudyListSerializer,
    ImagingStudyDetailSerializer,
    DicomImageSerializer,
    DiagnosisSerializer
)


@pytest.mark.django_db
class TestHospitalSerializer:
    """Test HospitalSerializer"""

    def test_serialize_hospital(self):
        """Test serializing a hospital instance"""
        hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )
        serializer = HospitalSerializer(hospital)
        data = serializer.data

        assert data['name'] == "Test Hospital"
        assert data['address'] == "123 Test St"
        assert data['contact_email'] == "test@hospital.com"
        assert 'id' in data
        assert 'created_at' in data

    def test_deserialize_hospital(self):
        """Test deserializing hospital data"""
        data = {
            'name': 'New Hospital',
            'address': '456 New St',
            'contact_email': 'new@hospital.com',
            'contact_phone': '9876543210'
        }
        serializer = HospitalSerializer(data=data)
        assert serializer.is_valid()
        hospital = serializer.save()
        assert hospital.name == 'New Hospital'

    def test_hospital_validation_required_fields(self):
        """Test that required fields are validated"""
        data = {'name': 'Test'}  # Missing required fields
        serializer = HospitalSerializer(data=data)
        assert not serializer.is_valid()
        assert 'address' in serializer.errors or 'contact_email' in serializer.errors


@pytest.mark.django_db
class TestPatientSerializer:
    """Test PatientSerializer"""

    @pytest.fixture
    def hospital(self):
        return Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )

    def test_serialize_patient(self, hospital):
        """Test serializing a patient instance"""
        patient = Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )
        factory = APIRequestFactory()
        request = factory.get('/')
        serializer = PatientListSerializer(patient, context={'request': request})
        data = serializer.data

        assert data['medical_record_number'] == "MRN001"
        assert data['first_name'] == "John"
        assert data['last_name'] == "Doe"
        assert 'full_name' in data
        assert 'id' in data

    def test_deserialize_patient(self, hospital):
        """Test deserializing patient data"""
        data = {
            'medical_record_number': 'MRN002',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'date_of_birth': '1995-05-15',
            'gender': 'F',
            'hospital': hospital.id
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = PatientListSerializer(data=data, context={'request': request})
        assert serializer.is_valid(), serializer.errors
        patient = serializer.save()
        assert patient.first_name == 'Jane'

    def test_patient_validation_gender_choices(self, hospital):
        """Test gender field validation"""
        data = {
            'medical_record_number': 'MRN003',
            'first_name': 'Test',
            'last_name': 'User',
            'date_of_birth': '1990-01-01',
            'gender': 'X',  # Invalid choice
            'hospital': hospital.id
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = PatientListSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'gender' in serializer.errors


@pytest.mark.django_db
class TestImagingStudySerializer:
    """Test ImagingStudySerializer"""

    @pytest.fixture
    def setup_data(self):
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

    def test_serialize_imaging_study(self, setup_data):
        """Test serializing an imaging study"""
        study = ImagingStudy.objects.create(
            patient=setup_data['patient'],
            study_date=date.today(),
            modality="CT",
            body_part="Chest",
            status="pending"
        )
        factory = APIRequestFactory()
        request = factory.get('/')
        serializer = ImagingStudyListSerializer(study, context={'request': request})
        data = serializer.data

        assert data['modality'] == "CT"
        assert data['body_part'] == "Chest"
        assert data['status'] == "pending"
        assert 'id' in data

    def test_deserialize_imaging_study(self, setup_data):
        """Test deserializing imaging study data"""
        data = {
            'patient': setup_data['patient'].id,
            'study_date': date.today().isoformat(),
            'modality': 'MRI',
            'body_part': 'Brain',
            'status': 'pending'
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = ImagingStudyListSerializer(data=data, context={'request': request})
        assert serializer.is_valid(), serializer.errors
        study = serializer.save()
        assert study.modality == 'MRI'

    def test_study_modality_validation(self, setup_data):
        """Test modality field validation"""
        data = {
            'patient': setup_data['patient'].id,
            'study_date': date.today().isoformat(),
            'modality': 'INVALID',  # Invalid modality
            'body_part': 'Brain',
            'status': 'pending'
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = ImagingStudyListSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'modality' in serializer.errors


@pytest.mark.django_db
class TestDicomImageSerializer:
    """Test DicomImageSerializer"""

    @pytest.fixture
    def study(self):
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
        return ImagingStudy.objects.create(
            patient=patient,
            study_date=date.today(),
            modality="CT",
            body_part="Chest",
            status="pending"
        )

    def test_serialize_dicom_image(self, study):
        """Test serializing a DICOM image"""
        image = DicomImage.objects.create(
            study=study,
            instance_number=1,
            is_dicom=True,
            slice_thickness=5.0,
            rows=512,
            columns=512
        )
        factory = APIRequestFactory()
        request = factory.get('/')
        serializer = DicomImageSerializer(image, context={'request': request})
        data = serializer.data

        assert data['instance_number'] == 1
        assert data['is_dicom'] is True
        assert 'id' in data

    def test_deserialize_dicom_image_minimal(self, study):
        """Test deserializing minimal DICOM image data"""
        data = {
            'study': study.id,
            'instance_number': 1,
            'is_dicom': False
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = DicomImageSerializer(data=data, context={'request': request})
        assert serializer.is_valid(), serializer.errors
        image = serializer.save()
        assert image.instance_number == 1

    def test_deserialize_dicom_image_with_metadata(self, study):
        """Test deserializing DICOM image with full metadata"""
        data = {
            'study': study.id,
            'instance_number': 1,
            'is_dicom': True,
            'slice_thickness': 5.0,
            'slice_location': 123.456,
            'pixel_spacing': '0.5\\0.5',
            'rows': 512,
            'columns': 512,
            'bits_allocated': 16,
            'bits_stored': 12,
            'window_center': '40',
            'window_width': '400',
            'rescale_intercept': -1024,
            'rescale_slope': 1,
            'manufacturer': 'Test Manufacturer',
            'sop_instance_uid': '1.2.3.4.5.6.7.8.9'
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = DicomImageSerializer(data=data, context={'request': request})
        assert serializer.is_valid(), serializer.errors
        image = serializer.save()
        assert image.is_dicom is True
        assert image.rows == 512


@pytest.mark.django_db
class TestDiagnosisSerializer:
    """Test DiagnosisSerializer"""

    @pytest.fixture
    def setup_data(self):
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
            email="radiologist@hospital.com",
            password="testpass123"
        )
        return {'study': study, 'radiologist': radiologist}

    def test_serialize_diagnosis(self, setup_data):
        """Test serializing a diagnosis"""
        diagnosis = Diagnosis.objects.create(
            study=setup_data['study'],
            radiologist=setup_data['radiologist'],
            findings="No abnormalities detected",
            impression="Normal study",
            severity="normal",
            recommendations="No follow-up needed"
        )
        factory = APIRequestFactory()
        request = factory.get('/')
        serializer = DiagnosisSerializer(diagnosis, context={'request': request})
        data = serializer.data

        assert data['findings'] == "No abnormalities detected"
        assert data['severity'] == "normal"
        assert 'id' in data

    def test_deserialize_diagnosis(self, setup_data):
        """Test deserializing diagnosis data"""
        data = {
            'study': setup_data['study'].id,
            'radiologist': setup_data['radiologist'].id,
            'findings': 'Test findings',
            'impression': 'Test impression',
            'severity': 'minor',
            'recommendations': 'Follow-up in 6 months'
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = DiagnosisSerializer(data=data, context={'request': request})
        assert serializer.is_valid(), serializer.errors
        diagnosis = serializer.save()
        assert diagnosis.severity == 'minor'

    def test_diagnosis_severity_validation(self, setup_data):
        """Test severity field validation"""
        data = {
            'study': setup_data['study'].id,
            'radiologist': setup_data['radiologist'].id,
            'findings': 'Test findings',
            'impression': 'Test impression',
            'severity': 'INVALID',  # Invalid severity
            'recommendations': 'Test'
        }
        factory = APIRequestFactory()
        request = factory.post('/')
        serializer = DiagnosisSerializer(data=data, context={'request': request})
        assert not serializer.is_valid()
        assert 'severity' in serializer.errors
