import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import DicomMetadataViewer from '../DicomMetadataViewer';
import { DicomImage } from '@/lib/api/types';

describe('DicomMetadataViewer', () => {
  const mockDicomImage: DicomImage = {
    id: 1,
    study: 1,
    instance_number: 1,
    image_file: 'test.dcm',
    image_url: 'http://localhost:8000/media/test.dcm',
    is_dicom: true,
    slice_thickness: 5.0,
    pixel_spacing: '0.5\\0.5',
    slice_location: 123.456,
    rows: 512,
    columns: 512,
    bits_allocated: 16,
    bits_stored: 12,
    window_center: '40',
    window_width: '400',
    rescale_intercept: -1024,
    rescale_slope: 1,
    manufacturer: 'Test Manufacturer',
    manufacturer_model: 'Test Model X',
    sop_instance_uid: '1.2.3.4.5.6.7.8.9',
    dicom_metadata: {
      patient: { name: 'John Doe' },
      study: { date: '2024-01-01' }
    },
    file_size_bytes: 1024000,
    uploaded_at: '2024-01-01T12:00:00Z',
  };

  const mockNonDicomImage: DicomImage = {
    id: 2,
    study: 1,
    instance_number: 1,
    image_file: 'test.jpg',
    image_url: 'http://localhost:8000/media/test.jpg',
    is_dicom: false,
    file_size_bytes: 50000,
    uploaded_at: '2024-01-01T12:00:00Z',
  };

  describe('Non-DICOM Image', () => {
    it('should display message for non-DICOM files', () => {
      render(<DicomMetadataViewer image={mockNonDicomImage} />);

      expect(screen.getByText(/not a DICOM file/i)).toBeInTheDocument();
      expect(screen.getByText('Image Information')).toBeInTheDocument();
    });

    it('should show file size for non-DICOM images', () => {
      render(<DicomMetadataViewer image={mockNonDicomImage} />);

      expect(screen.getByText('File Size:')).toBeInTheDocument();
      expect(screen.getByText(/KB/)).toBeInTheDocument();
    });

    it('should show upload date for non-DICOM images', () => {
      render(<DicomMetadataViewer image={mockNonDicomImage} />);

      expect(screen.getByText('Uploaded:')).toBeInTheDocument();
    });
  });

  describe('DICOM Image - Header', () => {
    it('should display DICOM Metadata title', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('DICOM Metadata')).toBeInTheDocument();
    });

    it('should show DICOM File badge', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('DICOM File')).toBeInTheDocument();
    });

    it('should display description', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText(/Medical imaging data/i)).toBeInTheDocument();
    });
  });

  describe('DICOM Image - Tabs', () => {
    it('should render all three tabs', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByRole('tab', { name: /Basic Info/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Technical/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /Equipment/i })).toBeInTheDocument();
    });

    it('should have Basic Info tab selected by default', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const basicTab = screen.getByRole('tab', { name: /Basic Info/i });
      expect(basicTab).toHaveAttribute('data-state', 'active');
    });

    it('should switch tabs when clicked', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(technicalTab).toHaveAttribute('data-state', 'active');
    });
  });

  describe('DICOM Image - Basic Info Tab', () => {
    it('should display instance number', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('Instance Number')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('should display SOP Instance UID', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('SOP Instance UID')).toBeInTheDocument();
      expect(screen.getByText(mockDicomImage.sop_instance_uid!)).toBeInTheDocument();
    });

    it('should display image dimensions', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('Image Size')).toBeInTheDocument();
      expect(screen.getByText('512 × 512 pixels')).toBeInTheDocument();
    });

    it('should display file size', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('File Size')).toBeInTheDocument();
      expect(screen.getByText(/KB/)).toBeInTheDocument();
    });

    it('should display upload timestamp', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      expect(screen.getByText('Uploaded')).toBeInTheDocument();
    });
  });

  describe('DICOM Image - Technical Tab', () => {
    it('should display slice thickness', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(screen.getByText('Slice Thickness')).toBeInTheDocument();
      expect(screen.getByText('5 mm')).toBeInTheDocument();
    });

    it('should display slice location', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(screen.getByText('Slice Location')).toBeInTheDocument();
      expect(screen.getByText(/123.456/)).toBeInTheDocument();
    });

    it('should display window/level settings', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(screen.getByText('Window Center')).toBeInTheDocument();
      expect(screen.getByText('40')).toBeInTheDocument();
      expect(screen.getByText('Window Width')).toBeInTheDocument();
      expect(screen.getByText('400')).toBeInTheDocument();
    });

    it('should display Hounsfield unit parameters', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(screen.getByText('Rescale Intercept')).toBeInTheDocument();
      expect(screen.getByText('-1024')).toBeInTheDocument();
      expect(screen.getByText('Rescale Slope')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('should display pixel spacing', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(screen.getByText('Pixel Spacing')).toBeInTheDocument();
      expect(screen.getByText('0.5\\0.5')).toBeInTheDocument();
    });

    it('should display bits allocated and stored', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const technicalTab = screen.getByRole('tab', { name: /Technical/i });
      await user.click(technicalTab);

      expect(screen.getByText('Bits Allocated')).toBeInTheDocument();
      expect(screen.getByText('16')).toBeInTheDocument();
      expect(screen.getByText('Bits Stored')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
    });
  });

  describe('DICOM Image - Equipment Tab', () => {
    it('should display manufacturer', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const equipmentTab = screen.getByRole('tab', { name: /Equipment/i });
      await user.click(equipmentTab);

      expect(screen.getByText('Manufacturer')).toBeInTheDocument();
      expect(screen.getByText('Test Manufacturer')).toBeInTheDocument();
    });

    it('should display model', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const equipmentTab = screen.getByRole('tab', { name: /Equipment/i });
      await user.click(equipmentTab);

      expect(screen.getByText('Model')).toBeInTheDocument();
      expect(screen.getByText('Test Model X')).toBeInTheDocument();
    });

    it('should display additional DICOM tags section', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const equipmentTab = screen.getByRole('tab', { name: /Equipment/i });
      await user.click(equipmentTab);

      expect(screen.getByText('Additional DICOM Tags')).toBeInTheDocument();
    });

    it('should render DICOM metadata as JSON', async () => {
      const user = userEvent.setup();
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const equipmentTab = screen.getByRole('tab', { name: /Equipment/i });
      await user.click(equipmentTab);

      const jsonContent = screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'pre' && content.includes('John Doe');
      });
      expect(jsonContent).toBeInTheDocument();
    });
  });

  describe('MetadataField Component', () => {
    it('should not render fields with null values', () => {
      const imageWithNulls: DicomImage = {
        ...mockDicomImage,
        slice_thickness: undefined,
        manufacturer: undefined,
      };

      render(<DicomMetadataViewer image={imageWithNulls} />);

      expect(screen.queryByText('Slice Thickness')).not.toBeInTheDocument();
    });

    it('should not render fields with empty string values', () => {
      const imageWithEmpty: DicomImage = {
        ...mockDicomImage,
        manufacturer: '',
      };

      render(<DicomMetadataViewer image={imageWithEmpty} />);

      expect(screen.queryByText('Manufacturer')).not.toBeInTheDocument();
    });

    it('should truncate long SOP UIDs with title attribute', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const sopElement = screen.getByText(mockDicomImage.sop_instance_uid!);
      expect(sopElement).toHaveClass('truncate');
      expect(sopElement).toHaveAttribute('title', mockDicomImage.sop_instance_uid);
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels for tabs', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(3);
      tabs.forEach(tab => {
        expect(tab).toHaveAttribute('aria-selected');
      });
    });

    it('should have readable text for screen readers', () => {
      render(<DicomMetadataViewer image={mockDicomImage} />);

      const content = screen.getByText('DICOM Metadata');
      expect(content).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing optional DICOM fields', () => {
      const minimalDicom: DicomImage = {
        id: 3,
        study: 1,
        instance_number: 1,
        image_file: 'minimal.dcm',
        image_url: 'http://localhost:8000/media/minimal.dcm',
        is_dicom: true,
        file_size_bytes: 1000,
        uploaded_at: '2024-01-01T12:00:00Z',
      };

      render(<DicomMetadataViewer image={minimalDicom} />);

      expect(screen.getByText('DICOM Metadata')).toBeInTheDocument();
    });

    it('should format large file sizes correctly', () => {
      const largeImage: DicomImage = {
        ...mockDicomImage,
        file_size_bytes: 10485760, // 10 MB
      };

      render(<DicomMetadataViewer image={largeImage} />);

      expect(screen.getByText(/KB/)).toBeInTheDocument();
    });
  });
});
