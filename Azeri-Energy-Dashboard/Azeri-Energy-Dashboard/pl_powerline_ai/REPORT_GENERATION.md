# Report Generation Feature

This document describes the report generation functionality for both single uploads and bulk batch processing.

## Overview

The system automatically generates PDF reports for:
1. **Single Upload Reports** - Incident-style reports for individual image processing runs
2. **Bulk Batch Reports** - Statistics-style reports for bulk batch processing

## Installation

Install the required dependency:

```bash
pip install reportlab>=4.0.0
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Single Upload Report

### Automatic Generation

Reports are automatically generated when processing a single image via `/api/pipeline/run`. The report is saved to:
```
outputs/runs/{run_id}/artifacts/report.pdf
```

### Report Contents

- **Header Section**: Report ID, Date & Time, Tower ID, Status, GPS coordinates, Voltage Level, Tower Type, Region, Corridor Tag
- **Summary Section**: Total Findings, Critical Findings (HIGH severity), Needs Review count, Average AI Confidence
- **Detailed Findings Table**: List of all detections with Component Type, Defect Type, Severity, Confidence, Status
- **Visual Evidence**: Original image and detection overlay image displayed **side by side** for easy comparison

### Accessing Reports

1. **Via API**: `GET /api/runs/{run_id}/artifacts/report`
2. **Direct File Access**: `outputs/runs/{run_id}/artifacts/report.pdf`

The report URL is automatically included in the run's `artifacts.report_url` field.

## Bulk Batch Report

### Automatic Generation

Reports are automatically generated when processing a bulk batch via `/api/pipeline/bulk`. The report is saved to:
```
outputs/bulk_processing/{batch_id}/batch_report.pdf
```

### Report Contents

- **Executive Summary**: Batch ID, Processing Date, Total Images, Success/Failure counts, Total Detections, Unique Towers
- **Defect Type Breakdown Table**: Statistics by defect type (HIGH/MEDIUM/LOW severity counts, totals, percentages)
- **Component Type Breakdown Table**: Statistics by component type (HIGH/MEDIUM/LOW severity counts, totals, percentages)
- **Status Breakdown Table**: Statistics by status (confirmed/needs_review/false_positive)
- **Analysis Summary**: Paragraphs summarizing key findings and statistics
- **Organization by Defect Type**: Table showing how images were organized by defect type
- **Sample Images by Defect Type**: Visual samples from each defect category displayed **side by side** (up to 3 samples per defect type, 2 images per row)

### Accessing Reports

1. **Via API**: `GET /api/bulk-batches/{batch_id}/report`
2. **Direct File Access**: `outputs/bulk_processing/{batch_id}/batch_report.pdf`

The report path is included in the batch summary's `report_path` field.

## Manual Report Generation

You can also generate reports manually using the Python API:

### Single Upload Report

```python
from pathlib import Path
from src.utils.report_generator import generate_single_upload_report

# Generate report for a specific run
run_json_path = Path("outputs/runs/abc123/run.json")
report_path = generate_single_upload_report(run_json_path)
print(f"Report generated at: {report_path}")
```

### Bulk Batch Report

```python
from pathlib import Path
from src.utils.report_generator import generate_bulk_batch_report

# Generate report for a specific batch
summary_json_path = Path("outputs/bulk_processing/20260203_204555/summary.json")
report_path = generate_bulk_batch_report(summary_json_path)
print(f"Report generated at: {report_path}")
```

## Report Format

Both reports use:
- **Page Size**: A4
- **Format**: PDF
- **Styling**: Professional tables with alternating row colors, color-coded severity levels
- **Layout**: Multi-page with proper pagination

## Error Handling

- If `reportlab` is not installed, report generation is skipped with a warning (non-blocking)
- If image loading fails, the report continues without the image
- Reports are generated asynchronously and failures don't affect the main processing pipeline

## Integration

Reports are automatically generated:
- After successful single image processing (`/api/pipeline/run`)
- After successful bulk batch processing (`/api/pipeline/bulk`)

The API endpoints handle report generation gracefully - if report generation fails, the main processing still succeeds.

## Example Usage

### Frontend Integration

```typescript
// Get single upload report
const reportUrl = `/api/runs/${runId}/artifacts/report`;
window.open(reportUrl, '_blank');

// Get bulk batch report
const batchReportUrl = `/api/bulk-batches/${batchId}/report`;
window.open(batchReportUrl, '_blank');
```

### Backend Integration

The reports are automatically generated and available via the artifact endpoints. No additional configuration is needed.
