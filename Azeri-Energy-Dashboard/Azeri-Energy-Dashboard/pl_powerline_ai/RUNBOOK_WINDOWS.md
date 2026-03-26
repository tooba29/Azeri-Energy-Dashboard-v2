# Powerline Inspection AI - Windows Execution Runbook

**Step-by-step checklist for running the complete pipeline on Windows PowerShell.**

## Prerequisites Checklist

- [ ] Python 3.10+ installed
- [ ] Datasets extracted under `pl_powerline_ai/data/raw/`
- [ ] GPU available (optional, but recommended)

---

## Phase 1: Environment Setup

### Step 1.1: Create Virtual Environment

```powershell
cd pl_powerline_ai
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Expected output:** `(venv)` prefix in your prompt

### Step 1.2: Install Dependencies

```powershell
pip install -r requirements.txt
```

**Expected output:** All packages installed successfully

### Step 1.3: Check Environment

```powershell
python scripts/00_check_env.py
```

**Expected output:** All checks pass with ✓

**If fails:** Install missing packages with `pip install <package_name>`

---

## Phase 2: Dataset Discovery & Configuration

### Step 2.1: Verify Dataset Folders Exist

```powershell
# Check what datasets you have
Get-ChildItem data/raw/ -Directory
```

**Expected output:** List of dataset folders (e.g., `insplad_det`, `plad`, `cplid`)

**Action:** Note the folder names for next step

### Step 2.2: List Available Labels in Datasets

```powershell
python scripts/01b_list_dataset_labels.py --dataset-sources configs/dataset_sources.yaml
```

**Expected output:** 
```
Dataset: insplad_det
  Format: coco
  Available labels: glass_insulator, polymer_insulator, yoke, clamp, ...
  
Dataset: plad
  Format: yolo
  Available labels: 0=glass_insulator, 1=polymer_insulator, ...
```

**Action:** Use this output to fill `configs/label_mapping.yaml`

### Step 2.3: Configure Label Mapping

Edit `configs/label_mapping.yaml` to map your dataset labels to unified classes:

```yaml
mappings:
  insplad_det:
    "glass_insulator": "glass_insulator"
    "polymer_insulator": "polymer_insulator"
    "yoke": "yoke_suspension"
    # ... map all labels
```

**Action:** Map all labels from Step 2.2 output

### Step 2.4: Verify Dataset Sources Config

Edit `configs/dataset_sources.yaml` if needed:

```yaml
datasets:
  - name: insplad_det
    path: data/raw/insplad_det  # Verify this path exists
    format: coco
    enabled: true
    max_images: null  # or set limit for quick test
```

**Action:** Ensure all `path` values point to existing folders

---

## Phase 3: Dataset Conversion (QUICK MODE OPTIONAL)

### Step 3.1: Convert to Unified YOLO Format

**Full mode (all images):**
```powershell
python scripts/02_convert_to_unified_detect_yolo.py `
    --dataset-sources configs/dataset_sources.yaml `
    --label-mapping configs/label_mapping.yaml `
    --output data/processed/detect_yolo
```

**Quick mode (max 500 images per dataset, for testing):**
```powershell
python scripts/02_convert_to_unified_detect_yolo.py `
    --dataset-sources configs/dataset_sources.yaml `
    --label-mapping configs/label_mapping.yaml `
    --output data/processed/detect_yolo `
    --quick
```

**Expected output:**
```
Converting 3 dataset(s) to unified YOLO format...
Processing: insplad_det (coco)
  ✓ Converted: 1234 images, 5678 boxes mapped, 12 boxes ignored
...
Conversion Summary:
  Total images converted: 3456
  Total boxes mapped: 12345
```

**⚠️ CRITICAL:** If you see "Total boxes mapped: 0", check `label_mapping.yaml`!

**Action:** Note the total boxes count - should be > 0

---

## Phase 4: Dataset Validation (CRITICAL - Prevents loss=0.0000)

### Step 4.1: Validate Unified Dataset

```powershell
python scripts/03_validate_detect_dataset.py `
    --dataset data/processed/detect_yolo `
    --output-report outputs/reports/detect_dataset_report.json
```

**Expected output:**
```
======================================================================
DATASET VALIDATION REPORT
======================================================================

Summary:
  Total images: 3456
  Total boxes: 12345
  Empty labels: 0
  Missing labels: 0
  Corrupt images: 0
  Invalid coordinates: 0
  Invalid class IDs: 0

Class counts:
  glass_insulator: 4567
  polymer_insulator: 3456
  ...

======================================================================
✓ DATASET VALIDATION PASSED
======================================================================
```

**⚠️ FATAL ERRORS - DO NOT PROCEED IF:**
- Total boxes: 0 → Fix `label_mapping.yaml`
- Empty labels > 70% → Check source datasets
- Missing labels > 20% → Check dataset structure
- Invalid coordinates > 10% → Check annotation format

**Action:** Fix any fatal issues before proceeding

---

## Phase 5: Visualization (Optional but Recommended)

### Step 5.1: Visualize Detection Labels

```powershell
python scripts/04_visualize_detect_labels.py `
    --dataset data/processed/detect_yolo `
    --split train `
    --output outputs/reports/detect_label_viz `
    --max-images 50 `
    --sample `
    --only-with-boxes
```

**Expected output:**
```
Visualizing 50 images from train split...
Visualizations saved to: outputs/reports/detect_label_viz
```

**Action:** Open `outputs/reports/detect_label_viz/` and verify boxes look correct

---

## Phase 6: Train Stage A Detector

### Step 6.1: Train Detector

**Full mode:**
```powershell
python scripts/05_train_detector.py `
    --config configs/train_detect.yaml `
    --epochs 150 `
    --imgsz 960 `
    --batch 16 `
    --device 0
```

**Quick mode (for testing):**
```powershell
python scripts/05_train_detector.py `
    --config configs/train_detect.yaml `
    --quick
```

**Expected output:**
```
Validating dataset before training...
✓ Dataset validation passed

Training detector:
  Model: yolov8m.pt
  Dataset: data/processed/detect_yolo/data.yaml
  Epochs: 150
  Image size: 960
  Batch size: 16
  Device: 0

Epoch 1/150: ...
...
Training completed! Results: outputs/runs/detect_train
✓ Best weights saved to: outputs/runs/detect_train/weights/best.pt
```

**Training time:** ~2-6 hours depending on dataset size and GPU

**Action:** Wait for training to complete. Best weights saved automatically.

### Step 6.2: Evaluate Detector

```powershell
python scripts/06_eval_detector.py `
    --weights outputs/runs/detect_train/weights/best.pt `
    --data data/processed/detect_yolo/data.yaml `
    --split val `
    --output outputs/reports/detect_metrics.json
```

**Expected output:**
```
Evaluating detector:
  Weights: outputs/runs/detect_train/weights/best.pt
  Dataset: data/processed/detect_yolo/data.yaml
  Split: val

Evaluation completed!
  mAP50: 0.8234
  mAP50-95: 0.6543

Metrics saved to: outputs/reports/detect_metrics.json
```

**Action:** Check mAP50 - should be > 0.5 for a working detector

---

## Phase 7: Generate Component Crops (Human-in-the-Loop)

### Step 7.1: Generate Crops from Detector Predictions

```powershell
python scripts/07_generate_component_crops.py `
    --from pred `
    --images data/processed/detect_yolo/train/images `
    --detector-weights outputs/runs/detect_train/weights/best.pt `
    --output outputs/crops/unlabeled `
    --conf-threshold 0.25 `
    --iou-threshold 0.45 `
    --padding-ratio 0.1 `
    --min-box-size 24 `
    --balance-classes
```

**Expected output:**
```
Generating crops from pred...
  Images: data/processed/detect_yolo/train/images
  Output: outputs/crops/unlabeled

Processing images: 100%|████████| 1234/1234 [02:15<00:00]
Saving crops: 100%|████████| 5678/5678 [00:45<00:00]

======================================================================
Crop Generation Summary:
  glass_insulator: 1234 crops
  polymer_insulator: 987 crops
  ...
Total: 5678 crops
```

**Action:** Crops saved to `outputs/crops/unlabeled/<component_class>/`

### Step 7.2: Manual Labeling (Human-in-the-Loop)

**Workflow:**
1. Open `outputs/crops/unlabeled/` in Windows File Explorer
2. For each component class folder, manually sort crops into defect folders:
   - Create folders: `data/processed/cls_defects/all/normal/`
   - Create folders: `data/processed/cls_defects/all/rust/`
   - Create folders: `data/processed/cls_defects/all/broken/`
   - Create folders: `data/processed/cls_defects/all/missing_part/`
   - Create folders: `data/processed/cls_defects/all/pollution_flashover/`
3. Drag and drop crops from `outputs/crops/unlabeled/<component>/` to appropriate defect folder

**Tips:**
- Start with 100-200 crops per defect class minimum
- Use image viewer to quickly preview crops
- Each crop has a `.json` file with metadata (original image, bbox, etc.)

**Action:** Sort at least 100 crops per defect class before proceeding

---

## Phase 8: Build Classification Dataset

### Step 8.1: Build Classification Dataset

```powershell
python scripts/08_build_defect_cls_dataset.py `
    --mode manual `
    --source-dir data/processed/cls_defects/all `
    --output data/processed/cls_defects `
    --create-splits
```

**Expected output:**
```
Validating manually sorted dataset: data/processed/cls_defects/all
  normal: 234 images
  rust: 187 images
  broken: 156 images
  missing_part: 98 images
  pollution_flashover: 123 images

✓ Dataset built at: data/processed/cls_defects/all
Creating train/val/test splits...
✓ Splits created
```

**Action:** Verify all defect classes have images

### Step 8.2: Validate Classification Dataset

```powershell
python scripts/09_validate_cls_dataset.py `
    --dataset data/processed/cls_defects `
    --output-report outputs/reports/cls_dataset_report.json
```

**Expected output:**
```
======================================================================
CLASSIFICATION DATASET VALIDATION REPORT
======================================================================

Total images: 798
Corrupt images: 0

Class counts:
  normal: 234
  rust: 187
  broken: 156
  missing_part: 98
  pollution_flashover: 123

======================================================================
✓ VALIDATION PASSED
======================================================================
```

**Action:** Ensure all classes have at least 50 images minimum

### Step 8.3: Visualize Classification Samples (Optional)

```powershell
python scripts/10_visualize_cls_samples.py `
    --dataset data/processed/cls_defects `
    --split train `
    --output outputs/reports/cls_samples_viz `
    --samples-per-class 5
```

**Action:** Review samples to verify labeling quality

---

## Phase 9: Train Stage B Classifier

### Step 9.1: Train Defect Classifier

**Full mode:**
```powershell
python scripts/11_train_defect_classifier.py `
    --config configs/train_cls.yaml `
    --epochs 80 `
    --batch 64 `
    --device 0
```

**Quick mode:**
```powershell
python scripts/11_train_defect_classifier.py `
    --config configs/train_cls.yaml `
    --quick
```

**Expected output:**
```
Training defect classifier:
  Model: yolov8s-cls.pt
  Dataset: data/processed/cls_defects
  Epochs: 80
  Image size: 224
  Batch size: 64
  Device: 0

Training completed! Results: outputs/runs/cls_train
✓ Best weights: outputs/runs/cls_train/weights/best.pt
```

**Training time:** ~30 minutes - 2 hours depending on dataset size

### Step 9.2: Evaluate Classifier

```powershell
python scripts/12_eval_defect_classifier.py `
    --weights outputs/runs/cls_train/weights/best.pt `
    --dataset data/processed/cls_defects `
    --split val `
    --output outputs/reports/cls_metrics.json `
    --conf-matrix outputs/reports/cls_confusion_matrix.png
```

**Expected output:**
```
Evaluation Results:
  Accuracy: 0.8765

Per-class metrics:
  normal:
    Precision: 0.9123
    Recall: 0.8901
    F1-Score: 0.9010
  ...
```

**Action:** Check accuracy - should be > 0.7 for a working classifier

---

## Phase 10: Full Inference & JSON Export

### Step 10.1: Prepare Test Images

Create a folder with test images:
```powershell
mkdir test_images
# Copy some test images to test_images/
```

### Step 10.2: Run Full Inference Pipeline

```powershell
python scripts/13_full_inference_export_json.py `
    --detector-weights outputs/runs/detect_train/weights/best.pt `
    --classifier-weights outputs/runs/cls_train/weights/best.pt `
    --source test_images `
    --output outputs/predictions `
    --conf-threshold 0.25 `
    --iou-threshold 0.45
```

**Expected output:**
```
Processing 10 image(s)...

Processing: 100%|████████| 10/10 [01:23<00:00]

======================================================================
INFERENCE SUMMARY
======================================================================
Total images: 10
Total detections: 45

Defect counts:
  normal: 23
  rust: 12
  broken: 5
  missing_part: 3
  pollution_flashover: 2

Component counts:
  glass_insulator: 18
  polymer_insulator: 15
  ...

Results saved to: outputs/predictions
```

---

## Output Locations

### Training Outputs
- **Detector weights:** `outputs/runs/detect_train/weights/best.pt`
- **Classifier weights:** `outputs/runs/cls_train/weights/best.pt`
- **Best weights paths:** 
  - `outputs/reports/best_detector.txt`
  - `outputs/reports/best_classifier.txt`

### Reports
- **Detection validation:** `outputs/reports/detect_dataset_report.json`
- **Detection metrics:** `outputs/reports/detect_metrics.json`
- **Classification validation:** `outputs/reports/cls_dataset_report.json`
- **Classification metrics:** `outputs/reports/cls_metrics.json`
- **Confusion matrix:** `outputs/reports/cls_confusion_matrix.png`

### Visualizations
- **Detection labels:** `outputs/reports/detect_label_viz/`
- **Classification samples:** `outputs/reports/cls_samples_viz/`

### Inference Results
- **Annotated images:** `outputs/predictions/annotated/`
- **JSON per image:** `outputs/predictions/json/`
- **Summary CSV:** `outputs/predictions/summary.csv`
- **Summary JSON:** `outputs/predictions/summary.json`

### Crops
- **Unlabeled crops:** `outputs/crops/unlabeled/<component_class>/`

---

## Quick Mode Summary

Use `--quick` flag for faster testing:

**Conversion (quick):**
- Limits to 500 images per dataset
- Faster for testing pipeline

**Training (quick):**
- Detection: 20 epochs, imgsz=640
- Classification: 20 epochs
- Faster iteration for debugging

**When to use:**
- First run to test pipeline
- Debugging configuration issues
- Testing on small subset

**When NOT to use:**
- Final model training
- Production deployment

---

## Troubleshooting

### Issue: "Total boxes: 0" during conversion
**Solution:** Check `configs/label_mapping.yaml` - labels not mapped correctly

### Issue: "loss=0.0000" during training
**Solution:** Run validation script (Step 4.1) - dataset has issues

### Issue: "Out of Memory" during training
**Solution:** Reduce batch size: `--batch 8` or `--batch 4`

### Issue: "No images found" in dataset
**Solution:** Check dataset paths in `configs/dataset_sources.yaml`

### Issue: "Invalid class ID" in validation
**Solution:** Check class IDs match `configs/components.yaml` (0-indexed)

---

## Next Steps After Successful Run

1. **Collect more defect data:** Increase defect dataset size for better classifier
2. **Fine-tune thresholds:** Adjust `--conf-threshold` and `--iou-threshold` based on results
3. **Experiment with models:** Try larger models (yolov8l, yolov8x) for better accuracy
4. **Active learning:** Use predictions to identify hard examples for labeling

---

**Last Updated:** [Date]
**Status:** Ready for execution
