'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ShieldCheck, Users, Activity, Database, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function AdminPanel() {
  const { isAdmin, isLoading, user } = useAuth();
  const router = useRouter();

  // Redirect non-admin users
  useEffect(() => {
    if (!isLoading && !isAdmin) {
      router.push('/dashboard');
    }
  }, [isAdmin, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return null; // Will redirect
  }

  const adminFeatures = [
    {
      title: 'User Management',
      description: 'Manage user accounts, roles, and permissions',
      icon: Users,
      href: '#',  // Not implemented yet
      available: true,
      disabled: true,
    },
    {
      title: 'System Settings',
      description: 'Configure system-wide settings and preferences',
      icon: Settings,
      href: '#',  // Not implemented yet
      available: true,
      disabled: true,
    },
    {
      title: 'Database Admin',
      description: 'Direct access to Django admin interface',
      icon: Database,
      href: 'http://localhost:8000/admin/',
      external: true,
      available: user?.is_staff,
      disabled: false,
    },
    {
      title: 'Audit Logs',
      description: 'View system activity and audit trails',
      icon: Activity,
      href: '/audit-logs',
      available: true,
      disabled: false,
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <ShieldCheck className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Admin Panel</h1>
            <p className="text-muted-foreground mt-1">
              System administration and management
            </p>
          </div>
        </div>

        {/* User Info */}
        <Card>
          <CardHeader>
            <CardTitle>Your Admin Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Email:</span>
              <span className="text-sm text-muted-foreground">{user?.email}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Role:</span>
              <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full font-medium">
                {user?.is_superuser ? 'Superuser' : user?.is_staff ? 'Staff' : 'Unknown'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Staff Status:</span>
              <span className="text-sm text-muted-foreground">
                {user?.is_staff ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Superuser:</span>
              <span className="text-sm text-muted-foreground">
                {user?.is_superuser ? 'Yes' : 'No'}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Admin Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {adminFeatures.map((feature) => {
            const Icon = feature.icon;

            if (!feature.available) {
              return null;
            }

            return (
              <Card key={feature.title} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-lg">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{feature.title}</CardTitle>
                      <CardDescription className="text-sm">
                        {feature.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <Button
                    variant="outline"
                    className="w-full"
                    disabled={feature.disabled}
                    onClick={() => {
                      if (feature.disabled) return;
                      if (feature.external) {
                        window.open(feature.href, '_blank');
                      } else if (feature.href !== '#') {
                        router.push(feature.href);
                      }
                    }}
                  >
                    {feature.disabled
                      ? 'Coming Soon'
                      : feature.external
                      ? 'Open in New Tab'
                      : 'Access'}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
