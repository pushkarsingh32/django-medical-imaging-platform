'use client';

import { useState, useRef } from 'react';
import { useStudy, useStudyImages, useAddDiagnosis, useUpdateDiagnosis, studyKeys } from '@/lib/hooks/useStudies';
import { useRouter, useParams } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, ArrowLeft, User, Calendar, Building2, Activity, FileImage, Upload, FilePlus, Pencil } from 'lucide-react';
import Image from 'next/image';
import { studyService } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import ProgressiveImage from '@/components/ProgressiveImage';
import DicomMetadataViewer from '@/components/DicomMetadataViewer';

export default function StudyDetailPage() {
  const router = useRouter();
  const params = useParams();
  const studyId = Number(params.id);
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: study, isLoading: studyLoading, error: studyError } = useStudy(studyId);
  const { data: images, isLoading: imagesLoading } = useStudyImages(studyId);
  const addDiagnosis = useAddDiagnosis(studyId);
  const updateDiagnosis = useUpdateDiagnosis(studyId);

  // Debug: Log images data
  console.log('Images data:', images);
  console.log('Images loading:', imagesLoading);
  console.log('Is array?', Array.isArray(images));
  console.log('Images length:', images?.length);

  const [showDiagnosisForm, setShowDiagnosisForm] = useState(false);
  const [isEditingDiagnosis, setIsEditingDiagnosis] = useState(false);
  const [diagnosisData, setDiagnosisData] = useState({
    findings: '',
    impression: '',
    severity: 'normal',
    recommendations: '',
  });
  const [selectedImage, setSelectedImage] = useState<any>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleEditDiagnosis = () => {
    if (study?.diagnosis) {
      setDiagnosisData({
        findings: study.diagnosis.findings || '',
        impression: study.diagnosis.impression || '',
        severity: study.diagnosis.severity || 'normal',
        recommendations: study.diagnosis.recommendations || '',
      });
      setIsEditingDiagnosis(true);
      setShowDiagnosisForm(true);
    }
  };

  const handleSaveDiagnosis = async () => {
    if (!diagnosisData.findings.trim()) return;

    if (isEditingDiagnosis && study?.diagnosis?.id) {
      // Update existing diagnosis
      await updateDiagnosis.mutateAsync({
        diagnosisId: study.diagnosis.id,
        data: diagnosisData,
      });
    } else {
      // Add new diagnosis
      await addDiagnosis.mutateAsync(diagnosisData);
    }

    setDiagnosisData({
      findings: '',
      impression: '',
      severity: 'normal',
      recommendations: '',
    });
    setShowDiagnosisForm(false);
    setIsEditingDiagnosis(false);
  };

  const handleCancelDiagnosis = () => {
    setDiagnosisData({
      findings: '',
      impression: '',
      severity: 'normal',
      recommendations: '',
    });
    setShowDiagnosisForm(false);
    setIsEditingDiagnosis(false);
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsUploading(true);
    const formData = new FormData();

    Array.from(files).forEach((file) => {
      formData.append('images', file);
    });

    try {
      const response = await studyService.uploadImages(studyId, formData);
      // Refresh images
      queryClient.invalidateQueries({ queryKey: studyKeys.images(studyId) });
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Show appropriate message based on response
      if (response.skipped && response.skipped.length > 0) {
        // Some files were skipped (duplicates)
        if (response.images && response.images.length > 0) {
          toast.success(response.message || `${response.images.length} image(s) uploaded, ${response.skipped.length} skipped (duplicates)`);
        } else {
          toast.warning(response.message || `All ${response.skipped.length} image(s) skipped (duplicates already exist)`);
        }
      } else {
        // All images uploaded successfully
        toast.success(response.message || `${response.images?.length || files.length} image(s) uploaded successfully!`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Failed to upload images. Please try again.');
    } finally {
      setIsUploading(false);
    }
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
                {!showDiagnosisForm && (
                  study.diagnosis ? (
                    <Button onClick={handleEditDiagnosis} size="sm" variant="outline">
                      <Pencil className="mr-2 h-4 w-4" />
                      Edit Diagnosis
                    </Button>
                  ) : (
                    <Button onClick={() => setShowDiagnosisForm(true)} size="sm">
                      <FilePlus className="mr-2 h-4 w-4" />
                      Add Diagnosis
                    </Button>
                  )
                )}
              </div>
            </CardHeader>
            <CardContent>
              {study.diagnosis && !showDiagnosisForm ? (
                <div className="space-y-4">
                  {/* Severity Badge */}
                  {study.diagnosis.severity && (
                    <div>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        study.diagnosis.severity === 'severe' ? 'bg-red-100 text-red-800' :
                        study.diagnosis.severity === 'moderate' ? 'bg-yellow-100 text-yellow-800' :
                        study.diagnosis.severity === 'minor' ? 'bg-blue-100 text-blue-800' :
                        'bg-green-100 text-green-800'
                      }`}>
                        {study.diagnosis.severity.charAt(0).toUpperCase() + study.diagnosis.severity.slice(1)}
                      </span>
                    </div>
                  )}

                  {/* Findings */}
                  <div>
                    <h4 className="font-semibold text-sm mb-1">Findings</h4>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">{study.diagnosis.findings}</p>
                  </div>

                  {/* Impression */}
                  {study.diagnosis.impression && (
                    <div>
                      <h4 className="font-semibold text-sm mb-1">Impression</h4>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">{study.diagnosis.impression}</p>
                    </div>
                  )}

                  {/* Recommendations */}
                  {study.diagnosis.recommendations && (
                    <div>
                      <h4 className="font-semibold text-sm mb-1">Recommendations</h4>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">{study.diagnosis.recommendations}</p>
                    </div>
                  )}

                  {/* Footer */}
                  <div className="pt-2 border-t text-xs text-muted-foreground">
                    {study.diagnosis.radiologist_name && (
                      <p>Diagnosed by: {study.diagnosis.radiologist_name}</p>
                    )}
                    {study.diagnosis.diagnosed_at && (
                      <p>Date: {new Date(study.diagnosis.diagnosed_at).toLocaleString()}</p>
                    )}
                  </div>
                </div>
              ) : showDiagnosisForm ? (
                <div className="space-y-4">
                  {/* Severity Selection */}
                  <div>
                    <Label htmlFor="severity">Severity Level</Label>
                    <Select
                      value={diagnosisData.severity}
                      onValueChange={(value) => setDiagnosisData({ ...diagnosisData, severity: value })}
                    >
                      <SelectTrigger id="severity" className="mt-2">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="normal">Normal - No significant findings</SelectItem>
                        <SelectItem value="minor">Minor - Minor findings noted</SelectItem>
                        <SelectItem value="moderate">Moderate - Requires attention</SelectItem>
                        <SelectItem value="severe">Severe - Urgent attention required</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Findings */}
                  <div>
                    <Label htmlFor="findings">Findings *</Label>
                    <Textarea
                      id="findings"
                      placeholder="Enter detailed radiological findings..."
                      value={diagnosisData.findings}
                      onChange={(e) => setDiagnosisData({ ...diagnosisData, findings: e.target.value })}
                      rows={4}
                      className="mt-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Detailed description of what was observed in the imaging study
                    </p>
                  </div>

                  {/* Impression */}
                  <div>
                    <Label htmlFor="impression">Impression *</Label>
                    <Textarea
                      id="impression"
                      placeholder="Enter clinical impression and conclusion..."
                      value={diagnosisData.impression}
                      onChange={(e) => setDiagnosisData({ ...diagnosisData, impression: e.target.value })}
                      rows={3}
                      className="mt-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Summary, interpretation, and clinical significance
                    </p>
                  </div>

                  {/* Recommendations */}
                  <div>
                    <Label htmlFor="recommendations">Recommendations (Optional)</Label>
                    <Textarea
                      id="recommendations"
                      placeholder="Enter follow-up recommendations..."
                      value={diagnosisData.recommendations}
                      onChange={(e) => setDiagnosisData({ ...diagnosisData, recommendations: e.target.value })}
                      rows={2}
                      className="mt-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Follow-up procedures, additional tests, or treatment suggestions
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      onClick={handleSaveDiagnosis}
                      disabled={
                        !diagnosisData.findings.trim() ||
                        !diagnosisData.impression.trim() ||
                        addDiagnosis.isPending ||
                        updateDiagnosis.isPending
                      }
                    >
                      {(addDiagnosis.isPending || updateDiagnosis.isPending) && (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      )}
                      {isEditingDiagnosis ? 'Update Diagnosis' : 'Save Diagnosis'}
                    </Button>
                    <Button variant="outline" onClick={handleCancelDiagnosis}>
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
          {/* Hidden file input - always present */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.dcm,.dicom"
            onChange={handleImageUpload}
            className="hidden"
          />

          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <FileImage className="h-5 w-5" />
                Medical Images
                {images && Array.isArray(images) && images.length > 0 ? (
                  <Badge variant="secondary">{images.length} {images.length === 1 ? 'image' : 'images'}</Badge>
                ) : null}
              </CardTitle>
              {images && images.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  title="Upload more images"
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {imagesLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : images && images.length > 0 ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {images.map((image: any) => (
                    <div
                      key={image.id}
                      className="relative aspect-square rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-primary transition-all"
                    >
                      <ProgressiveImage
                        imageId={image.id}
                        alt={`Image ${image.instance_number}`}
                        fill={true}
                        sizes="(max-width: 768px) 50vw, (max-width: 1200px) 33vw, 25vw"
                        onClick={() => setSelectedImage(image)}
                        className="aspect-square"
                        isModal={false}
                      />
                      <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-2">
                        Image {image.instance_number}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <FileImage className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="mb-4">No images uploaded yet</p>
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="mr-2 h-4 w-4" />
                      Upload First Image
                    </>
                  )}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Image Modal with DICOM Metadata */}
        {selectedImage && (
          <div
            className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
            onClick={() => setSelectedImage(null)}
          >
            <div className="max-w-7xl w-full h-[90vh] flex gap-4" onClick={(e) => e.stopPropagation()}>
              {/* Image Viewer */}
              <div className="relative flex-1 bg-black rounded-lg overflow-hidden">
                <ProgressiveImage
                  imageId={selectedImage.id}
                  alt={`Image ${selectedImage.instance_number}`}
                  fill={true}
                  sizes="60vw"
                  thumbnailClassName="object-contain"
                  className="w-full h-full"
                  priority={true}
                  isModal={true}
                />
                <div className="absolute bottom-4 left-4 bg-black/60 text-white text-sm px-3 py-2 rounded">
                  Image {selectedImage.instance_number}
                </div>
              </div>

              {/* DICOM Metadata Panel */}
              <div className="w-96 bg-background rounded-lg overflow-y-auto">
                <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-background z-10">
                  <h3 className="font-semibold">Image Details</h3>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setSelectedImage(null)}
                  >
                    Close
                  </Button>
                </div>
                <div className="p-4">
                  <DicomMetadataViewer image={selectedImage} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
