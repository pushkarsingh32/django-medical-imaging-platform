import React from 'react';

/**
 * A simple component that renders three bouncing dots.
 */
export default function LoadingDots({ className = '' }: { className?: string }) {
  return (
    <div className={`flex space-x-1 items-center justify-center ${className}`}>
      <span className="loading-dot dot-1"></span>
      <span className="loading-dot dot-2"></span>
      <span className="loading-dot dot-3"></span>
    </div>
  );
}
