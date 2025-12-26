'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { Loader2 } from 'lucide-react';

interface ProgressiveImageProps {
  imageId: number;
  alt: string;
  className?: string;
  thumbnailClassName?: string;
  fill?: boolean;
  sizes?: string;
  onClick?: () => void;
  priority?: boolean;
  isModal?: boolean; // NEW: indicates if this is being used in modal
}

/**
 * Progressive Image component - Simplified 2-tier loading:
 * 1. Gallery: Always show thumbnail (200x200, fast)
 * 2. Modal: Always show full quality
 *
 * This provides fast gallery browsing while preserving full quality for detailed viewing.
 */
export default function ProgressiveImage({
  imageId,
  alt,
  className = '',
  thumbnailClassName = '',
  fill = false,
  sizes,
  onClick,
  priority = false,
  isModal = false, // NEW
}: ProgressiveImageProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

  // Image URLs - only 2 versions
  const thumbnailUrl = `${API_BASE}/images/${imageId}/thumbnail/`;
  const fullUrl = `${API_BASE}/images/${imageId}/full/`;

  // Use thumbnail for gallery, full for modal
  const imageSrc = isModal ? fullUrl : thumbnailUrl;

  useEffect(() => {
    setLoading(true);
    setError(false);

    // Preload the appropriate image
    const img = new window.Image();
    img.onload = () => setLoading(false);
    img.onerror = () => {
      setError(true);
      setLoading(false);
    };
    img.src = imageSrc;
  }, [imageSrc]);

  if (error) {
    return (
      <div className={`flex items-center justify-center bg-gray-100 ${className}`}>
        <div className="text-center text-muted-foreground">
          <p className="text-sm">Failed to load image</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={`flex items-center justify-center bg-gray-100 ${className}`}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className={`relative ${className}`} onClick={onClick}>
      <Image
        src={imageSrc}
        alt={alt}
        fill={fill}
        sizes={sizes}
        className={`object-cover ${thumbnailClassName}`}
        priority={priority}
        unoptimized
      />
    </div>
  );
}
