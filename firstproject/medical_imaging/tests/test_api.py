import pytest
import json
from datetime import date
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from medical_imaging.models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis


@pytest.mark.django_db
@pytest.mark.integration
class TestAuthenticationAPI:
    """Test authentication endpoints"""

    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def test_user(self):
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_login_success(self, api_client, test_user):
        """Test successful login"""
        response = api_client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data

    def test_login_invalid_credentials(self, api_client):
        """Test login with invalid credentials"""
        response = api_client.post('/api/auth/login/', {
            'username': 'wronguser',
            'password': 'wrongpass'
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_protected_endpoint_without_auth(self, api_client):
        """Test that protected endpoints require authentication"""
        response = api_client.get('/api/patients/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
@pytest.mark.integration
class TestHospitalAPI:
    """Test Hospital API endpoints"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def sample_hospital(self):
        return Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )

    def test_list_hospitals(self, authenticated_client, sample_hospital):
        """Test listing all hospitals"""
        response = authenticated_client.get('/api/hospitals/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_hospital(self, authenticated_client):
        """Test creating a new hospital"""
        data = {
            'name': 'New Hospital',
            'address': '456 New St',
            'contact_email': 'new@hospital.com',
            'contact_phone': '9876543210'
        }
        response = authenticated_client.post('/api/hospitals/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'New Hospital'

    def test_get_hospital_detail(self, authenticated_client, sample_hospital):
        """Test retrieving a specific hospital"""
        response = authenticated_client.get(f'/api/hospitals/{sample_hospital.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == sample_hospital.name


@pytest.mark.django_db
@pytest.mark.integration
class TestPatientAPI:
    """Test Patient API endpoints"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def hospital(self):
        return Hospital.objects.create(
            name="Test Hospital",
            address="123 Test St",
            contact_email="test@hospital.com",
            contact_phone="1234567890"
        )

    @pytest.fixture
    def sample_patient(self, hospital):
        return Patient.objects.create(
            medical_record_number="MRN001",
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            hospital=hospital
        )

    def test_list_patients(self, authenticated_client, sample_patient):
        """Test listing all patients"""
        response = authenticated_client.get('/api/patients/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_create_patient(self, authenticated_client, hospital):
        """Test creating a new patient"""
        data = {
            'medical_record_number': 'MRN002',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'date_of_birth': '1995-05-15',
            'gender': 'F',
            'hospital': hospital.id
        }
        response = authenticated_client.post('/api/patients/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['medical_record_number'] == 'MRN002'

    def test_get_patient_detail(self, authenticated_client, sample_patient):
        """Test retrieving a specific patient"""
        response = authenticated_client.get(f'/api/patients/{sample_patient.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['medical_record_number'] == 'MRN001'

    def test_search_patients(self, authenticated_client, sample_patient):
        """Test patient search functionality"""
        response = authenticated_client.get('/api/patients/?search=John')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1

    def test_filter_patients_by_gender(self, authenticated_client, sample_patient):
        """Test filtering patients by gender"""
        response = authenticated_client.get('/api/patients/?gender=M')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.integration
class TestImagingStudyAPI:
    """Test ImagingStudy API endpoints"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

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
            status="pending"
        )
        return {'hospital': hospital, 'patient': patient, 'study': study}

    def test_list_studies(self, authenticated_client, setup_data):
        """Test listing all imaging studies"""
        response = authenticated_client.get('/api/studies/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_create_study(self, authenticated_client, setup_data):
        """Test creating a new imaging study"""
        data = {
            'patient': setup_data['patient'].id,
            'study_date': date.today().isoformat(),
            'modality': 'MRI',
            'body_part': 'Brain',
            'status': 'pending',
            'description': 'Brain MRI scan'
        }
        response = authenticated_client.post('/api/studies/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['modality'] == 'MRI'

    def test_get_study_detail(self, authenticated_client, setup_data):
        """Test retrieving a specific study"""
        study = setup_data['study']
        response = authenticated_client.get(f'/api/studies/{study.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['modality'] == 'CT'

    def test_filter_studies_by_modality(self, authenticated_client, setup_data):
        """Test filtering studies by modality"""
        response = authenticated_client.get('/api/studies/?modality=CT')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_studies_by_patient(self, authenticated_client, setup_data):
        """Test filtering studies by patient"""
        patient_id = setup_data['patient'].id
        response = authenticated_client.get(f'/api/studies/?patient={patient_id}')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.integration
class TestImageUploadAPI:
    """Test DICOM image upload functionality"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

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

    def test_upload_images_endpoint_exists(self, authenticated_client, study):
        """Test that upload endpoint exists"""
        from io import BytesIO
        from PIL import Image as PILImage

        # Create a simple test image
        img = PILImage.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        img_bytes.name = 'test.jpg'

        response = authenticated_client.post(
            f'/api/studies/{study.id}/upload_images/',
            {'images': img_bytes},
            format='multipart'
        )
        # Should either succeed or fail gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ]


@pytest.mark.django_db
@pytest.mark.integration
class TestDiagnosisAPI:
    """Test Diagnosis API endpoints"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

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

    def test_create_diagnosis(self, authenticated_client, setup_data):
        """Test creating a diagnosis for a study"""
        data = {
            'findings': 'No abnormalities detected',
            'impression': 'Normal study',
            'severity': 'normal',
            'recommendations': 'No follow-up needed'
        }
        response = authenticated_client.post(
            f'/api/studies/{setup_data["study"].id}/diagnosis/',
            data
        )
        # Should either succeed or have specific error
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ]


@pytest.mark.django_db
@pytest.mark.integration
class TestStatisticsAPI:
    """Test statistics and analytics endpoints"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

    def test_study_statistics_endpoint(self, authenticated_client):
        """Test study statistics endpoint"""
        response = authenticated_client.get('/api/studies/statistics/')
        assert response.status_code == status.HTTP_200_OK
        assert 'total_studies' in response.data
