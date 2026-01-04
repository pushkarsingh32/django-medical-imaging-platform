'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Settings, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api';

interface AuditLog {
  id: number;
  action: string;
  user_email: string;
  model_name: string;
  object_id: number | null;
  timestamp: string;
  ip_address: string;
  changes: any;
}

export default function AuditLogsPage() {
  const { isAdmin, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  // Redirect non-admin users
  useEffect(() => {
    if (!authLoading && !isAdmin) {
      router.push('/dashboard');
    }
  }, [isAdmin, authLoading, router]);

  // Fetch audit logs
  useEffect(() => {
    if (!isAdmin) return;

    const fetchLogs = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get(`/audit-logs/?page=${page}`);
        setLogs(response.results || []);
      } catch (err: any) {
        setError(err.message || 'Failed to load audit logs');
      } finally {
        setIsLoading(false);
      }
    };

    fetchLogs();
  }, [isAdmin, page]);

  if (authLoading || (isLoading && logs.length === 0)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
          <p className="mt-4 text-muted-foreground">Loading audit logs...</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return null; // Will redirect
  }

  const getActionBadgeColor = (action: string) => {
    switch (action) {
      case 'create':
        return 'default';
      case 'update':
        return 'secondary';
      case 'delete':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Settings className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Audit Logs</h1>
            <p className="text-muted-foreground mt-1">
              Track system activity and changes
            </p>
          </div>
        </div>

        {/* Logs Table */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>System-wide audit trail of user actions</CardDescription>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="text-center py-12">
                <p className="text-red-600">{error}</p>
                <Button
                  variant="outline"
                  onClick={() => window.location.reload()}
                  className="mt-4"
                >
                  Retry
                </Button>
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                No audit logs found
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-6">Timestamp</TableHead>
                      <TableHead>User</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Object ID</TableHead>
                      <TableHead>IP Address</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="pl-6 font-mono text-xs">
                          {new Date(log.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-sm">
                          {log.user_email || 'System'}
                        </TableCell>
                        <TableCell>
                          <Badge variant={getActionBadgeColor(log.action)}>
                            {log.action}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{log.model_name}</TableCell>
                        <TableCell className="text-sm font-mono">
                          {log.object_id || '-'}
                        </TableCell>
                        <TableCell className="text-sm font-mono">
                          {log.ip_address || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {/* Pagination */}
            {logs.length > 0 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  Page {page}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={logs.length < 20}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
