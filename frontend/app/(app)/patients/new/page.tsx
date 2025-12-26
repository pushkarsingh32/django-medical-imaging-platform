'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { format } from 'date-fns';
import { useHospitals } from '@/lib/hooks/useHospitals';
import { useCreatePatient } from '@/lib/hooks/usePatients';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, ArrowLeft, UserPlus, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import type { CreatePatientData } from '@/lib/api/types';

export default function NewPatientPage() {
  const router = useRouter();
  const { data: hospitalsData, isLoading: hospitalsLoading } = useHospitals();
  const createPatient = useCreatePatient();

  const [formData, setFormData] = useState({
    medical_record_number: '',
    first_name: '',
    last_name: '',
    gender: '',
    phone: '',
    email: '',
    address: '',
    hospital: '',
  });

  const [dateOfBirth, setDateOfBirth] = useState<Date>();
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error for this field when user starts typing
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.medical_record_number.trim()) {
      newErrors.medical_record_number = 'Medical Record Number is required';
    }
    if (!formData.first_name.trim()) {
      newErrors.first_name = 'First name is required';
    }
    if (!formData.last_name.trim()) {
      newErrors.last_name = 'Last name is required';
    }
    if (!dateOfBirth) {
      newErrors.date_of_birth = 'Date of birth is required';
    }
    if (!formData.gender) {
      newErrors.gender = 'Gender is required';
    }
    if (!formData.hospital) {
      newErrors.hospital = 'Hospital is required';
    }

    // Validate email format if provided
    if (formData.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Invalid email format';
    }

    // Validate phone format if provided (basic validation)
    if (formData.phone && !/^[\d\s\-\+\(\)]+$/.test(formData.phone)) {
      newErrors.phone = 'Invalid phone number format';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    // Parse hospital ID and validate it's a valid number
    const hospitalId = parseInt(formData.hospital);
    if (isNaN(hospitalId)) {
      setErrors({ hospital: 'Please select a valid hospital' });
      return;
    }

    const submitData: CreatePatientData = {
      medical_record_number: formData.medical_record_number,
      first_name: formData.first_name,
      last_name: formData.last_name,
      date_of_birth: dateOfBirth ? format(dateOfBirth, 'yyyy-MM-dd') : '',
      gender: formData.gender as 'M' | 'F' | 'O',
      hospital: hospitalId,
      phone: formData.phone || undefined,
      email: formData.email || undefined,
      address: formData.address || undefined,
    };

    console.log('Submitting patient data:', submitData); // Debug log

    try {
      const result = await createPatient.mutateAsync(submitData);
      toast.success('Patient created successfully!');
      router.push(`/patients/${result.id}`);
    } catch (error: any) {
      console.error('Create patient error:', error);

      // Handle validation errors from backend
      if (error.response?.data) {
        const backendErrors: Record<string, string> = {};
        Object.entries(error.response.data).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            backendErrors[key] = value[0];
          } else {
            backendErrors[key] = String(value);
          }
        });
        setErrors(backendErrors);
      } else {
        toast.error('Failed to create patient. Please try again.');
      }
    }
  };

  const hospitals = Array.isArray(hospitalsData) ? hospitalsData : hospitalsData?.results || [];

  // Debug: Log hospitals data
  console.log('Hospitals data:', hospitalsData);
  console.log('Parsed hospitals:', hospitals);
  console.log('Current form data:', formData);

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Add New Patient</h1>
            <p className="text-muted-foreground">Create a new patient record</p>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <Card>
            <CardHeader>
              <CardTitle>Patient Information</CardTitle>
              <CardDescription>Enter the patient's personal and medical information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* MRN and Hospital */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="medical_record_number">Medical Record Number *</Label>
                  <Input
                    id="medical_record_number"
                    placeholder="12345"
                    value={formData.medical_record_number.replace('MRN-', '')}
                    onChange={(e) => {
                      const value = e.target.value.replace(/[^0-9]/g, '');
                      handleInputChange('medical_record_number', value ? `MRN-${value}` : '');
                    }}
                    className={errors.medical_record_number ? 'border-red-500' : ''}
                  />
                  {formData.medical_record_number && (
                    <p className="text-xs text-muted-foreground">Preview: {formData.medical_record_number}</p>
                  )}
                  {errors.medical_record_number && (
                    <p className="text-sm text-red-500 mt-1">{errors.medical_record_number}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="hospital">Hospital *</Label>
                  <Select
                    value={formData.hospital}
                    onValueChange={(value) => handleInputChange('hospital', value)}
                    disabled={hospitalsLoading}
                  >
                    <SelectTrigger id="hospital" className={errors.hospital ? 'border-red-500' : ''}>
                      <SelectValue placeholder={hospitalsLoading ? "Loading hospitals..." : "Select hospital"} />
                    </SelectTrigger>
                    <SelectContent>
                      {hospitals.length === 0 ? (
                        <div className="p-2 text-sm text-muted-foreground text-center">
                          No hospitals available
                        </div>
                      ) : (
                        hospitals.map((hospital: any) => (
                          <SelectItem key={hospital.id} value={hospital.id.toString()}>
                            {hospital.name}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                  {errors.hospital && (
                    <p className="text-sm text-red-500 mt-1">{errors.hospital}</p>
                  )}
                </div>
              </div>

              {/* Name Fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name">First Name *</Label>
                  <Input
                    id="first_name"
                    placeholder="John"
                    value={formData.first_name}
                    onChange={(e) => handleInputChange('first_name', e.target.value)}
                    className={errors.first_name ? 'border-red-500' : ''}
                  />
                  {errors.first_name && (
                    <p className="text-sm text-red-500 mt-1">{errors.first_name}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="last_name">Last Name *</Label>
                  <Input
                    id="last_name"
                    placeholder="Doe"
                    value={formData.last_name}
                    onChange={(e) => handleInputChange('last_name', e.target.value)}
                    className={errors.last_name ? 'border-red-500' : ''}
                  />
                  {errors.last_name && (
                    <p className="text-sm text-red-500 mt-1">{errors.last_name}</p>
                  )}
                </div>
              </div>

              {/* DOB and Gender */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="date_of_birth">Date of Birth *</Label>
                  <Popover open={isCalendarOpen} onOpenChange={setIsCalendarOpen}>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        id="date_of_birth"
                        className={cn(
                          'w-full justify-between text-left font-normal',
                          !dateOfBirth && 'text-muted-foreground',
                          errors.date_of_birth && 'border-red-500'
                        )}
                      >
                        {dateOfBirth ? dateOfBirth.toLocaleDateString() : 'Select date'}
                        <ChevronDown className="h-4 w-4 opacity-50" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto overflow-hidden p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={dateOfBirth}
                        captionLayout="dropdown"
                        onSelect={(date) => {
                          setDateOfBirth(date);
                          setIsCalendarOpen(false);
                          if (errors.date_of_birth) {
                            setErrors((prev) => {
                              const newErrors = { ...prev };
                              delete newErrors.date_of_birth;
                              return newErrors;
                            });
                          }
                        }}
                        disabled={(date) => date > new Date() || date < new Date('1900-01-01')}
                        fromYear={1900}
                        toYear={new Date().getFullYear()}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                  {errors.date_of_birth && (
                    <p className="text-sm text-red-500 mt-1">{errors.date_of_birth}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="gender">Gender *</Label>
                  <Select
                    value={formData.gender}
                    onValueChange={(value) => handleInputChange('gender', value)}
                  >
                    <SelectTrigger id="gender" className={errors.gender ? 'border-red-500' : ''}>
                      <SelectValue placeholder="Select gender" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="M">Male</SelectItem>
                      <SelectItem value="F">Female</SelectItem>
                      <SelectItem value="O">Other</SelectItem>
                    </SelectContent>
                  </Select>
                  {errors.gender && (
                    <p className="text-sm text-red-500 mt-1">{errors.gender}</p>
                  )}
                </div>
              </div>

              {/* Contact Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    type="tel"
                    placeholder="+1 (555) 123-4567"
                    value={formData.phone}
                    onChange={(e) => handleInputChange('phone', e.target.value)}
                    className={errors.phone ? 'border-red-500' : ''}
                  />
                  {errors.phone && (
                    <p className="text-sm text-red-500 mt-1">{errors.phone}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="john.doe@example.com"
                    value={formData.email}
                    onChange={(e) => handleInputChange('email', e.target.value)}
                    className={errors.email ? 'border-red-500' : ''}
                  />
                  {errors.email && (
                    <p className="text-sm text-red-500 mt-1">{errors.email}</p>
                  )}
                </div>
              </div>

              {/* Address */}
              <div className="space-y-2">
                <Label htmlFor="address">Address</Label>
                <Textarea
                  id="address"
                  placeholder="Enter patient's full address"
                  value={formData.address}
                  onChange={(e) => handleInputChange('address', e.target.value)}
                  rows={3}
                  className={errors.address ? 'border-red-500' : ''}
                />
                {errors.address && (
                  <p className="text-sm text-red-500 mt-1">{errors.address}</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="mt-6">
            <Button type="submit" size="lg" disabled={createPatient.isPending}>
              {createPatient.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating Patient...
                </>
              ) : (
                <>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Create Patient
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
