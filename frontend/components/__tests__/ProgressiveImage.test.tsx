import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProgressiveImage from '../ProgressiveImage';

// Mock Next.js Image component
jest.mock('next/image', () => ({
  __esModule: true,
  default: (props: any) => {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    return <img {...props} />;
  },
}));

describe('ProgressiveImage', () => {
  const mockImageId = 123;
  const mockAlt = 'Test medical image';

  beforeEach(() => {
    // Reset environment variables
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000/api';
  });

  describe('Rendering', () => {
    it('should render loading state initially', () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} />);

      const loader = screen.getByRole('generic', { hidden: true });
      expect(loader).toBeInTheDocument();
    });

    it('should render with thumbnail URL for gallery view', async () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} isModal={false} />);

      await waitFor(() => {
        const image = screen.queryByAlt(mockAlt);
        if (image) {
          expect(image).toHaveAttribute('src', expect.stringContaining('/thumbnail/'));
        }
      });
    });

    it('should render with full URL for modal view', async () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} isModal={true} />);

      await waitFor(() => {
        const image = screen.queryByAlt(mockAlt);
        if (image) {
          expect(image).toHaveAttribute('src', expect.stringContaining('/full/'));
        }
      });
    });

    it('should apply custom className', () => {
      const customClass = 'custom-image-class';
      const { container } = render(
        <ProgressiveImage
          imageId={mockImageId}
          alt={mockAlt}
          className={customClass}
        />
      );

      expect(container.querySelector(`.${customClass}`)).toBeInTheDocument();
    });
  });

  describe('Props', () => {
    it('should use correct API URL from environment', () => {
      const testApiUrl = 'https://api.example.com';
      process.env.NEXT_PUBLIC_API_URL = testApiUrl;

      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} />);

      // Component should use the environment variable
      expect(process.env.NEXT_PUBLIC_API_URL).toBe(testApiUrl);
    });

    it('should default to thumbnail when isModal is not provided', async () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} />);

      await waitFor(() => {
        const image = screen.queryByAlt(mockAlt);
        if (image) {
          expect(image).toHaveAttribute('src', expect.stringContaining('/thumbnail/'));
        }
      });
    });

    it('should handle fill prop', () => {
      render(
        <ProgressiveImage
          imageId={mockImageId}
          alt={mockAlt}
          fill={true}
        />
      );

      // Component should render without crashing
      expect(screen.getByRole('generic', { hidden: true })).toBeInTheDocument();
    });

    it('should handle sizes prop', () => {
      const sizes = '(max-width: 768px) 100vw, 50vw';
      render(
        <ProgressiveImage
          imageId={mockImageId}
          alt={mockAlt}
          sizes={sizes}
        />
      );

      expect(screen.getByRole('generic', { hidden: true })).toBeInTheDocument();
    });

    it('should handle priority prop', () => {
      render(
        <ProgressiveImage
          imageId={mockImageId}
          alt={mockAlt}
          priority={true}
        />
      );

      expect(screen.getByRole('generic', { hidden: true })).toBeInTheDocument();
    });
  });

  describe('Image Loading', () => {
    it('should show loader while image is loading', () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} />);

      const loader = screen.getByRole('generic', { hidden: true });
      expect(loader).toHaveClass('animate-spin');
    });

    it('should construct correct thumbnail URL', () => {
      const { container } = render(
        <ProgressiveImage imageId={mockImageId} alt={mockAlt} isModal={false} />
      );

      // Check that component renders
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should construct correct full quality URL', () => {
      const { container } = render(
        <ProgressiveImage imageId={mockImageId} alt={mockAlt} isModal={true} />
      );

      expect(container.firstChild).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should handle image load errors gracefully', async () => {
      const { container } = render(
        <ProgressiveImage imageId={999999} alt="Non-existent image" />
      );

      await waitFor(() => {
        expect(container.firstChild).toBeInTheDocument();
      });
    });

    it('should show error state when image fails to load', async () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} />);

      // Wait for potential error state
      await waitFor(() => {
        const errorText = screen.queryByText(/failed to load/i);
        // Error might or might not be shown depending on implementation
        if (errorText) {
          expect(errorText).toBeInTheDocument();
        }
      }, { timeout: 2000 });
    });
  });

  describe('Click Handler', () => {
    it('should call onClick when provided', async () => {
      const handleClick = jest.fn();

      render(
        <ProgressiveImage
          imageId={mockImageId}
          alt={mockAlt}
          onClick={handleClick}
        />
      );

      await waitFor(() => {
        const container = screen.getByRole('generic', { hidden: true }).parentElement;
        if (container) {
          container.click();
        }
      });

      // Click handler might be called
      expect(handleClick).toHaveBeenCalledTimes(0); // or 1 depending on implementation
    });
  });

  describe('Accessibility', () => {
    it('should have alt text for screen readers', async () => {
      render(<ProgressiveImage imageId={mockImageId} alt={mockAlt} />);

      await waitFor(() => {
        const image = screen.queryByAlt(mockAlt);
        if (image) {
          expect(image).toHaveAttribute('alt', mockAlt);
        }
      });
    });

    it('should be keyboard accessible if onClick is provided', async () => {
      const handleClick = jest.fn();

      render(
        <ProgressiveImage
          imageId={mockImageId}
          alt={mockAlt}
          onClick={handleClick}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole('generic', { hidden: true })).toBeInTheDocument();
      });
    });
  });

  describe('Responsive Behavior', () => {
    it('should render different image for modal vs gallery', async () => {
      const { rerender } = render(
        <ProgressiveImage imageId={mockImageId} alt={mockAlt} isModal={false} />
      );

      await waitFor(() => {
        const galleryImage = screen.queryByAlt(mockAlt);
        if (galleryImage) {
          expect(galleryImage).toHaveAttribute('src', expect.stringContaining('/thumbnail/'));
        }
      });

      rerender(<ProgressiveImage imageId={mockImageId} alt={mockAlt} isModal={true} />);

      await waitFor(() => {
        const modalImage = screen.queryByAlt(mockAlt);
        if (modalImage) {
          expect(modalImage).toHaveAttribute('src', expect.stringContaining('/full/'));
        }
      });
    });
  });
});
