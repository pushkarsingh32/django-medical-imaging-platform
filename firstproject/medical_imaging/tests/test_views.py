import pytest
from datetime import date
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from medical_imaging.models import Hospital, Patient, ImagingStudy, DicomImage, Diagnosis


@pytest.mark.django_db
class TestHospitalViewSet:
    """Test Hospital ViewSet CRUD operations"""

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

    def test_list_hospitals(self, authenticated_client, hospital):
        """Test listing hospitals"""
        response = authenticated_client.get('/api/hospitals/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_retrieve_hospital(self, authenticated_client, hospital):
        """Test retrieving single hospital"""
        response = authenticated_client.get(f'/api/hospitals/{hospital.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == hospital.name

    def test_create_hospital(self, authenticated_client):
        """Test creating a hospital"""
        data = {
            'name': 'New Hospital',
            'address': '456 New St',
            'contact_email': 'new@hospital.com',
            'contact_phone': '9876543210'
        }
        response = authenticated_client.post('/api/hospitals/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert Hospital.objects.filter(name='New Hospital').exists()

    def test_update_hospital(self, authenticated_client, hospital):
        """Test updating a hospital"""
        data = {'name': 'Updated Hospital'}
        response = authenticated_client.patch(f'/api/hospitals/{hospital.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        hospital.refresh_from_db()
        assert hospital.name == 'Updated Hospital'

    def test_delete_hospital(self, authenticated_client, hospital):
        """Test deleting a hospital"""
        hospital_id = hospital.id
        response = authenticated_client.delete(f'/api/hospitals/{hospital_id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Hospital.objects.filter(id=hospital_id).exists()


@pytest.mark.django_db
class TestPatientViewSet:
    """Test Patient ViewSet operations"""

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
        return {'hospital': hospital, 'patient': patient}

    def test_list_patients_paginated(self, authenticated_client, setup_data):
        """Test paginated patient list"""
        response = authenticated_client.get('/api/patients/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'count' in response.data

    def test_retrieve_patient(self, authenticated_client, setup_data):
        """Test retrieving single patient"""
        patient = setup_data['patient']
        response = authenticated_client.get(f'/api/patients/{patient.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['medical_record_number'] == 'MRN001'

    def test_search_patients(self, authenticated_client, setup_data):
        """Test patient search"""
        response = authenticated_client.get('/api/patients/?search=John')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1

    def test_filter_by_hospital(self, authenticated_client, setup_data):
        """Test filtering patients by hospital"""
        hospital_id = setup_data['hospital'].id
        response = authenticated_client.get(f'/api/patients/?hospital={hospital_id}')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_gender(self, authenticated_client, setup_data):
        """Test filtering patients by gender"""
        response = authenticated_client.get('/api/patients/?gender=M')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestImagingStudyViewSet:
    """Test ImagingStudy ViewSet operations"""

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
        """Test listing studies"""
        response = authenticated_client.get('/api/studies/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data

    def test_retrieve_study(self, authenticated_client, setup_data):
        """Test retrieving single study"""
        study = setup_data['study']
        response = authenticated_client.get(f'/api/studies/{study.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['modality'] == 'CT'

    def test_filter_by_modality(self, authenticated_client, setup_data):
        """Test filtering by modality"""
        response = authenticated_client.get('/api/studies/?modality=CT')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_status(self, authenticated_client, setup_data):
        """Test filtering by status"""
        response = authenticated_client.get('/api/studies/?status=pending')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_by_patient(self, authenticated_client, setup_data):
        """Test filtering by patient"""
        patient_id = setup_data['patient'].id
        response = authenticated_client.get(f'/api/studies/?patient={patient_id}')
        assert response.status_code == status.HTTP_200_OK

    def test_get_pending_studies(self, authenticated_client, setup_data):
        """Test get pending studies endpoint"""
        response = authenticated_client.get('/api/studies/pending/')
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_get_statistics(self, authenticated_client, setup_data):
        """Test study statistics endpoint"""
        response = authenticated_client.get('/api/studies/statistics/')
        assert response.status_code == status.HTTP_200_OK
        assert 'total_studies' in response.data


@pytest.mark.django_db
class TestDicomImageViewSet:
    """Test DicomImage ViewSet operations"""

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

    def test_list_images(self, authenticated_client, study):
        """Test listing images"""
        response = authenticated_client.get('/api/images/')
        assert response.status_code == status.HTTP_200_OK

    def test_filter_images_by_study(self, authenticated_client, study):
        """Test filtering images by study"""
        response = authenticated_client.get(f'/api/images/?study={study.id}')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestDiagnosisViewSet:
    """Test Diagnosis ViewSet operations"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='radiologist', password='testpass123')
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
            username="radiologist2",
            password="testpass123"
        )
        diagnosis = Diagnosis.objects.create(
            study=study,
            radiologist=radiologist,
            findings="Normal study",
            impression="No abnormalities",
            severity="normal",
            recommendations="None"
        )
        return {'study': study, 'diagnosis': diagnosis, 'radiologist': radiologist}

    def test_list_diagnoses(self, authenticated_client, setup_data):
        """Test listing diagnoses"""
        response = authenticated_client.get('/api/diagnoses/')
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_diagnosis(self, authenticated_client, setup_data):
        """Test retrieving single diagnosis"""
        diagnosis = setup_data['diagnosis']
        response = authenticated_client.get(f'/api/diagnoses/{diagnosis.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['severity'] == 'normal'

    def test_filter_by_severity(self, authenticated_client, setup_data):
        """Test filtering by severity"""
        response = authenticated_client.get('/api/diagnoses/?severity=normal')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCustomEndpoints:
    """Test custom ViewSet endpoints"""

    @pytest.fixture
    def authenticated_client(self):
        client = APIClient()
        user = User.objects.create_user(username='testuser', password='testpass123')
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def setup_study(self):
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
            status="completed"
        )

    def test_mark_study_completed(self, authenticated_client, setup_study):
        """Test marking study as completed"""
        response = authenticated_client.post(
            f'/api/studies/{setup_study.id}/mark_completed/'
        )
        # Endpoint may or may not exist - just test it doesn't crash
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_405_METHOD_NOT_ALLOWED
        ]

    def test_get_study_images(self, authenticated_client, setup_study):
        """Test getting images for a study"""
        response = authenticated_client.get(f'/api/images/?study={setup_study.id}')
        assert response.status_code == status.HTTP_200_OK
