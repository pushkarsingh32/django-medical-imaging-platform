'use client';

import { useState } from 'react';
import { usePatients } from '@/lib/hooks/usePatients';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Plus, Search } from 'lucide-react';

export default function PatientsPage() {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [gender, setGender] = useState<string>('');
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = usePatients({ search, gender, page });

  const handleRowClick = (patientId: number) => {
    router.push(`/patients/${patientId}`);
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-[400px]">
          <CardHeader>
            <CardTitle className="text-red-600">Error</CardTitle>
            <CardDescription>Failed to load patients</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Patients</h1>
            <p className="text-muted-foreground mt-1">
              Manage patient records and medical history
            </p>
          </div>
          <Button onClick={() => router.push('/patients/new')} size="lg">
            <Plus className="mr-2 h-4 w-4" />
            Add Patient
          </Button>
        </div>

        {/* Filters Card */}
        <Card>
          <CardHeader>
            <CardTitle>Search & Filter</CardTitle>
            <CardDescription>Find patients by name, MRN, or demographic filters</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Search Input */}
              <div className="relative">
                <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name or MRN..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>

              {/* Gender Filter */}
              <Select value={gender} onValueChange={setGender}>
                <SelectTrigger>
                  <SelectValue placeholder="All Genders" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Genders</SelectItem>
                  <SelectItem value="M">Male</SelectItem>
                  <SelectItem value="F">Female</SelectItem>
                  <SelectItem value="O">Other</SelectItem>
                </SelectContent>
              </Select>

              {/* Clear Filters */}
              {(search || gender) && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearch('');
                    setGender('');
                    setPage(1);
                  }}
                >
                  Clear Filters
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Patients Table */}
        <Card>
          <CardContent className="p-0">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>MRN</TableHead>
                      <TableHead>Patient Name</TableHead>
                      <TableHead>Age</TableHead>
                      <TableHead>Gender</TableHead>
                      <TableHead>Hospital</TableHead>
                      <TableHead>Contact</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data?.results.map((patient) => (
                      <TableRow
                        key={patient.id}
                        onClick={() => handleRowClick(patient.id)}
                        className="cursor-pointer hover:bg-muted/50"
                      >
                        <TableCell className="font-medium">
                          {patient.medical_record_number}
                        </TableCell>
                        <TableCell>
                          <div>
                            <div className="font-medium">{patient.full_name}</div>
                            <div className="text-sm text-muted-foreground">
                              DOB: {new Date(patient.date_of_birth).toLocaleDateString()}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>{patient.age} years</TableCell>
                        <TableCell>
                          <Badge variant={patient.gender === 'M' ? 'default' : 'secondary'}>
                            {patient.gender === 'M' ? 'Male' : patient.gender === 'F' ? 'Female' : 'Other'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">{patient.hospital_name}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {patient.phone || patient.email || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                    {data?.results.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                          No patients found
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>

                {/* Pagination */}
                {data && data.count > 20 && (
                  <div className="flex items-center justify-between border-t px-6 py-4">
                    <div className="text-sm text-muted-foreground">
                      Showing{' '}
                      <span className="font-medium text-foreground">
                        {(page - 1) * 20 + 1}
                      </span>{' '}
                      to{' '}
                      <span className="font-medium text-foreground">
                        {Math.min(page * 20, data.count)}
                      </span>{' '}
                      of <span className="font-medium text-foreground">{data.count}</span> results
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={!data.previous}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => p + 1)}
                        disabled={!data.next}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
