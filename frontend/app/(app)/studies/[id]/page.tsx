'use client';

import { useState } from 'react';
import { useStudy, useStudyImages, useAddDiagnosis } from '@/lib/hooks/useStudies';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Loader2, ArrowLeft, User, Calendar, Building2, Activity, FileImage, FilePlus } from 'lucide-react';
import Image from 'next/image';

export default function StudyDetailPage() {
  const router = useRouter();
  const params = useParams();
  const studyId = Number(params.id);

  const { data: study, isLoading: studyLoading, error: studyError } = useStudy(studyId);
  const { data: images, isLoading: imagesLoading } = useStudyImages(studyId);
  const addDiagnosis = useAddDiagnosis(studyId);

  const [showDiagnosisForm, setShowDiagnosisForm] = useState(false);
  const [diagnosisText, setDiagnosisText] = useState('');
  const [selectedImage, setSelectedImage] = useState<any>(null);

  const handleAddDiagnosis = async () => {
    if (!diagnosisText.trim()) return;

    await addDiagnosis.mutateAsync({
      diagnosis: diagnosisText,
    });

    setDiagnosisText('');
    setShowDiagnosisForm(false);
  };

  if (studyLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (studyError || !study) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-[400px]">
          <CardHeader>
            <CardTitle className="text-red-600">Error</CardTitle>
            <CardDescription>Study not found</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push('/studies')}>Back to Studies</Button>
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
            <h1 className="text-3xl font-bold tracking-tight">
              {study.modality} Study - {study.body_part}
            </h1>
            <p className="text-muted-foreground">
              Study Date: {new Date(study.study_date).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Study Information */}
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Study Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3 text-sm">
                <User className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Patient</div>
                  <div className="text-muted-foreground">{study.patient_name}</div>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Hospital</div>
                  <div className="text-muted-foreground">{study.hospital_name}</div>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Study Date</div>
                  <div className="text-muted-foreground">
                    {new Date(study.study_date).toLocaleString()}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <FileImage className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Modality</div>
                  <Badge variant="outline">{study.modality}</Badge>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <div>
                  <div className="font-medium">Status</div>
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
                </div>
              </div>

              {study.description && (
                <div className="pt-4 border-t">
                  <div className="font-medium text-sm mb-2">Description</div>
                  <p className="text-sm text-muted-foreground">{study.description}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Diagnosis Section */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Diagnosis</CardTitle>
                  <CardDescription>Medical findings and diagnosis</CardDescription>
                </div>
                {!study.diagnosis && !showDiagnosisForm && (
                  <Button onClick={() => setShowDiagnosisForm(true)} size="sm">
                    <FilePlus className="mr-2 h-4 w-4" />
                    Add Diagnosis
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {study.diagnosis ? (
                <div className="space-y-2">
                  <p className="text-sm whitespace-pre-wrap">{study.diagnosis}</p>
                  {study.diagnosed_at && (
                    <p className="text-xs text-muted-foreground">
                      Diagnosed on {new Date(study.diagnosed_at).toLocaleString()}
                    </p>
                  )}
                </div>
              ) : showDiagnosisForm ? (
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="diagnosis">Diagnosis</Label>
                    <Textarea
                      id="diagnosis"
                      placeholder="Enter diagnosis findings..."
                      value={diagnosisText}
                      onChange={(e) => setDiagnosisText(e.target.value)}
                      rows={6}
                      className="mt-2"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={handleAddDiagnosis}
                      disabled={!diagnosisText.trim() || addDiagnosis.isPending}
                    >
                      {addDiagnosis.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Save Diagnosis
                    </Button>
                    <Button variant="outline" onClick={() => setShowDiagnosisForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No diagnosis available yet
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Images Gallery */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileImage className="h-5 w-5" />
              Medical Images
              {images && Array.isArray(images) ? <Badge variant="secondary">{images.length} images</Badge> : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {imagesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : images && images.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {images.map((image: any) => (
                  <div
                    key={image.id}
                    className="relative aspect-square bg-gray-100 rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-primary transition-all"
                    onClick={() => setSelectedImage(image)}
                  >
                    <Image
                      src={image.image_url}
                      alt={`Image ${image.instance_number}`}
                      fill
                      className="object-cover"
                      sizes="(max-width: 768px) 50vw, (max-width: 1200px) 33vw, 25vw"
                    />
                    <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-2">
                      Image {image.instance_number}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                No images available for this study
              </div>
            )}
          </CardContent>
        </Card>

        {/* Image Modal */}
        {selectedImage && (
          <div
            className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
            onClick={() => setSelectedImage(null)}
          >
            <div className="relative max-w-4xl max-h-[90vh] w-full h-full">
              <Image
                src={selectedImage.image_url}
                alt={`Image ${selectedImage.instance_number}`}
                fill
                className="object-contain"
                sizes="90vw"
              />
              <Button
                className="absolute top-4 right-4"
                variant="secondary"
                onClick={() => setSelectedImage(null)}
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
