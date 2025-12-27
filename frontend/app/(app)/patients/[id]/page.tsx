'use client';

import { useState, useEffect } from 'react';
import { usePatient } from '@/lib/hooks/usePatients';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Loader2, ArrowLeft, User, Phone, Mail, MapPin, Calendar, Building2, Pencil, FileText, Download, Eye } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { patientService, studyService } from '@/lib/api';
import { toast } from 'sonner';
import type { PatientReport } from '@/lib/api/types';

export default function PatientDetailPage() {
  const router = useRouter();
  const params = useParams();
  const patientId = Number(params.id);

  const { data: patient, isLoading, error } = usePatient(patientId);
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
  const [pdfProgress, setPdfProgress] = useState(0);
  const [reports, setReports] = useState<PatientReport[]>([]);
  const [loadingReports, setLoadingReports] = useState(false);

  // Fetch reports on mount
  useEffect(() => {
    const fetchReports = async () => {
      if (!patientId) return;
      setLoadingReports(true);
      try {
        const data = await patientService.getReports(patientId);
        setReports(data);
      } catch (err) {
        console.error('Failed to fetch reports:', err);
      } finally {
        setLoadingReports(false);
      }
    };

    fetchReports();
  }, [patientId]);

  const handleGeneratePDF = async () => {
    setIsGeneratingPDF(true);
    setPdfProgress(0);

    try {
      // Trigger PDF generation
      const response = await patientService.generateReport(patientId);

      toast.info('Generating PDF report...');

      // Poll for task status
      const pollInterval = setInterval(async () => {
        try {
          const taskStatus = await studyService.getTaskStatus(response.task_id);
          setPdfProgress(taskStatus.progress_percentage);

          if (taskStatus.status === 'completed') {
            clearInterval(pollInterval);
            setIsGeneratingPDF(false);
            setPdfProgress(0);

            // Refresh reports list
            const data = await patientService.getReports(patientId);
            setReports(data);

            toast.success('PDF report generated successfully!');
          } else if (taskStatus.status === 'failed') {
            clearInterval(pollInterval);
            setIsGeneratingPDF(false);
            setPdfProgress(0);
            toast.error(taskStatus.error_message || 'Failed to generate PDF. Please try again.');
          }
        } catch (pollError) {
          console.error('Poll error:', pollError);
        }
      }, 2000); // Poll every 2 seconds

      // Timeout after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (isGeneratingPDF) {
          setIsGeneratingPDF(false);
          toast.error('PDF generation timeout. Please try again.');
        }
      }, 2 * 60 * 1000);

    } catch (error) {
      console.error('PDF generation error:', error);
      toast.error('Failed to generate PDF. Please try again.');
      setIsGeneratingPDF(false);
      setPdfProgress(0);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-[400px]">
          <CardHeader>
            <CardTitle className="text-red-600">Error</CardTitle>
            <CardDescription>Patient not found</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push('/patients')}>Back to Patients</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{patient.full_name}</h1>
            <p className="text-muted-foreground">MRN: {patient.medical_record_number}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Patient Information */}
          <Card className="lg:col-span-1 group relative">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Patient Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push(`/patients/${patientId}/edit`)}
                className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Pencil className="h-4 w-4 mr-2" />
                Edit
              </Button>
              <div className="flex items-center gap-3 text-sm">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Date of Birth</div>
                  <div className="text-muted-foreground">
                    {new Date(patient.date_of_birth).toLocaleDateString()} ({patient.age} years)
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <User className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Gender</div>
                  <Badge variant={patient.gender === 'M' ? 'default' : 'secondary'}>
                    {patient.gender === 'M' ? 'Male' : patient.gender === 'F' ? 'Female' : 'Other'}
                  </Badge>
                </div>
              </div>

              {patient.phone && (
                <div className="flex items-center gap-3 text-sm">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <div className="font-medium">Phone</div>
                    <div className="text-muted-foreground">{patient.phone}</div>
                  </div>
                </div>
              )}

              {patient.email && (
                <div className="flex items-center gap-3 text-sm">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <div className="font-medium">Email</div>
                    <div className="text-muted-foreground">{patient.email}</div>
                  </div>
                </div>
              )}

              {patient.address && (
                <div className="flex items-center gap-3 text-sm">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <div className="font-medium">Address</div>
                    <div className="text-muted-foreground">{patient.address}</div>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3 text-sm">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Hospital</div>
                  <div className="text-muted-foreground">{patient.hospital_name}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Imaging Studies */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Imaging Studies</CardTitle>
                  <CardDescription>Total: {patient.total_studies} studies</CardDescription>
                </div>
                <Button onClick={() => router.push(`/studies/new?patient=${patientId}`)}>
                  Add Study
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {patient.recent_studies && patient.recent_studies.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Modality</TableHead>
                      <TableHead>Body Part</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Images</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {patient.recent_studies.map((study: any) => (
                      <TableRow
                        key={study.id}
                        onClick={() => router.push(`/studies/${study.id}`)}
                        className="cursor-pointer hover:bg-muted/50"
                      >
                        <TableCell>
                          {new Date(study.study_date).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{study.modality}</Badge>
                        </TableCell>
                        <TableCell>{study.body_part}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              study.status === 'completed'
                                ? 'default'
                                : study.status === 'pending'
                                ? 'secondary'
                                : 'outline'
                            }
                          >
                            {study.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{study.image_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  No imaging studies found
                </div>
              )}
            </CardContent>
          </Card>

          {/* Generated Reports Section */}
          <Card className="lg:col-span-3">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Generated Reports
                    {reports.length > 0 && (
                      <Badge variant="secondary">{reports.length} {reports.length === 1 ? 'report' : 'reports'}</Badge>
                    )}
                  </CardTitle>
                  <CardDescription>PDF reports generated for this patient</CardDescription>
                </div>
                <Button
                  onClick={handleGeneratePDF}
                  disabled={isGeneratingPDF}
                  className="gap-2"
                >
                  {isGeneratingPDF ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Generating... {pdfProgress}%
                    </>
                  ) : (
                    <>
                      <FileText className="h-4 w-4" />
                      Generate Report
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingReports ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : reports.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Filename</TableHead>
                      <TableHead>Generated</TableHead>
                      <TableHead>Studies</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Generated By</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reports.map((report) => (
                      <TableRow key={report.id}>
                        <TableCell className="font-medium">{report.filename}</TableCell>
                        <TableCell>{new Date(report.generated_at).toLocaleString()}</TableCell>
                        <TableCell>{report.studies_count}</TableCell>
                        <TableCell>{report.file_size_mb}</TableCell>
                        <TableCell>{report.generated_by_name || 'System'}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => window.open(report.file_url, '_blank')}
                          >
                            <Eye className="h-4 w-4 mr-1" />
                            View
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No reports generated yet</p>
                  <p className="text-sm mt-2">Click "Generate Report" to create the first PDF report</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
