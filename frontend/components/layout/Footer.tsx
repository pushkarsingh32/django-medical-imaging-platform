import Link from 'next/link';
import { Activity, Mail, MapPin, Phone, FileCode } from 'lucide-react';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  // Get API base URL from environment variable
  // Remove '/api' suffix to get the server base URL, then add '/api/docs/'
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
  const serverBaseUrl = apiBaseUrl.replace(/\/api\/?$/, ''); // Remove '/api' or '/api/' from end
  const apiDocsUrl = `${serverBaseUrl}/api/docs/`;

  return (
    <footer className="bg-gray-900 text-gray-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Activity className="h-8 w-8 text-primary" />
              <span className="text-xl font-bold text-white">MediScan</span>
            </div>
            <p className="text-sm">
              Advanced medical imaging platform for healthcare professionals.
              Streamline your diagnostic workflow.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-white font-semibold mb-4">Quick Links</h3>
            <ul className="space-y-2">
              <li>
                <Link href="/" className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors">
                  Home
                </Link>
              </li>
              <li>
                <Link href="/about" className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors">
                  About Us
                </Link>
              </li>
              <li>
                <Link href="/contact" className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors">
                  Contact
                </Link>
              </li>
              <li>
                <Link href="/auth/login" className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors">
                  Login
                </Link>
              </li>
              <li>
                <a
                  href={apiDocsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors inline-flex items-center gap-1"
                >
                  <FileCode className="h-3 w-3" />
                  API Docs
                </a>
              </li>
            </ul>
          </div>

          {/* Services */}
          <div>
            <h3 className="text-white font-semibold mb-4">Services</h3>
            <ul className="space-y-2">
              <li className="text-sm">Patient Management</li>
              <li className="text-sm">DICOM Image Storage</li>
              <li className="text-sm">Study Analysis</li>
              <li className="text-sm">Diagnosis Reporting</li>
            </ul>
          </div>

          {/* Contact Info */}
          <div>
            <h3 className="text-white font-semibold mb-4">Contact Us</h3>
            <ul className="space-y-3">
              <li className="flex items-start gap-2 text-sm">
                <MapPin className="h-4 w-4 mt-1 flex-shrink-0" />
                <span>123 Medical Center Dr, Healthcare City, HC 12345</span>
              </li>
              <li className="flex items-center gap-2 text-sm">
                <Phone className="h-4 w-4 flex-shrink-0" />
                <span>+1 (555) 123-4567</span>
              </li>
              <li className="flex items-center gap-2 text-sm">
                <Mail className="h-4 w-4 flex-shrink-0" />
                <span>info@mediscan.com</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 pt-8 border-t border-gray-800">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm">
              &copy; {currentYear} MediScan. All rights reserved.
            </p>
            <div className="flex gap-6">
              <Link href="#" className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors">
                Privacy Policy
              </Link>
              <Link href="#" className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors">
                Terms of Service
              </Link>
              <a
                href={apiDocsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-300 hover:text-white hover:underline cursor-pointer transition-colors"
              >
                API Documentation
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
