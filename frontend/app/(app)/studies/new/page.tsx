'use client';

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { usePatients } from '@/lib/hooks/usePatients';
import { useHospitals } from '@/lib/hooks/useHospitals';
import { useCreateStudy } from '@/lib/hooks/useStudies';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Upload, X, ArrowLeft, FileImage } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const MODALITY_OPTIONS = [
  { value: 'CT', label: 'CT - Computed Tomography' },
  { value: 'MR', label: 'MRI - Magnetic Resonance Imaging' },
  { value: 'XR', label: 'X-Ray - Radiography' },
  { value: 'US', label: 'Ultrasound' },
  { value: 'MG', label: 'Mammography' },
  { value: 'PT', label: 'PET - Positron Emission Tomography' },
  { value: 'NM', label: 'Nuclear Medicine' },
];

const BODY_PART_OPTIONS = [
  'Head', 'Brain', 'Chest', 'Abdomen', 'Pelvis', 'Spine', 'Extremity',
  'Heart', 'Lung', 'Liver', 'Kidney', 'Breast', 'Other'
];

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
];

function NewStudyForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const patientIdParam = searchParams.get('patient');

  const { data: patientsData } = usePatients();
  const { data: hospitals } = useHospitals();
  const createStudy = useCreateStudy();

  const [formData, setFormData] = useState({
    patient: patientIdParam || '',
    hospital: '',
    modality: '',
    body_part: '',
    study_date: new Date().toISOString().split('T')[0],
    status: 'pending',
    description: '',
  });

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...files]);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.patient || !formData.hospital || !formData.modality || !formData.body_part) {
      alert('Please fill in all required fields');
      return;
    }

    const submitData = new FormData();
    Object.entries(formData).forEach(([key, value]) => {
      submitData.append(key, value);
    });

    selectedFiles.forEach((file, index) => {
      submitData.append(`images`, file);
    });

    try {
      const result = await createStudy.mutateAsync(submitData);
      router.push(`/studies/${result.id}`);
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload study. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Upload New Study</h1>
            <p className="text-muted-foreground">Add a new medical imaging study</p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <Card>
            <CardHeader>
              <CardTitle>Study Information</CardTitle>
              <CardDescription>Fill in the details for the new imaging study</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Patient Selection */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="patient">Patient *</Label>
                  <Select value={formData.patient} onValueChange={(value) => handleInputChange('patient', value)}>
                    <SelectTrigger id="patient">
                      <SelectValue placeholder="Select patient" />
                    </SelectTrigger>
                    <SelectContent>
                      {patientsData?.results.map((patient) => (
                        <SelectItem key={patient.id} value={patient.id.toString()}>
                          {patient.full_name} - {patient.medical_record_number}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="hospital">Hospital *</Label>
                  <Select value={formData.hospital} onValueChange={(value) => handleInputChange('hospital', value)}>
                    <SelectTrigger id="hospital">
                      <SelectValue placeholder="Select hospital" />
                    </SelectTrigger>
                    <SelectContent>
                      {hospitals?.results?.map((hospital) => (
                        <SelectItem key={hospital.id} value={hospital.id.toString()}>
                          {hospital.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Modality and Body Part */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="modality">Modality *</Label>
                  <Select value={formData.modality} onValueChange={(value) => handleInputChange('modality', value)}>
                    <SelectTrigger id="modality">
                      <SelectValue placeholder="Select modality" />
                    </SelectTrigger>
                    <SelectContent>
                      {MODALITY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="body_part">Body Part *</Label>
                  <Select value={formData.body_part} onValueChange={(value) => handleInputChange('body_part', value)}>
                    <SelectTrigger id="body_part">
                      <SelectValue placeholder="Select body part" />
                    </SelectTrigger>
                    <SelectContent>
                      {BODY_PART_OPTIONS.map((part) => (
                        <SelectItem key={part} value={part}>
                          {part}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Study Date and Status */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="study_date">Study Date *</Label>
                  <Input
                    id="study_date"
                    type="date"
                    value={formData.study_date}
                    onChange={(e) => handleInputChange('study_date', e.target.value)}
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="status">Status</Label>
                  <Select value={formData.status} onValueChange={(value) => handleInputChange('status', value)}>
                    <SelectTrigger id="status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Description */}
              <div>
                <Label htmlFor="description">Description (Optional)</Label>
                <Textarea
                  id="description"
                  placeholder="Enter study description or notes..."
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  rows={4}
                />
              </div>

              {/* File Upload */}
              <div className="space-y-4">
                <Label>Medical Images (DICOM files)</Label>
                <div className="border-2 border-dashed rounded-lg p-8 text-center">
                  <FileImage className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      Drag and drop DICOM files here, or click to browse
                    </p>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => document.getElementById('file-input')?.click()}
                    >
                      <Upload className="mr-2 h-4 w-4" />
                      Select Files
                    </Button>
                  </div>
                  <input
                    id="file-input"
                    type="file"
                    multiple
                    accept=".dcm,.dicom,image/*"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </div>

                {/* Selected Files */}
                {selectedFiles.length > 0 && (
                  <div className="space-y-2">
                    <Label>Selected Files ({selectedFiles.length})</Label>
                    <div className="max-h-48 overflow-y-auto space-y-2">
                      {selectedFiles.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-3 bg-muted rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <FileImage className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium">{file.name}</p>
                              <p className="text-xs text-muted-foreground">
                                {(file.size / 1024).toFixed(2)} KB
                              </p>
                            </div>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={() => removeFile(index)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex gap-4 mt-6">
            <Button type="submit" size="lg" disabled={createStudy.isPending}>
              {createStudy.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Upload Study
            </Button>
            <Button type="button" variant="outline" size="lg" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function NewStudyPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><div className="text-muted-foreground">Loading...</div></div>}>
      <NewStudyForm />
    </Suspense>
  );
}
