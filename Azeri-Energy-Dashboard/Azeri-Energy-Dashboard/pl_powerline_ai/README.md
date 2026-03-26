# Powerline Inspection AI System - Multi-Dataset Support

A complete, production-grade end-to-end Computer Vision system for automated powerline component detection and defect classification. This system supports multiple public datasets (InsPLAD, PLAD, CPLID, TTPLA) with automatic format conversion and unified training.

## 🏗️ Architecture Overview

This system uses a **two-stage pipeline**:

1. **Stage A (Detector)**: Detects powerline components in images using YOLO object detection
   - Components: glass_insulator, polymer_insulator, yoke_suspension, clamp, vari_grip, lightning_rod_suspension

2. **Stage B (Classifier)**: Classifies defects in each detected component crop
   - Defects: normal, rust, broken, missing_part, pollution_flashover

### Why Two Stages?

- **Modularity**: Train detection and classification independently
- **Efficiency**: Focus classification on component regions only
- **Scalability**: Easy to add new component types or defect classes
- **Data Efficiency**: Build defect dataset incrementally from detected components
- **Multi-Dataset Support**: Combine multiple datasets with different formats seamlessly

## 📁 Project Structure

```
pl_powerline_ai/
├── configs/                    # Configuration files
│   ├── components.yaml         # Component class definitions
│   ├── defects.yaml            # Defect class definitions
│   ├── train_detect.yaml       # Detection training config
│   ├── train_cls.yaml          # Classification training config
│   ├── dataset_sources.yaml    # Registered datasets and paths
│   └── label_mapping.yaml      # Dataset label -> unified label mapping
├── scripts/                    # Executable scripts (00-13)
│   ├── 00_check_env.py
│   ├── 01_register_datasets.py
│   ├── 02_convert_to_unified_detect_yolo.py
│   ├── 03_validate_detect_dataset.py      # CRITICAL: Prevents loss=0.0000
│   ├── 04_visualize_detect_labels.py
│   ├── 05_train_detector.py
│   ├── 06_eval_detector.py
│   ├── 07_generate_component_crops.py    # CRITICAL: Human-in-the-loop
│   ├── 08_build_defect_cls_dataset.py
│   ├── 09_validate_cls_dataset.py
│   ├── 10_visualize_cls_samples.py
│   ├── 11_train_defect_classifier.py
│   ├── 12_eval_defect_classifier.py
│   └── 13_full_inference_export_json.py   # Main inference script
├── src/
│   ├── converters/             # Format converters
│   │   ├── coco_to_yolo.py
│   │   ├── voc_to_yolo.py
│   │   ├── yolo_to_yolo.py
│   │   └── common.py
│   ├── datasets/               # Dataset management
│   │   ├── splits.py
│   │   └── mappings.py
│   ├── pipelines/              # Pipeline modules
│   └── utils/                  # Utility modules
│       ├── io.py
│       ├── viz.py
│       ├── metrics.py
│       ├── image_ops.py
│       └── logging.py
├── data/
│   ├── raw/                    # Place your downloaded datasets here
│   └── processed/              # Generated unified datasets
│       ├── detect_yolo/        # Unified detection dataset
│       └── cls_defects/        # Classification dataset
└── outputs/                     # All outputs
    ├── runs/                   # Ultralytics training outputs
    ├── reports/                # Validation and evaluation reports
    ├── crops/                  # Generated component crops
    └── predictions/            # Inference results
```

## 🚀 Quick Start

### 1. Installation

```powershell
# Create virtual environment (recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Check environment
python scripts/00_check_env.py
```

### 2. Prepare Your Datasets

Place your downloaded datasets in `data/raw/`. For example:

```
data/raw/
├── insplad_det/
│   ├── images/
│   └── annotations/
│       └── instances.json
├── plad/
│   ├── images/
│   └── labels/
└── cplid/
    ├── JPEGImages/
    └── Annotations/
```

## 📋 Complete Workflow (Windows PowerShell)

### Phase 1: Dataset Registration and Conversion

#### Step 1.1: Register Datasets

Register each dataset in `configs/dataset_sources.yaml`. You can do this manually or use the script:

**For InsPLAD (COCO format):**
```powershell
python scripts/01_register_datasets.py `
    --name insplad_det `
    --path data/raw/insplad_det `
    --format coco `
    --images-dir images `
    --ann-path annotations/instances.json
```

**For PLAD (YOLO format):**
```powershell
python scripts/01_register_datasets.py `
    --name plad `
    --path data/raw/plad `
    --format yolo `
    --images-dir images `
    --labels-dir labels
```

**For CPLID (VOC format):**
```powershell
python scripts/01_register_datasets.py `
    --name cplid `
    --path data/raw/cplid `
    --format voc `
    --images-dir JPEGImages `
    --ann-dir Annotations
```

Alternatively, edit `configs/dataset_sources.yaml` directly.

#### Step 1.2: Configure Label Mapping

Edit `configs/label_mapping.yaml` to map dataset-specific labels to unified component classes:

```yaml
mappings:
  insplad_det:
    "glass_insulator": "glass_insulator"
    "polymer_insulator": "polymer_insulator"
    "yoke": "yoke_suspension"
    "clamp": "clamp"
    # ... etc
```

#### Step 1.3: Convert to Unified YOLO Format

```powershell
python scripts/02_convert_to_unified_detect_yolo.py `
    --dataset-sources configs/dataset_sources.yaml `
    --label-mapping configs/label_mapping.yaml `
    --output data/processed/detect_yolo
```

This creates:
- `data/processed/detect_yolo/train/` (images + labels)
- `data/processed/detect_yolo/val/` (images + labels)
- `data/processed/detect_yolo/test/` (images + labels)
- `data/processed/detect_yolo/data.yaml` (YOLO config)

#### Step 1.4: Validate Detection Dataset (CRITICAL)

**This step prevents loss=0.0000 by catching missing/empty labels:**

```powershell
python scripts/03_validate_detect_dataset.py `
    --dataset data/processed/detect_yolo `
    --output-report outputs/reports/detect_dataset_report.json
```

**What it checks:**
- ✅ Every image has matching label file
- ✅ YOLO coordinates are valid (0-1 range)
- ✅ Class IDs are within range
- ✅ No corrupt images
- ✅ Class imbalance detection
- ✅ **Fatal issues that cause loss=0.0000**

**If validation fails, fix issues before training!**

#### Step 1.5: Visualize Detection Labels

```powershell
python scripts/04_visualize_detect_labels.py `
    --dataset data/processed/detect_yolo `
    --split train `
    --output outputs/reports/detect_label_viz `
    --max-images 50 `
    --sample
```

### Phase 2: Train Stage A Detector

#### Step 2.1: Train Detector

```powershell
python scripts/05_train_detector.py `
    --config configs/train_detect.yaml `
    --epochs 100 `
    --batch 16 `
    --device 0
```

**Training outputs:**
- `outputs/runs/detect_train/weights/best.pt` (best weights)
- `outputs/reports/best_detector.txt` (path to best weights)

#### Step 2.2: Evaluate Detector

```powershell
python scripts/06_eval_detector.py `
    --weights outputs/runs/detect_train/weights/best.pt `
    --data data/processed/detect_yolo/data.yaml `
    --split val `
    --output outputs/reports/detect_metrics.json
```

### Phase 3: Build Defect Classification Dataset (Human-in-the-Loop)

#### Step 3.1: Generate Component Crops

**Option A: From Ground-Truth Labels**
```powershell
python scripts/07_generate_component_crops.py `
    --from gt `
    --images data/processed/detect_yolo/train/images `
    --labels data/processed/detect_yolo/train/labels `
    --output outputs/crops/unlabeled `
    --padding-ratio 0.1 `
    --min-box-size 32 `
    --balance-classes
```

**Option B: From Detector Predictions**
```powershell
python scripts/07_generate_component_crops.py `
    --from pred `
    --images data/raw/your_images `
    --detector-weights outputs/runs/detect_train/weights/best.pt `
    --output outputs/crops/unlabeled `
    --conf-threshold 0.25 `
    --padding-ratio 0.1 `
    --min-box-size 32 `
    --balance-classes
```

**Output structure:**
```
outputs/crops/unlabeled/
├── glass_insulator/
│   ├── image1_0_0.jpg
│   ├── image1_0_0.json    # Metadata
│   └── ...
├── polymer_insulator/
└── ...
```

#### Step 3.2: Manual Labeling (Human-in-the-Loop)

**Workflow:**
1. Crops are generated in `outputs/crops/unlabeled/<component_class>/`
2. Manually sort crops into defect folders:
   ```
   data/processed/cls_defects/all/
   ├── normal/
   ├── rust/
   ├── broken/
   ├── missing_part/
   └── pollution_flashover/
   ```

**Tips:**
- Use Windows File Explorer to quickly drag-and-drop crops
- Start with 100-200 crops per defect class minimum
- Each crop has a `.json` file with metadata (original image, bbox, etc.)

**Alternative: CSV Labeling**

Create a CSV file `crop_labels.csv`:
```csv
crop_path,defect_label
outputs/crops/unlabeled/glass_insulator/img1.jpg,rust
outputs/crops/unlabeled/glass_insulator/img2.jpg,normal
...
```

Then use script 08 with `--mode csv`.

#### Step 3.3: Build Classification Dataset

**If manually sorted:**
```powershell
python scripts/08_build_defect_cls_dataset.py `
    --mode manual `
    --source-dir data/processed/cls_defects/all `
    --output data/processed/cls_defects `
    --create-splits
```

**If using CSV:**
```powershell
python scripts/08_build_defect_cls_dataset.py `
    --mode csv `
    --crops-dir outputs/crops/unlabeled `
    --csv-path crop_labels.csv `
    --output data/processed/cls_defects `
    --create-splits
```

#### Step 3.4: Validate Classification Dataset

```powershell
python scripts/09_validate_cls_dataset.py `
    --dataset data/processed/cls_defects `
    --output-report outputs/reports/cls_dataset_report.json
```

#### Step 3.5: Visualize Classification Samples

```powershell
python scripts/10_visualize_cls_samples.py `
    --dataset data/processed/cls_defects `
    --split train `
    --output outputs/reports/cls_samples_viz `
    --samples-per-class 5
```

### Phase 4: Train Stage B Classifier

#### Step 4.1: Train Defect Classifier

```powershell
python scripts/11_train_defect_classifier.py `
    --config configs/train_cls.yaml `
    --epochs 100 `
    --batch 32 `
    --device 0
```

**Training outputs:**
- `outputs/runs/cls_train/weights/best.pt` (best weights)
- `outputs/reports/best_classifier.txt` (path to best weights)

#### Step 4.2: Evaluate Classifier

```powershell
python scripts/12_eval_defect_classifier.py `
    --weights outputs/runs/cls_train/weights/best.pt `
    --dataset data/processed/cls_defects `
    --split val `
    --output outputs/reports/cls_metrics.json `
    --conf-matrix outputs/reports/cls_confusion_matrix.png
```

### Phase 5: Production Inference

#### Step 5.1: Run Full Inference Pipeline

```powershell
python scripts/13_full_inference_export_json.py `
    --detector-weights outputs/runs/detect_train/weights/best.pt `
    --classifier-weights outputs/runs/cls_train/weights/best.pt `
    --source ./test_images `
    --output outputs/predictions `
    --conf-threshold 0.25 `
    --iou-threshold 0.45
```

**Outputs:**
- `outputs/predictions/annotated/` - Annotated images with boxes and labels
- `outputs/predictions/json/` - JSON per image with detection and classification results
- `outputs/predictions/summary.csv` - Summary report
- `outputs/predictions/summary.json` - Summary statistics

#### JSON Output Format

Each image produces a JSON file:

```json
{
  "image_name": "image1.jpg",
  "width": 1920,
  "height": 1080,
  "detections": [
    {
      "component_class": "glass_insulator",
      "component_class_id": 0,
      "component_conf": 0.95,
      "bbox_xyxy": [100, 200, 300, 400],
      "defect_class": "rust",
      "defect_class_id": 1,
      "defect_conf": 0.87
    }
  ]
}
```

## 🐛 Common Failures and Solutions

### 1. Loss = 0.0000 During Training

**Cause**: No valid boxes in dataset or all boxes filtered out.

**Solution**:
- ✅ **Run script 03_validate_detect_dataset.py** - it catches this issue
- Check validation report for:
  - Missing label files
  - Invalid coordinates (not in 0-1 range)
  - Invalid class IDs (out of range)
  - Empty label files
- Fix issues and re-validate before training

**Prevention**: Always run validation script before training!

### 2. Duplicate Detections / NMS Issues

**Cause**: Overlapping detections not properly filtered.

**Solution**:
- Adjust `--iou-threshold` (lower = more aggressive NMS, default: 0.45)
- Adjust `--conf-threshold` (higher = fewer detections, default: 0.25)
- Check for duplicate labels in training data

### 3. Class Imbalance

**Cause**: One class has many more samples than others.

**Solution**:
- Use `--balance-classes` in crop generation
- Use `--max-crops-per-class` to limit per class
- Use data augmentation (configured in training YAML)
- Collect more data for minority classes
- Use class weights in training (modify config)

### 4. Poor Classification Performance

**Cause**: Insufficient or low-quality defect data.

**Solution**:
- Collect more defect samples (aim for 100+ per class minimum)
- Ensure crops are well-centered and contain the component
- Check for label noise (misclassified samples)
- Use data augmentation
- Try larger model (yolov8m-cls.pt or yolov8l-cls.pt)

### 5. Out of Memory (OOM)

**Solution**:
- Reduce batch size in training config
- Reduce image size (`--imgsz`)
- Use smaller model (yolov8n.pt instead of yolov8x.pt)
- Enable mixed precision training (default in Ultralytics)

### 6. Dataset Conversion Errors

**Cause**: Dataset format mismatch or missing files.

**Solution**:
- Check dataset structure matches expected format
- Verify paths in `dataset_sources.yaml`
- Check label mapping in `label_mapping.yaml`
- Ensure all required files exist (images, annotations)

## ⚙️ Configuration

### Component Classes (`configs/components.yaml`)

Edit to add/remove component types:

```yaml
classes:
  0: glass_insulator
  1: polymer_insulator
  # Add more...
```

### Defect Classes (`configs/defects.yaml`)

Edit to add/remove defect types:

```yaml
classes:
  0: normal
  1: rust
  # Add more...
```

### Dataset Sources (`configs/dataset_sources.yaml`)

Define your datasets:

```yaml
datasets:
  - name: insplad_det
    path: data/raw/insplad_det
    format: coco
    images_dir: images
    ann_path: annotations/instances.json
    enabled: true
    max_images: null  # null = all, or set limit
```

### Label Mapping (`configs/label_mapping.yaml`)

Map dataset labels to unified labels:

```yaml
mappings:
  insplad_det:
    "glass_insulator": "glass_insulator"
    "yoke": "yoke_suspension"
    "unknown": null  # Ignore this label
```

## 📊 Performance Tuning

### Detection Tuning

- **Confidence threshold**: Start with 0.25, adjust based on precision/recall trade-off
- **IoU threshold**: 0.45 for NMS (lower = more aggressive filtering)
- **Image size**: 640 is standard, increase to 1280 for small components
- **Model size**: yolov8n (fast) → yolov8s → yolov8m → yolov8l → yolov8x (accurate)

### Classification Tuning

- **Image size**: 224 is standard for classification
- **Batch size**: Increase if GPU memory allows (32-64)
- **Augmentation**: Adjust in `train_cls.yaml` (rotation, color jitter, etc.)

## 🔧 Adding Custom Dataset Format

If you have a dataset in a custom format:

1. Create a converter in `src/converters/custom_to_yolo.py`:

```python
from .common import ...

def convert_custom_dataset(
    dataset_path: Path,
    output_dir: Path,
    dataset_name: str,
    mapping_config_path: Path,
    components_config_path: Path,
    max_images: Optional[int] = None
) -> Dict[str, int]:
    # Your conversion logic here
    # Return stats dictionary
    pass
```

2. Register it in `scripts/02_convert_to_unified_detect_yolo.py`
3. Add format to `--format` choices in `01_register_datasets.py`

## 🚀 Next Improvements

### Active Learning Loop
- Automatically identify hard examples
- Prioritize crops for human labeling
- Iteratively improve classifier

### Hard Negative Mining
- Identify false positives from detector
- Add to training set to reduce false detections

### Multi-Task Detection (Future)
- Single-stage model that detects component + defect simultaneously
- Requires defect-annotated detection dataset

### Data Augmentation Strategies
- Domain-specific augmentations (weather, lighting)
- Synthetic data generation

## 📝 Dataset Labeling Guidelines

### Detection Labels (Stage A)

1. **Bounding boxes should:**
   - Tightly enclose the component
   - Include all visible parts
   - Avoid including background
   - Be consistent across similar components

2. **Class assignment:**
   - Use exact class names from `components.yaml`
   - Be consistent (same component type = same class)

3. **Quality checks:**
   - No overlapping boxes for same component
   - All components visible in image should be labeled
   - Boxes should not extend beyond image bounds

### Classification Labels (Stage B)

1. **Defect categories:**
   - **normal**: No visible defects
   - **rust**: Corrosion or rust visible
   - **broken**: Physical damage or cracks
   - **missing_part**: Component parts missing
   - **pollution_flashover**: Contamination or flashover marks

2. **Crop quality:**
   - Center the component in the crop
   - Include some context (padding helps)
   - Avoid crops that are too small (< 32px)

## 🤝 Contributing

This is a production system. When modifying:

1. Update configs for new classes
2. Re-run validation scripts
3. Test on validation set before production
4. Document any new features

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- Built with [Ultralytics YOLO](https://github.com/ultralytics/ultralytics)
- Uses OpenCV for image processing
- Supports InsPLAD, PLAD, CPLID, TTPLA datasets

---

**For questions or issues, check the validation reports and logs in `outputs/reports/`**

**Remember: Always run validation scripts before training to prevent loss=0.0000!**
