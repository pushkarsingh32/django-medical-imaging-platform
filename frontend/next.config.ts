import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'medical-imaging-dev-pushkar.s3.amazonaws.com',
        pathname: '/dicom_image/**',
      },
    ],
  },
};

export default nextConfig;
