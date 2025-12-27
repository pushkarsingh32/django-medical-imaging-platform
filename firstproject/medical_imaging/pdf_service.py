"""
PDF Report Generation Service
Generates comprehensive patient medical reports including studies and diagnoses
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.colors import HexColor
from datetime import datetime
from io import BytesIO
from django.conf import settings
import os


class PatientReportGenerator:
    """Generate PDF reports for patients with their medical imaging data"""

    def __init__(self, patient):
        self.patient = patient
        self.buffer = BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch,
        )
        self.styles = getSampleStyleSheet()
        self.story = []

        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=HexColor('#1a73e8'),
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=HexColor('#1a73e8'),
            spaceAfter=12,
            spaceBefore=12,
        )

        self.subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=HexColor('#5f6368'),
            spaceAfter=6,
        )

    def add_header(self):
        """Add report header with hospital and patient info"""
        # Title
        title = Paragraph("Medical Imaging Report", self.title_style)
        self.story.append(title)

        # Report metadata
        report_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        metadata = Paragraph(f"<i>Generated on {report_date}</i>", self.styles['Normal'])
        self.story.append(metadata)
        self.story.append(Spacer(1, 0.3*inch))

    def add_patient_info(self):
        """Add patient demographic information"""
        self.story.append(Paragraph("Patient Information", self.heading_style))

        # Calculate age
        today = datetime.now().date()
        age = today.year - self.patient.date_of_birth.year - (
            (today.month, today.day) < (self.patient.date_of_birth.month, self.patient.date_of_birth.day)
        )

        gender_display = {
            'M': 'Male',
            'F': 'Female',
            'O': 'Other'
        }.get(self.patient.gender, self.patient.gender)

        data = [
            ['Medical Record Number:', self.patient.medical_record_number],
            ['Full Name:', self.patient.full_name],
            ['Date of Birth:', self.patient.date_of_birth.strftime("%B %d, %Y")],
            ['Age:', f"{age} years"],
            ['Gender:', gender_display],
            ['Phone:', self.patient.phone or 'N/A'],
            ['Email:', self.patient.email or 'N/A'],
            ['Address:', self.patient.address or 'N/A'],
            ['Hospital:', self.patient.hospital.name],
        ]

        table = Table(data, colWidths=[2.5*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#5f6368')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.3*inch))

    def add_studies_summary(self, studies):
        """Add summary of all imaging studies"""
        if not studies:
            self.story.append(Paragraph("No imaging studies found for this patient.", self.styles['Normal']))
            return

        self.story.append(Paragraph("Imaging Studies Summary", self.heading_style))

        # Summary statistics
        total_studies = len(studies)
        total_images = sum(study.images.count() for study in studies)

        summary_text = f"<b>Total Studies:</b> {total_studies} | <b>Total Images:</b> {total_images}"
        self.story.append(Paragraph(summary_text, self.styles['Normal']))
        self.story.append(Spacer(1, 0.2*inch))

        # Studies table
        table_data = [['Date', 'Modality', 'Body Part', 'Status', 'Images', 'Diagnosis']]

        for study in studies:
            diagnosis_status = 'Yes' if hasattr(study, 'diagnosis') and study.diagnosis else 'No'
            table_data.append([
                study.study_date.strftime("%Y-%m-%d"),
                study.modality,
                study.body_part,
                study.status.title(),
                str(study.images.count()),
                diagnosis_status,
            ])

        table = Table(table_data, colWidths=[1.2*inch, 1*inch, 1.2*inch, 1*inch, 0.7*inch, 0.9*inch])
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a73e8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Body style
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')]),

            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        self.story.append(table)
        self.story.append(Spacer(1, 0.3*inch))

    def add_detailed_studies(self, studies):
        """Add detailed information for each study including diagnoses"""
        if not studies:
            return

        self.story.append(PageBreak())
        self.story.append(Paragraph("Detailed Study Reports", self.heading_style))
        self.story.append(Spacer(1, 0.2*inch))

        for idx, study in enumerate(studies, 1):
            # Study header
            study_title = f"Study {idx}: {study.modality} - {study.body_part}"
            self.story.append(Paragraph(study_title, self.subheading_style))

            # Study details
            details_data = [
                ['Study Date:', study.study_date.strftime("%B %d, %Y at %I:%M %p")],
                ['Status:', study.status.title()],
                ['Total Images:', str(study.images.count())],
            ]

            if study.referring_physician:
                details_data.append(['Referring Physician:', study.referring_physician])

            if study.clinical_notes:
                details_data.append(['Clinical Notes:', study.clinical_notes])

            details_table = Table(details_data, colWidths=[2*inch, 4.5*inch])
            details_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))

            self.story.append(details_table)
            self.story.append(Spacer(1, 0.15*inch))

            # Diagnosis section
            if hasattr(study, 'diagnosis') and study.diagnosis:
                diagnosis = study.diagnosis

                self.story.append(Paragraph("<b>Diagnosis Report</b>", self.styles['Normal']))
                self.story.append(Spacer(1, 0.1*inch))

                # Severity badge color
                severity_colors = {
                    'normal': HexColor('#10b981'),
                    'minor': HexColor('#3b82f6'),
                    'moderate': HexColor('#f59e0b'),
                    'severe': HexColor('#ef4444'),
                }
                severity_color = severity_colors.get(diagnosis.severity, colors.grey)

                diagnosis_data = [
                    ['Severity:', diagnosis.severity.upper()],
                    ['Radiologist:', diagnosis.radiologist.get_full_name() or diagnosis.radiologist.username],
                    ['Diagnosed On:', diagnosis.diagnosed_at.strftime("%B %d, %Y at %I:%M %p")],
                ]

                diag_table = Table(diagnosis_data, colWidths=[2*inch, 4.5*inch])
                diag_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('TEXTCOLOR', (1, 0), (1, 0), severity_color),
                    ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))

                self.story.append(diag_table)
                self.story.append(Spacer(1, 0.1*inch))

                # Findings
                self.story.append(Paragraph("<b>Findings:</b>", self.styles['Normal']))
                findings = Paragraph(diagnosis.findings.replace('\n', '<br/>'), self.styles['BodyText'])
                self.story.append(findings)
                self.story.append(Spacer(1, 0.1*inch))

                # Impression
                if diagnosis.impression:
                    self.story.append(Paragraph("<b>Impression:</b>", self.styles['Normal']))
                    impression = Paragraph(diagnosis.impression.replace('\n', '<br/>'), self.styles['BodyText'])
                    self.story.append(impression)
                    self.story.append(Spacer(1, 0.1*inch))

                # Recommendations
                if diagnosis.recommendations:
                    self.story.append(Paragraph("<b>Recommendations:</b>", self.styles['Normal']))
                    recommendations = Paragraph(diagnosis.recommendations.replace('\n', '<br/>'), self.styles['BodyText'])
                    self.story.append(recommendations)
            else:
                self.story.append(Paragraph("<i>No diagnosis available for this study.</i>", self.styles['Normal']))

            # Separator between studies
            if idx < len(studies):
                self.story.append(Spacer(1, 0.2*inch))
                self.story.append(Paragraph("─" * 80, self.styles['Normal']))
                self.story.append(Spacer(1, 0.2*inch))

    def add_footer(self):
        """Add report footer"""
        self.story.append(Spacer(1, 0.5*inch))
        footer_text = f"""
        <para align=center>
        <font size=8 color='#5f6368'>
        This is a confidential medical report generated by the Medical Imaging Platform.<br/>
        Report ID: {self.patient.id}-{datetime.now().strftime("%Y%m%d%H%M%S")}<br/>
        © {datetime.now().year} Medical Imaging Platform. All rights reserved.
        </font>
        </para>
        """
        self.story.append(Paragraph(footer_text, self.styles['Normal']))

    def generate(self):
        """Generate the complete PDF report"""
        # Get all studies for this patient
        studies = self.patient.imaging_studies.all().order_by('-study_date').prefetch_related('images', 'diagnosis')

        # Build the report
        self.add_header()
        self.add_patient_info()
        self.add_studies_summary(studies)
        self.add_detailed_studies(studies)
        self.add_footer()

        # Build PDF
        self.doc.build(self.story)

        # Get PDF bytes
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()

        return pdf_bytes
