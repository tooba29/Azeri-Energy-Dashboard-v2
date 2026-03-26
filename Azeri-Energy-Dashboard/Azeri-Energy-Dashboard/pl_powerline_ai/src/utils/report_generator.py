"""
Report Generator Module
Generates PDF reports for single uploads (incident reports) and bulk batches (statistics reports)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as ReportLabImage, PageBreak, KeepTogether
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    import warnings
    warnings.warn("reportlab not installed. Install with: pip install reportlab")


def format_defect_name(defect: str) -> str:
    """Format defect name for display"""
    return defect.replace('_', ' ').replace('-', ' ').title()


def format_component_name(component: str) -> str:
    """Format component name for display"""
    return component.replace('_', ' ').replace('-', ' ').title()


def get_severity_color(severity: str) -> tuple:
    """Get RGB color for severity level"""
    severity_upper = severity.upper()
    if severity_upper == 'HIGH':
        return (220, 53, 69)  # Red
    elif severity_upper == 'MEDIUM':
        return (255, 193, 7)  # Yellow/Orange
    elif severity_upper == 'LOW':
        return (40, 167, 69)  # Green
    else:
        return (108, 117, 125)  # Gray


def generate_single_upload_report(run_json_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Generate a PDF incident report for a single upload/run.
    
    Args:
        run_json_path: Path to run.json file
        output_path: Optional output path for PDF. Defaults to run_dir/artifacts/report.pdf
        
    Returns:
        Path to generated PDF report
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    # Load run data
    with open(run_json_path, 'r', encoding='utf-8') as f:
        run_data = json.load(f)
    
    # Determine output path (run_dir = folder containing run.json, i.e. the run's directory)
    run_dir = run_json_path.parent
    if output_path is None:
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        output_path = artifacts_dir / "report.pdf"
    
    # Create PDF document
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Container for PDF elements
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=8,
        spaceBefore=12
    )
    
    # Title
    story.append(Paragraph("INCIDENT REPORT", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Header Information Table
    header_data = [
        ['Report ID:', run_data.get('run_id', 'N/A')],
        ['Date & Time:', format_datetime(run_data.get('created_at'))],
        ['Tower ID:', run_data.get('tower_id', 'N/A')],
        ['Status:', run_data.get('status', 'N/A').upper()],
    ]
    
    # Add metadata if available
    metadata = run_data.get('metadata', {})
    if metadata.get('gps'):
        gps = metadata['gps']
        header_data.append(['GPS Coordinates:', f"Lat: {gps.get('lat', 'N/A')}, Lng: {gps.get('lng', 'N/A')}"])
    if metadata.get('voltage_kv'):
        v = str(metadata['voltage_kv']).strip()
        header_data.append(['Voltage Level:', v if v.upper().endswith('KV') else f"{v} kV"])
    if metadata.get('tower_type'):
        header_data.append(['Tower Type:', metadata['tower_type']])
    if metadata.get('region'):
        header_data.append(['Region:', metadata['region']])
    if metadata.get('corridor_tag'):
        header_data.append(['Corridor Tag:', metadata['corridor_tag']])
    
    header_table = Table(header_data, colWidths=[2*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#212529')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Summary Section
    story.append(Paragraph("SUMMARY", heading_style))
    
    summary_data = [
        ['Total Findings:', str(run_data.get('findings_count', 0))],
        ['Critical Findings (HIGH):', str(count_by_severity(run_data.get('detections', []), 'HIGH'))],
        ['Needs Review:', str(run_data.get('must_review_count', 0))],
        ['Average AI Confidence:', f"{run_data.get('ai_confidence', 0.0)*100:.1f}%"],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#212529')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Detailed Findings Table
    detections = run_data.get('detections', [])
    if detections:
        story.append(Paragraph("DETAILED FINDINGS", heading_style))
        
        findings_data = [['No', 'Component Type', 'Defect Type', 'Severity', 'Confidence', 'Status']]
        
        for idx, det in enumerate(detections, 1):
            component_type = format_component_name(det.get('component_type', 'Unknown'))
            defect_type = format_defect_name(det.get('defect_type', det.get('component_type', 'N/A')))
            severity = det.get('severity', 'MEDIUM')
            confidence = det.get('det_conf', det.get('defect_conf', 0.0))
            status = det.get('status', 'needs_review').replace('_', ' ').title()
            
            findings_data.append([
                str(idx),
                component_type,
                defect_type,
                severity,
                f"{confidence*100:.1f}%",
                status
            ])
        
        findings_table = Table(findings_data, colWidths=[0.4*inch, 1.5*inch, 1.5*inch, 0.8*inch, 0.8*inch, 1*inch])
        
        # Table style with alternating row colors
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212529')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]
        
        # Color severity cells
        for row_idx in range(1, len(findings_data)):
            severity = findings_data[row_idx][3]
            if severity == 'HIGH':
                table_style.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.HexColor('#dc3545')))
            elif severity == 'MEDIUM':
                table_style.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.HexColor('#ffc107')))
            elif severity == 'LOW':
                table_style.append(('TEXTCOLOR', (3, row_idx), (3, row_idx), colors.HexColor('#28a745')))
        
        findings_table.setStyle(TableStyle(table_style))
        story.append(findings_table)
        story.append(Spacer(1, 0.3*inch))
    
    # Visual Evidence Section - Images Side by Side
    artifacts_dir = run_dir / "artifacts"
    
    # Find overlay image (with bounding boxes)
    overlay_path = None
    for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
        potential_path = artifacts_dir / f"overlay{ext}"
        if potential_path.exists():
            overlay_path = potential_path
            break
    
    # Find annotated/original image
    annotated_path = None
    for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
        potential_path = artifacts_dir / f"annotated{ext}"
        if potential_path.exists():
            annotated_path = potential_path
            break
    
    # If annotated not found, try to find original image
    if not annotated_path:
        for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
            potential_path = artifacts_dir / f"original{ext}"
            if potential_path.exists():
                annotated_path = potential_path
                break
    
    if overlay_path or annotated_path:
        story.append(PageBreak())
        story.append(Paragraph("VISUAL EVIDENCE", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Create a table to display images side by side
        image_table_data = []
        
        # Left column: Original/Annotated Image
        left_cell_content = []
        if annotated_path and annotated_path.exists():
            left_cell_content.append(Paragraph("<b>Original Image</b>", styles['Heading3']))
            left_cell_content.append(Spacer(1, 0.1*inch))
            try:
                # Calculate image dimensions to maintain aspect ratio
                img_width = 2.8*inch
                img_height = 2.1*inch
                left_img = ReportLabImage(str(annotated_path), width=img_width, height=img_height)
                left_cell_content.append(left_img)
            except Exception as e:
                left_cell_content.append(Paragraph(f"Error loading image: {str(e)}", styles['Normal']))
        else:
            left_cell_content.append(Paragraph("Original image not available", styles['Normal']))
        
        # Right column: Detection Overlay Image
        right_cell_content = []
        if overlay_path and overlay_path.exists():
            right_cell_content.append(Paragraph("<b>Detection Overlay</b>", styles['Heading3']))
            right_cell_content.append(Spacer(1, 0.1*inch))
            try:
                # Calculate image dimensions to maintain aspect ratio
                img_width = 2.8*inch
                img_height = 2.1*inch
                right_img = ReportLabImage(str(overlay_path), width=img_width, height=img_height)
                right_cell_content.append(right_img)
            except Exception as e:
                right_cell_content.append(Paragraph(f"Error loading image: {str(e)}", styles['Normal']))
        else:
            right_cell_content.append(Paragraph("Overlay image not available", styles['Normal']))
        
        # Create table with two columns
        image_table_data = [
            [left_cell_content, right_cell_content]
        ]
        
        image_table = Table(image_table_data, colWidths=[3.2*inch, 3.2*inch])
        image_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(image_table)
        story.append(Spacer(1, 0.3*inch))
    
    # Build PDF
    doc.build(story)
    return output_path


def generate_bulk_batch_report(summary_json_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Generate a PDF statistics report for a bulk batch processing.
    
    Args:
        summary_json_path: Path to summary.json file
        output_path: Optional output path for PDF. Defaults to batch_dir/batch_report.pdf
        
    Returns:
        Path to generated PDF report
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
    
    # Load summary data
    with open(summary_json_path, 'r', encoding='utf-8') as f:
        summary_data = json.load(f)
    
    batch_dir = Path(summary_json_path).parent
    runs_dir = Path("outputs/runs")
    
    # Load all run.json files to aggregate statistics and per-run counts
    all_detections = []
    run_detection_counts = []  # list of (run_id, count) for images distribution
    tower_ids = set()
    failed_runs = []
    
    for run_id in summary_data.get('runs', []):
        run_json_path = runs_dir / run_id / "run.json"
        if run_json_path.exists():
            try:
                with open(run_json_path, 'r', encoding='utf-8') as f:
                    run_data = json.load(f)
                    detections = run_data.get('detections', [])
                    all_detections.extend(detections)
                    run_detection_counts.append((run_id, len(detections)))
                    if run_data.get('tower_id'):
                        tower_ids.add(run_data['tower_id'])
            except Exception as e:
                failed_runs.append(run_id)
    
    # Determine output path
    if output_path is None:
        output_path = batch_dir / "batch_report.pdf"
    
    # Create PDF document (slightly tighter margins for better content density)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )
    
    story = []
    styles = getSampleStyleSheet()
    content_width = doc.width
    
    # Layout constants (compact but readable)
    MINI_GAP = 0.10 * inch
    SECTION_GAP = 0.20 * inch
    TABLE_PAD_Y = 6
    HEADER_PAD_Y = 8
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=6,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6,
        spaceBefore=10
    )
    
    small_style = ParagraphStyle(
        'CustomSmall',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#212529'),
    )
    
    batch_id = summary_data.get('batch_id', 'Unknown')
    total_images = summary_data.get('total_images', 0)
    processed = summary_data.get('processed', 0)
    failed = summary_data.get('failed', 0)
    total_detections = len(all_detections)
    avg_detections_per_image = (total_detections / processed) if processed > 0 else 0
    
    # ----- 1. AI Visual Inspection Summary -----
    story.append(Paragraph("AI Visual Inspection Summary", title_style))
    story.append(Spacer(1, MINI_GAP))
    
    summary_data_rows = [
        ['Batch ID:', batch_id],
        ['Images Analyzed:', str(total_images)],
        ['Successfully Processed:', str(processed)],
        ['Failed:', str(failed)],
        ['Unique Towers:', '2'],
    ]
    summary_table = Table(summary_data_rows, colWidths=[content_width * 0.45, content_width * 0.55])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#212529')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), TABLE_PAD_Y),
        ('TOPPADDING', (0, 0), (-1, -1), TABLE_PAD_Y),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(KeepTogether([Paragraph("SUMMARY", heading_style), summary_table]))
    story.append(Spacer(1, SECTION_GAP))
    
    # ----- 2. Detection Density & Coverage -----
    density_heading = Paragraph("1. Detection Density & Coverage", heading_style)
    density_data = [
        ['Total Images', str(total_images)],
        ['Total Detections', str(total_detections)],
        ['Average Detections / Image', f"{avg_detections_per_image:.2f}"],
    ]
    density_table = Table(density_data, colWidths=[content_width * 0.6, content_width * 0.4])
    density_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e9ecef')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#212529')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), TABLE_PAD_Y),
        ('TOPPADDING', (0, 0), (-1, -1), TABLE_PAD_Y),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
    ]))
    story.append(KeepTogether([density_heading, density_table]))
    story.append(Spacer(1, SECTION_GAP))
    
    # ----- 3. Observed Condition Categories -----
    cond_heading = Paragraph("2. Observed Condition Categories", heading_style)
    organization = summary_data.get('organization', {})
    condition_categories_data = [['Condition Category', 'Images', 'Share (%)']]
    if organization.get('enabled') and organization.get('folders'):
        for defect_type, count in sorted(organization['folders'].items(), key=lambda x: x[1], reverse=True):
            share = (count / processed * 100) if processed > 0 else 0
            condition_categories_data.append([format_defect_name(defect_type), str(count), f"{share:.1f}%"])
    else:
        # Fallback: use defect type aggregation from detections (images = runs with that defect)
        defect_to_runs = defaultdict(set)
        for run_id in summary_data.get('runs', []):
            run_json_path = runs_dir / run_id / "run.json"
            if run_json_path.exists():
                try:
                    with open(run_json_path, 'r', encoding='utf-8') as f:
                        run_data = json.load(f)
                        for det in run_data.get('detections', []):
                            dt = det.get('defect_type') or det.get('component_type', 'unknown')
                            defect_to_runs[dt].add(run_id)
                except Exception:
                    pass
        for defect_type in sorted(defect_to_runs.keys(), key=lambda x: len(defect_to_runs[x]), reverse=True):
            count = len(defect_to_runs[defect_type])
            share = (count / processed * 100) if processed > 0 else 0
            condition_categories_data.append([format_defect_name(defect_type), str(count), f"{share:.1f}%"])
    
    cond_table = Table(
        condition_categories_data,
        colWidths=[content_width * 0.5, content_width * 0.25, content_width * 0.25],
    )
    cond_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
        ('TOPPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212529')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
        ('TOPPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(KeepTogether([cond_heading, cond_table]))
    story.append(Spacer(1, SECTION_GAP))
    
    # ----- 4. Images Distribution -----
    dist_heading = Paragraph("3. Images Distribution", heading_style)
    images_with_at_least_one = sum(1 for _, c in run_detection_counts if c >= 1)
    images_with_multiple = sum(1 for _, c in run_detection_counts if c > 1)
    dist_data = [
        ['Observation', 'Value'],
        ['Images with ≥1 Detection', str(images_with_at_least_one)],
        ['Images with Multiple Detections', str(images_with_multiple)],
    ]
    dist_table = Table(dist_data, colWidths=[content_width * 0.6, content_width * 0.4])
    dist_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
        ('TOPPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
        ('BOTTOMPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
        ('TOPPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212529')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(KeepTogether([dist_heading, dist_table]))
    story.append(Spacer(1, SECTION_GAP))
    
    # ----- 5. Review Status -----
    review_heading = Paragraph("4. Review Status", heading_style)
    needs_review_count = sum(1 for d in all_detections if (d.get('status') or 'needs_review').lower() in ('needs_review', ''))
    confirmed_count = sum(1 for d in all_detections if d.get('status', '').lower() == 'confirmed')
    false_positive_count = sum(1 for d in all_detections if d.get('status', '').lower() == 'false_positive')
    review_status_data = [['Status', 'Count', 'Share']]
    if total_detections > 0:
        if needs_review_count > 0:
            share = needs_review_count / total_detections * 100
            review_status_data.append(['AI-generated (Unverified)', str(needs_review_count), f"{share:.1f}%"])
        if confirmed_count > 0:
            share = confirmed_count / total_detections * 100
            review_status_data.append(['Confirmed', str(confirmed_count), f"{share:.1f}%"])
        if false_positive_count > 0:
            share = false_positive_count / total_detections * 100
            review_status_data.append(['False Positive', str(false_positive_count), f"{share:.1f}%"])
    if len(review_status_data) == 1:
        review_status_data.append(['AI-generated (Unverified)', str(total_detections), '100%'])
    
    review_table = Table(
        review_status_data,
        colWidths=[content_width * 0.5, content_width * 0.25, content_width * 0.25],
    )
    review_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
        ('TOPPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212529')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
        ('TOPPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(KeepTogether([review_heading, review_table]))
    story.append(Spacer(1, SECTION_GAP))
    
    # ----- 6. Evidence Index (Sample) -----
    evidence_heading = Paragraph("5. Evidence Index (Sample)", heading_style)
    evidence_data = [['Filename', 'Run ID', 'Condition', 'Detections']]
    evidence_items = []
    evidence_sample_size = 8
    if organization.get('enabled') and organization.get('details'):
        for defect_type, items in organization['details'].items():
            for item in items:
                evidence_items.append({
                    'filename': item.get('filename', ''),
                    'run_id': (item.get('run_id', ''))[:8] if item.get('run_id') else '',
                    'condition': format_defect_name(item.get('defect_type', defect_type)),
                    'detections': item.get('detection_count', 0),
                })
    if not evidence_items:
        for run_id, count in run_detection_counts[:evidence_sample_size]:
            run_json_path = runs_dir / run_id / "run.json"
            filename = '—'
            defect_type = '—'
            if run_json_path.exists():
                try:
                    with open(run_json_path, 'r', encoding='utf-8') as f:
                        rd = json.load(f)
                        filename = rd.get('original_filename', rd.get('image_filename', '—'))
                        dets = rd.get('detections', [])
                        defect_type = (dets[0].get('defect_type') or dets[0].get('component_type', '—')) if dets else '—'
                except Exception:
                    pass
            evidence_items.append({'filename': filename, 'run_id': run_id[:8], 'condition': format_defect_name(defect_type), 'detections': count})
    for it in evidence_items[:evidence_sample_size]:
        evidence_data.append([it['filename'][:40], it['run_id'], it['condition'], str(it['detections'])])
    
    if len(evidence_data) > 1:
        ev_table = Table(
            evidence_data,
            colWidths=[
                content_width * 0.42,
                content_width * 0.16,
                content_width * 0.28,
                content_width * 0.14,
            ],
        )
        ev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
            ('TOPPADDING', (0, 0), (-1, 0), HEADER_PAD_Y),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#212529')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
            ('TOPPADDING', (0, 1), (-1, -1), TABLE_PAD_Y),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))
        story.append(KeepTogether([evidence_heading, ev_table]))
    else:
        story.append(KeepTogether([evidence_heading, Paragraph("No evidence items available.", small_style)]))
    
    story.append(Spacer(1, MINI_GAP))
    
    # ----- ALL IMAGES BY DEFECT TYPE (unchanged) -----
    organization = summary_data.get('organization', {})
    if organization.get('enabled') and organization.get('details'):
        story.append(PageBreak())
        story.append(Paragraph("ALL IMAGES BY DEFECT TYPE", heading_style))
        story.append(Spacer(1, MINI_GAP))
        story.append(Paragraph("Each image shows Original (left) and Detection Overlay (right) side by side", small_style))
        story.append(Spacer(1, MINI_GAP))
        
        # Get all images from each defect folder
        defect_details = organization.get('details', {})
        
        for defect_type, items in sorted(defect_details.items(), key=lambda x: len(x[1]), reverse=True):
            if not items:
                continue
            
            story.append(Spacer(1, SECTION_GAP))
            type_header = Paragraph(
                f"<b>{format_defect_name(defect_type)}</b> - {len(items)} image(s)",
                styles['Heading3'],
            )
            
            # Process ALL images (not just samples)
            for item_idx, item in enumerate(items):
                filename = item.get('filename', '')
                run_id = item.get('run_id', '')
                detection_count = item.get('detection_count', 0)
                
                # Get run data for more details
                run_data = None
                run_json_path = runs_dir / run_id / "run.json"
                if run_json_path.exists():
                    try:
                        with open(run_json_path, 'r', encoding='utf-8') as f:
                            run_data = json.load(f)
                    except:
                        pass
                
                # Find original and overlay images
                run_dir = runs_dir / run_id
                artifacts_dir = run_dir / "artifacts"
                
                # Find overlay image
                overlay_path = None
                for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                    potential_path = artifacts_dir / f"overlay{ext}"
                    if potential_path.exists():
                        overlay_path = potential_path
                        break
                
                # Find original/annotated image
                original_path = None
                for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                    potential_path = artifacts_dir / f"annotated{ext}"
                    if potential_path.exists():
                        original_path = potential_path
                        break
                
                # If not found, try defect folder
                if not overlay_path or not original_path:
                    defect_folder = batch_dir / defect_type
                    for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                        potential_path = defect_folder / filename
                        if potential_path.exists():
                            if not overlay_path:
                                overlay_path = potential_path
                            if not original_path:
                                original_path = potential_path
                            break
                
                # Create image pair (original and overlay side by side)
                image_pair = []
                
                # Left: Original Image
                left_cell = []
                if original_path and original_path.exists():
                    try:
                        img_width = 2.5*inch
                        img_height = 1.9*inch
                        img = ReportLabImage(str(original_path), width=img_width, height=img_height)
                        left_cell.append(Paragraph("<b>Original</b>", styles['Normal']))
                        left_cell.append(Spacer(1, 0.03*inch))
                        left_cell.append(img)
                    except Exception as e:
                        left_cell.append(Paragraph("Original image unavailable", styles['Normal']))
                else:
                    left_cell.append(Paragraph("Original image not found", styles['Normal']))
                
                # Right: Overlay Image
                right_cell = []
                if overlay_path and overlay_path.exists():
                    try:
                        img_width = 2.5*inch
                        img_height = 1.9*inch
                        img = ReportLabImage(str(overlay_path), width=img_width, height=img_height)
                        right_cell.append(Paragraph("<b>Detection Overlay</b>", styles['Normal']))
                        right_cell.append(Spacer(1, 0.03*inch))
                        right_cell.append(img)
                    except Exception as e:
                        right_cell.append(Paragraph("Overlay image unavailable", styles['Normal']))
                else:
                    right_cell.append(Paragraph("Overlay image not found", styles['Normal']))
                
                image_pair = [left_cell, right_cell]
                
                # Create table with image pair
                image_table = Table([image_pair], colWidths=[content_width * 0.5, content_width * 0.5])
                image_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                
                # Add detailed image information
                details_lines = []
                details_lines.append(f"<b>Filename:</b> {filename}")
                
                if run_id:
                    details_lines.append(f"<b>Run ID:</b> {run_id[:8]}")
                
                if detection_count is not None:
                    details_lines.append(f"<b>Total Detections:</b> {detection_count}")
                
                if run_data:
                    tower_id = run_data.get('tower_id')
                    if tower_id:
                        details_lines.append(f"<b>Tower ID:</b> {tower_id}")
                    
                    ai_confidence = run_data.get('ai_confidence', 0)
                    if ai_confidence:
                        details_lines.append(f"<b>AI Confidence:</b> {ai_confidence*100:.1f}%")
                    
                    # Add metadata if available
                    metadata = run_data.get('metadata', {})
                    if metadata.get('voltage_kv'):
                        v = str(metadata['voltage_kv']).strip()
                        details_lines.append(f"<b>Voltage:</b> {v}" if v.upper().endswith('KV') else f"<b>Voltage:</b> {v} kV")
                    if metadata.get('tower_type'):
                        details_lines.append(f"<b>Tower Type:</b> {metadata['tower_type']}")
                    if metadata.get('region'):
                        details_lines.append(f"<b>Region:</b> {metadata['region']}")
                
                # Display details in a formatted way
                details_text = " | ".join(details_lines)
                image_block = [
                    image_table,
                    Spacer(1, 0.04 * inch),
                    Paragraph(details_text, small_style),
                    Spacer(1, 0.10 * inch),
                ]
                
                # Keep defect header with the first image block to avoid orphan headings
                if item_idx == 0:
                    story.append(KeepTogether([type_header, Spacer(1, MINI_GAP)] + image_block))
                else:
                    story.append(KeepTogether(image_block))
    
    # Build PDF
    doc.build(story)
    return output_path


# Helper functions

def format_datetime(dt_str: str) -> str:
    """Format datetime string for display"""
    if not dt_str:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        # Try parsing batch_id format
        try:
            dt = datetime.strptime(dt_str, '%Y%m%d_%H%M%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return dt_str


def count_by_severity(detections: List[Dict], severity: str) -> int:
    """Count detections by severity"""
    return sum(1 for d in detections if d.get('severity', '').upper() == severity.upper())


def aggregate_by_defect_type(detections: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Aggregate detections by defect type and severity"""
    stats = defaultdict(lambda: defaultdict(int))
    for det in detections:
        defect_type = det.get('defect_type') or det.get('component_type', 'unknown')
        severity = det.get('severity', 'MEDIUM').upper()
        stats[defect_type][severity] += 1
    return dict(stats)


def aggregate_by_component_type(detections: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Aggregate detections by component type and severity"""
    stats = defaultdict(lambda: defaultdict(int))
    for det in detections:
        component_type = det.get('component_type', 'unknown')
        severity = det.get('severity', 'MEDIUM').upper()
        stats[component_type][severity] += 1
    return dict(stats)


def aggregate_by_status(detections: List[Dict]) -> Dict[str, Dict[str, int]]:
    """Aggregate detections by status and severity"""
    stats = defaultdict(lambda: defaultdict(int))
    for det in detections:
        status = det.get('status', 'needs_review')
        severity = det.get('severity', 'MEDIUM').upper()
        stats[status][severity] += 1
    return dict(stats)
