import { DicomImage } from '@/lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface DicomMetadataViewerProps {
  image: DicomImage;
}

export default function DicomMetadataViewer({ image }: DicomMetadataViewerProps) {
  if (!image.is_dicom) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Image Information</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">This is a regular image file, not a DICOM file.</p>
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="font-medium">File Size:</span>
              <span>{(image.file_size_bytes / 1024).toFixed(2)} KB</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="font-medium">Uploaded:</span>
              <span>{new Date(image.uploaded_at).toLocaleString()}</span>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>DICOM Metadata</CardTitle>
          <Badge variant="default">DICOM File</Badge>
        </div>
        <CardDescription>
          Medical imaging data extracted from DICOM tags
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="basic" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basic">Basic Info</TabsTrigger>
            <TabsTrigger value="technical">Technical</TabsTrigger>
            <TabsTrigger value="equipment">Equipment</TabsTrigger>
          </TabsList>

          <TabsContent value="basic" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <MetadataField
                label="Instance Number"
                value={image.instance_number}
              />
              <MetadataField
                label="SOP Instance UID"
                value={image.sop_instance_uid}
                truncate
              />
              <MetadataField
                label="Image Size"
                value={image.rows && image.columns ? `${image.columns} × ${image.rows} pixels` : undefined}
              />
              <MetadataField
                label="File Size"
                value={`${(image.file_size_bytes / 1024).toFixed(2)} KB`}
              />
              <MetadataField
                label="Uploaded"
                value={new Date(image.uploaded_at).toLocaleString()}
              />
            </div>
          </TabsContent>

          <TabsContent value="technical" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <MetadataField
                label="Slice Thickness"
                value={image.slice_thickness ? `${image.slice_thickness} mm` : undefined}
              />
              <MetadataField
                label="Slice Location"
                value={image.slice_location ? `${image.slice_location} mm` : undefined}
              />
              <MetadataField
                label="Pixel Spacing"
                value={image.pixel_spacing}
              />
              <MetadataField
                label="Bits Allocated"
                value={image.bits_allocated}
              />
              <MetadataField
                label="Bits Stored"
                value={image.bits_stored}
              />
              <MetadataField
                label="Window Center"
                value={image.window_center}
                description="Optimal brightness for viewing"
              />
              <MetadataField
                label="Window Width"
                value={image.window_width}
                description="Optimal contrast for viewing"
              />
              <MetadataField
                label="Rescale Intercept"
                value={image.rescale_intercept}
                description="Hounsfield unit conversion"
              />
              <MetadataField
                label="Rescale Slope"
                value={image.rescale_slope}
              />
            </div>
          </TabsContent>

          <TabsContent value="equipment" className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              <MetadataField
                label="Manufacturer"
                value={image.manufacturer}
              />
              <MetadataField
                label="Model"
                value={image.manufacturer_model}
              />
            </div>

            {image.dicom_metadata && (
              <div className="mt-6">
                <h4 className="text-sm font-semibold mb-2">Additional DICOM Tags</h4>
                <div className="bg-muted p-4 rounded-md max-h-64 overflow-y-auto">
                  <pre className="text-xs">
                    {JSON.stringify(image.dicom_metadata, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function MetadataField({
  label,
  value,
  description,
  truncate = false,
}: {
  label: string;
  value?: string | number;
  description?: string;
  truncate?: boolean;
}) {
  if (value === undefined || value === null || value === '') {
    return null;
  }

  return (
    <div className="space-y-1">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className={`text-sm ${truncate ? 'truncate' : ''}`} title={truncate ? String(value) : undefined}>
        {value}
      </div>
      {description && (
        <div className="text-xs text-muted-foreground">{description}</div>
      )}
    </div>
  );
}
