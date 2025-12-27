'use client';

import { useState } from 'react';
import { useDashboardStats, useModalityDistribution, useStudyTrends, useRecentActivity } from '@/lib/hooks/useStats';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Loader2, Users, Building2, Activity, FileImage, TrendingUp, Calendar } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

export default function DashboardPage() {
  const router = useRouter();
  const [trendDays, setTrendDays] = useState(30);
  const { data: stats, isLoading: statsLoading } = useDashboardStats();
  const { data: modality, isLoading: modalityLoading } = useModalityDistribution();
  const { data: trends, isLoading: trendsLoading } = useStudyTrends({ days: trendDays });
  const { data: activity, isLoading: activityLoading } = useRecentActivity(10);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Overview of your medical imaging platform
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Patients</CardTitle>
              <div className="p-2 rounded-lg bg-blue-100">
                <Users className="h-4 w-4 text-blue-600" />
              </div>
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">{stats?.total_patients?.toLocaleString() || 0}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Studies</CardTitle>
              <div className="p-2 rounded-lg bg-green-100">
                <Activity className="h-4 w-4 text-green-600" />
              </div>
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">{stats?.total_studies?.toLocaleString() || 0}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Images</CardTitle>
              <div className="p-2 rounded-lg bg-purple-100">
                <FileImage className="h-4 w-4 text-purple-600" />
              </div>
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">{stats?.total_images?.toLocaleString() || 0}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Hospitals</CardTitle>
              <div className="p-2 rounded-lg bg-orange-100">
                <Building2 className="h-4 w-4 text-orange-600" />
              </div>
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">{stats?.total_hospitals?.toLocaleString() || 0}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">New Patients (This Month)</CardTitle>
              <div className="p-2 rounded-lg bg-emerald-100">
                <TrendingUp className="h-4 w-4 text-emerald-600" />
              </div>
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">{stats?.new_patients_this_month?.toLocaleString() || 0}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Studies (This Week)</CardTitle>
              <div className="p-2 rounded-lg bg-pink-100">
                <Calendar className="h-4 w-4 text-pink-600" />
              </div>
            </CardHeader>
            <CardContent>
              {statsLoading ? (
                <Skeleton className="h-8 w-20" />
              ) : (
                <div className="text-2xl font-bold">{stats?.studies_this_week?.toLocaleString() || 0}</div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Study Trends Chart */}
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    Study Trends
                  </CardTitle>
                  <CardDescription>Number of studies over time</CardDescription>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setTrendDays(7)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      trendDays === 7 ? 'bg-primary text-white' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                  >
                    7 Days
                  </button>
                  <button
                    onClick={() => setTrendDays(30)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      trendDays === 30 ? 'bg-primary text-white' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                  >
                    30 Days
                  </button>
                  <button
                    onClick={() => setTrendDays(90)}
                    className={`px-3 py-1 rounded text-sm transition-colors ${
                      trendDays === 90 ? 'bg-primary text-white' : 'bg-gray-200 hover:bg-gray-300'
                    }`}
                  >
                    90 Days
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {trendsLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-[300px] w-full" />
                </div>
              ) : trends && trends.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={trends as any}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      height={60}
                    />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="#8884d8"
                      strokeWidth={2}
                      name="Studies"
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                  No trend data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* Modality Distribution Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Modality Distribution
              </CardTitle>
              <CardDescription>Studies by imaging modality type</CardDescription>
            </CardHeader>
            <CardContent>
              {modalityLoading ? (
                <div className="space-y-3">
                  <Skeleton className="h-[300px] w-full" />
                </div>
              ) : modality && modality.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={modality as any}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="modality" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="count" fill="#8884d8" name="Studies">
                      {modality.map((entry: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                  No modality data available
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5" />
                  Recent Activity
                </CardTitle>
                <CardDescription>Latest studies and updates</CardDescription>
              </div>
              <Button variant="outline" onClick={() => router.push('/studies')}>
                View All
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {activityLoading ? (
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-start justify-between p-4 rounded-lg border">
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center gap-2">
                        <Skeleton className="h-5 w-16" />
                        <Skeleton className="h-5 w-24" />
                      </div>
                      <Skeleton className="h-4 w-48" />
                      <Skeleton className="h-3 w-32" />
                    </div>
                    <div className="space-y-2">
                      <Skeleton className="h-5 w-20" />
                      <Skeleton className="h-3 w-24" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activity && activity.length > 0 ? (
              <div className="space-y-4">
                {activity.map((item: any) => (
                  <div
                    key={item.id}
                    className="flex items-start justify-between p-4 rounded-lg border hover:bg-muted/50 cursor-pointer transition-colors"
                    onClick={() => router.push(`/studies/${item.id}`)}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{item.modality}</Badge>
                        <span className="font-medium">{item.body_part}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Patient: {item.patient_name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.hospital_name}
                      </p>
                    </div>
                    <div className="text-right">
                      <Badge
                        variant={
                          item.status === 'completed'
                            ? 'default'
                            : item.status === 'pending'
                            ? 'secondary'
                            : 'outline'
                        }
                      >
                        {item.status}
                      </Badge>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(item.study_date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                No recent activity
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks and shortcuts</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Button onClick={() => router.push('/patients/new')} className="h-20">
                <Users className="mr-2 h-5 w-5" />
                Add Patient
              </Button>
              <Button onClick={() => router.push('/studies/new')} className="h-20">
                <FileImage className="mr-2 h-5 w-5" />
                Upload Study
              </Button>
              <Button onClick={() => router.push('/patients')} className="h-20" variant="outline">
                <Activity className="mr-2 h-5 w-5" />
                View All Patients
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
