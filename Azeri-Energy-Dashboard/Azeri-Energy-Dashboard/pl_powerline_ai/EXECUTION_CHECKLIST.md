# Execution Checklist - Step-by-Step Validation

**Follow these steps in order. Do NOT proceed to training until all greenlights pass.**

---

## Step 1: List Dataset Labels

**Command:**
```powershell
python scripts/01b_list_dataset_labels.py
```

**What to check:**
- ✅ Script runs without errors
- ✅ You can see all dataset class names/categories
- ✅ Labels match what you have in `configs/label_mapping.yaml`

**If labels don't match:** Update `configs/label_mapping.yaml` before proceeding.

**Expected output:**
```
======================================================================
DATASET LABEL DISCOVERY
======================================================================

Dataset: insplad_det
  Path: data/raw/insplad_det
  Format: coco
  Available labels (5):
    'glass_insulator' (ID: 0)
    'polymer_insulator' (ID: 1)
    ...
```

---

## Step 2: Convert to Unified YOLO (Quick Mode First)

**Command:**
```powershell
python scripts/02_convert_to_unified_detect_yolo.py --quick
```

**Greenlight conditions (ALL must pass):**
- ✅ Script finishes without fatal errors
- ✅ `Total images converted: > 0`
- ✅ `Total boxes mapped: > 0` ⚠️ **CRITICAL**
- ✅ Boxes per class not all zero

**If you see:**
```
⚠️  FATAL ERROR: No boxes were mapped!
```
**→ DO NOT PROCEED** - Fix `configs/label_mapping.yaml` and re-run.

**Expected output:**
```
======================================================================
CONVERSION SUMMARY
======================================================================

Total images converted: 1234
Total labels created: 1234
Total boxes mapped: 5678

Per-dataset breakdown:
  insplad_det:
    Images: 500
    Boxes mapped: 2345
    Boxes ignored: 12
  ...
```

---

## Step 3: Validate Dataset (CRITICAL - Prevents loss=0.0000)

**Command:**
```powershell
python scripts/03_validate_detect_dataset.py --dataset data/processed/detect_yolo
```

**Greenlight conditions (ALL must pass):**
- ✅ `Total boxes: > 0` ⚠️ **CRITICAL**
- ✅ `Empty labels: < 70%` (ideally < 10%)
- ✅ No fatal issues reported
- ✅ Invalid coordinates < 10% of boxes
- ✅ Invalid class IDs < 10% of boxes

**If validator fails:**
- Copy the entire summary output
- Check the "FATAL ISSUES" section
- Fix issues before proceeding

**Expected output:**
```
======================================================================
DATASET VALIDATION REPORT
======================================================================

Summary:
  Total images: 1234
  Total boxes: 5678
  Empty labels: 0
  Missing labels: 0
  Corrupt images: 0
  Invalid coordinates: 0
  Invalid class IDs: 0

Class counts:
  glass_insulator: 2345
  polymer_insulator: 1234
  ...

======================================================================
✓ DATASET VALIDATION PASSED
======================================================================
```

**If you see FATAL ISSUES:**
```
======================================================================
FATAL ISSUES - DATASET VALIDATION FAILED
======================================================================
  ✗ FATAL: No valid boxes found in entire dataset!
```
**→ DO NOT PROCEED TO TRAINING** - Fix dataset issues first.

---

## Step 4: Visualize Labels (Sanity Check)

**Command:**
```powershell
python scripts/04_visualize_detect_labels.py --dataset data/processed/detect_yolo --split train --num 50
```

**What to check:**
- ✅ Script completes
- ✅ Images saved to `outputs/reports/detect_label_viz/`
- ✅ Open a few images and verify:
  - Boxes are aligned on real components
  - Boxes are NOT random/off-image
  - Boxes match the component class
  - Labels are readable

**If boxes look wrong:**
- Check source dataset annotations
- Verify label mapping is correct
- Re-run conversion if needed

---

## Step 5: Quick Training Smoke Test (Recommended)

**Command:**
```powershell
python scripts/05_train_detector.py --config configs/train_detect.yaml --quick
```

**Greenlight conditions:**
- ✅ Training starts (validation passes automatically)
- ✅ Loss is NOT 0.0000
- ✅ Loss decreases over epochs
- ✅ Training completes without errors

**If loss = 0.0000:**
- Stop training immediately
- Re-run validator (Step 3)
- Check for empty labels or missing boxes
- Fix dataset issues

**Expected output:**
```
Validating dataset before training...
✓ Dataset validation passed

Training detector:
  Model: yolov8m.pt
  Epochs: 20 (quick mode)
  ...

Epoch 1/20: loss=2.3456
Epoch 2/20: loss=1.9876
...
```

---

## Step 6: Full Training

**Command:**
```powershell
python scripts/05_train_detector.py --config configs/train_detect.yaml
```

**What to monitor:**
- Loss decreases over time
- mAP metrics improve
- Training completes successfully

**Training time:** 2-6 hours depending on dataset size and GPU

**After training:**
- Best weights: `outputs/runs/detect_train/weights/best.pt`
- Path saved: `outputs/reports/best_detector.txt`

---

## Step 7: Evaluate Detector

**Command:**
```powershell
python scripts/06_eval_detector.py --weights outputs/runs/detect_train/weights/best.pt --data data/processed/detect_yolo/data.yaml --split val
```

**Check metrics:**
- mAP50 > 0.5 (good)
- mAP50-95 > 0.3 (acceptable for first run)

---

## Stage B: Defect Classification

### Step 8: Generate Component Crops

**Command:**
```powershell
python scripts/07_generate_component_crops.py --from pred --weights outputs/runs/detect_train/weights/best.pt --source data/processed/detect_yolo/train/images --output outputs/crops/unlabeled
```

**Then manually sort crops into:**
- `data/processed/cls_defects/all/normal/`
- `data/processed/cls_defects/all/rust/`
- `data/processed/cls_defects/all/broken/`
- `data/processed/cls_defects/all/missing_part/`
- `data/processed/cls_defects/all/pollution_flashover/`

### Step 9: Build Classification Dataset

```powershell
python scripts/08_build_defect_cls_dataset.py --mode manual --source-dir data/processed/cls_defects/all --create-splits
```

### Step 10: Validate Classification Dataset

```powershell
python scripts/09_validate_cls_dataset.py --dataset data/processed/cls_defects
```

### Step 11: Train Classifier

```powershell
python scripts/11_train_defect_classifier.py --config configs/train_cls.yaml
```

---

## 🚨 Hard Rules

1. **DO NOT start training until Step 3 (validator) passes**
2. **DO NOT proceed if total_boxes == 0**
3. **DO NOT proceed if empty labels > 70%**
4. **DO NOT proceed if visualization shows wrong boxes**

---

## Quick Reference: What to Paste for Help

If you need help, paste this information:

1. **From Step 2 (Conversion):**
   - Total images converted
   - Total boxes mapped
   - Per-dataset breakdown

2. **From Step 3 (Validation):**
   - Total images
   - Total boxes
   - Empty labels count and %
   - Class counts
   - Any fatal issues

3. **From Step 5 (Quick Training):**
   - First epoch loss value
   - Whether loss decreases

---

**Last Updated:** Ready for execution
