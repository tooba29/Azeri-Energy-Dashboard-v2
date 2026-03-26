# Powerline Inspection AI System

A complete, production-grade end-to-end Computer Vision system for automated powerline component detection and defect classification.

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

## 📁 Project Structure

```
pl_inspection_cv/
├── configs/                    # Configuration files
│   ├── components.yaml         # Component class definitions
│   ├── defects.yaml            # Defect class definitions
│   ├── train_detect.yaml       # Detection training config
│   └── train_cls.yaml          # Classification training config
├── scripts/                    # Executable scripts
│   ├── 01_make_detect_splits.py
│   ├── 02_validate_detect_dataset.py
│   ├── 03_visualize_detect_labels.py
│   ├── 04_train_detector.py
│   ├── 05_eval_detector.py
│   ├── 06_generate_crops_for_defects.py    # CRITICAL for dataset building
│   ├── 07_make_cls_splits.py
│   ├── 08_validate_cls_dataset.py
│   ├── 09_visualize_cls_samples.py
│   ├── 10_train_defect_classifier.py
│   ├── 11_eval_defect_classifier.py
│   └── 12_predict_stageA_stageB_export_json.py  # Main inference script
├── src/
│   ├── utils/                  # Utility modules
│   │   ├── io.py
│   │   ├── yolo.py
│   │   ├── viz.py
│   │   ├── metrics.py
│   │   ├── crops.py
│   │   └── dataset.py
│   └── pipelines/              # Pipeline modules
│       ├── detect_pipeline.py
│       ├── cls_pipeline.py
│       └── full_inference_pipeline.py
├── outputs/                    # Generated outputs
│   ├── runs/                   # Ultralytics training outputs
│   ├── reports/                 # Validation and evaluation reports
│   ├── crops/                  # Generated component crops
│   └── predictions/            # Inference results
├── yolo_dataset/               # YOLO detection dataset (created by scripts)
├── cls_dataset/                # Classification dataset (created by scripts)
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### 1. Installation

```powershell
# Create virtual environment (recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Dataset Structure

#### Stage A (Detection) Dataset

```
yolo_dataset/
├── train/
│   ├── images/
│   └── labels/          # YOLO format: class_id x_center y_center width height (normalized)
├── val/
│   ├── images/
│   └── labels/
└── test/                # Optional
    ├── images/
    └── labels/
```

**YOLO Label Format**: Each `.txt` file corresponds to an image and contains:
```
0 0.5 0.5 0.2 0.3
1 0.3 0.4 0.15 0.25
```
Where: `class_id x_center y_center width height` (all normalized 0-1)

#### Stage B (Classification) Dataset

```
cls_dataset/
├── train/
│   ├── normal/
│   ├── rust/
│   ├── broken/
│   ├── missing_part/
│   └── pollution_flashover/
├── val/
│   ├── normal/
│   ├── rust/
│   └── ...
└── test/                # Optional
    └── ...
```

## 📋 Step-by-Step Workflow

### Phase 1: Build Detection Dataset (Stage A)

#### Step 1.1: Prepare Detection Dataset

Organize your images and YOLO labels:
```
raw_data/
├── image1.jpg
├── image1.txt    # YOLO labels
├── image2.jpg
├── image2.txt
└── ...
```

#### Step 1.2: Create Train/Val/Test Splits

```powershell
python scripts/01_make_detect_splits.py `
    --source ./raw_data `
    --output ./yolo_dataset `
    --train-ratio 0.7 `
    --val-ratio 0.2 `
    --test-ratio 0.1
```

This creates `yolo_dataset/` with train/val/test splits and generates `yolo_dataset/data.yaml`.

#### Step 1.3: Validate Detection Dataset

```powershell
python scripts/02_validate_detect_dataset.py `
    --dataset ./yolo_dataset `
    --output-report ./outputs/reports/detect_dataset_report.json
```

**Checks performed:**
- Image-label pairing
- YOLO coordinate validation (0-1 range, valid dimensions)
- Class ID validation
- Class imbalance detection
- Empty label detection

**Common Issues:**
- **Loss = 0.0000**: Usually means no valid boxes found. Check validator output.
- **Invalid coordinates**: Ensure labels are normalized (0-1) and boxes are within image bounds.

#### Step 1.4: Visualize Labels

```powershell
python scripts/03_visualize_detect_labels.py `
    --dataset ./yolo_dataset `
    --split train `
    --output ./outputs/visualizations/detect `
    --max-images 50 `
    --sample
```

#### Step 1.5: Train Detector

```powershell
python scripts/04_train_detector.py `
    --config ./configs/train_detect.yaml `
    --epochs 100 `
    --batch 16 `
    --device 0
```

**Training outputs**: `./outputs/runs/detect_train/`

**Best weights**: `./outputs/runs/detect_train/weights/best.pt`

#### Step 1.6: Evaluate Detector

```powershell
python scripts/05_eval_detector.py `
    --weights ./outputs/runs/detect_train/weights/best.pt `
    --data ./yolo_dataset/data.yaml `
    --split val `
    --output ./outputs/reports/detect_metrics.json
```

### Phase 2: Build Classification Dataset (Stage B)

#### Step 2.1: Generate Component Crops

**Option A: From Ground-Truth Labels**

```powershell
python scripts/06_generate_crops_for_defects.py `
    --from gt `
    --images ./yolo_dataset/train/images `
    --labels ./yolo_dataset/train/labels `
    --output ./outputs/crops/unlabeled `
    --padding-ratio 0.1 `
    --min-box-size 32 `
    --balance-classes
```

**Option B: From Detector Predictions**

```powershell
python scripts/06_generate_crops_for_defects.py `
    --from pred `
    --images ./raw_images `
    --detector-weights ./outputs/runs/detect_train/weights/best.pt `
    --output ./outputs/crops/unlabeled `
    --conf-threshold 0.25 `
    --iou-threshold 0.45 `
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

#### Step 2.2: Manual Labeling (Human-in-the-Loop)

**Workflow:**
1. Crops are generated in `outputs/crops/unlabeled/<component_class>/`
2. Manually sort crops into defect folders:
   ```
   cls_dataset/train/
   ├── normal/
   ├── rust/
   ├── broken/
   ├── missing_part/
   └── pollution_flashover/
   ```

**Tips:**
- Start with a small subset (100-200 crops per defect class)
- Use file explorer or image viewer to quickly sort
- Each crop has a `.json` file with metadata (original image, bbox, etc.)

#### Step 2.3: Create Train/Val/Test Splits

If you organized crops directly into `cls_dataset/train/`, create splits:

```powershell
python scripts/07_make_cls_splits.py `
    --source ./cls_dataset/train `
    --output ./cls_dataset `
    --train-ratio 0.7 `
    --val-ratio 0.2 `
    --test-ratio 0.1
```

Or if you have a flat structure (`cls_dataset/all/normal/`, etc.):

```powershell
python scripts/07_make_cls_splits.py `
    --source ./cls_dataset/all `
    --output ./cls_dataset `
    --train-ratio 0.7 `
    --val-ratio 0.2 `
    --test-ratio 0.1
```

#### Step 2.4: Validate Classification Dataset

```powershell
python scripts/08_validate_cls_dataset.py `
    --dataset ./cls_dataset `
    --output-report ./outputs/reports/cls_dataset_report.json
```

**Checks performed:**
- Image counts per class
- Empty class detection
- Corrupt image detection
- Class imbalance detection

#### Step 2.5: Visualize Classification Samples

```powershell
python scripts/09_visualize_cls_samples.py `
    --dataset ./cls_dataset `
    --split train `
    --output ./outputs/visualizations/cls `
    --samples-per-class 5
```

#### Step 2.6: Train Defect Classifier

```powershell
python scripts/10_train_defect_classifier.py `
    --config ./configs/train_cls.yaml `
    --epochs 100 `
    --batch 32 `
    --device 0
```

**Training outputs**: `./outputs/runs/cls_train/`

**Best weights**: `./outputs/runs/cls_train/weights/best.pt`

#### Step 2.7: Evaluate Classifier

```powershell
python scripts/11_eval_defect_classifier.py `
    --weights ./outputs/runs/cls_train/weights/best.pt `
    --dataset ./cls_dataset `
    --split val `
    --output ./outputs/reports/cls_metrics.json `
    --conf-matrix ./outputs/reports/cls_confusion_matrix.png
```

### Phase 3: Production Inference

#### Step 3.1: Run Full Pipeline

```powershell
python scripts/12_predict_stageA_stageB_export_json.py `
    --detector-weights ./outputs/runs/detect_train/weights/best.pt `
    --classifier-weights ./outputs/runs/cls_train/weights/best.pt `
    --source ./test_images `
    --output ./outputs/predictions `
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

### Training Configs

- `configs/train_detect.yaml`: Detection training parameters
- `configs/train_cls.yaml`: Classification training parameters

## 🐛 Troubleshooting

### Common Issues

#### 1. Loss = 0.0000 During Training

**Cause**: No valid boxes in dataset or all boxes filtered out.

**Solution**:
- Run `02_validate_detect_dataset.py` to check for issues
- Verify labels are in correct format (normalized 0-1)
- Check that class IDs match config (0 to num_classes-1)
- Ensure boxes have width/height > 0

#### 2. Duplicate Detections / NMS Issues

**Cause**: Overlapping detections not properly filtered.

**Solution**:
- Adjust `--iou-threshold` (lower = more aggressive NMS)
- Adjust `--conf-threshold` (higher = fewer detections)
- Check for duplicate labels in training data

#### 3. Class Imbalance

**Cause**: One class has many more samples than others.

**Solution**:
- Use `--balance-classes` in crop generation
- Use data augmentation (configured in training YAML)
- Collect more data for minority classes
- Use class weights in training (modify config)

#### 4. Poor Classification Performance

**Cause**: Insufficient or low-quality defect data.

**Solution**:
- Collect more defect samples (aim for 100+ per class minimum)
- Ensure crops are well-centered and contain the component
- Check for label noise (misclassified samples)
- Use data augmentation
- Try larger model (yolo11m-cls.pt or yolo11l-cls.pt)

#### 5. Out of Memory (OOM)

**Solution**:
- Reduce batch size in training config
- Reduce image size (`--imgsz`)
- Use smaller model (yolo11n.pt instead of yolo11x.pt)
- Enable mixed precision training (default in Ultralytics)

### Validation Failures

If `02_validate_detect_dataset.py` or `08_validate_cls_dataset.py` report fatal issues:

1. **No valid boxes**: Check label files exist and are not empty
2. **Invalid coordinates**: Ensure YOLO format is normalized (0-1)
3. **Invalid class IDs**: Check class IDs match config (0-indexed)
4. **Corrupt images**: Re-download or re-process images
5. **Empty classes**: Collect more data for missing classes

## 📊 Performance Tuning

### Detection Tuning

- **Confidence threshold**: Start with 0.25, adjust based on precision/recall trade-off
- **IoU threshold**: 0.45 for NMS (lower = more aggressive filtering)
- **Image size**: 640 is standard, increase to 1280 for small components
- **Model size**: yolo11n (fast) → yolo11s → yolo11m → yolo11l → yolo11x (accurate)

### Classification Tuning

- **Image size**: 224 is standard for classification
- **Batch size**: Increase if GPU memory allows (32-64)
- **Augmentation**: Adjust in `train_cls.yaml` (rotation, color jitter, etc.)

## 🔧 Advanced Usage

### Custom Model Paths

Override model paths in training:

```powershell
python scripts/04_train_detector.py `
    --config ./configs/train_detect.yaml `
    --model yolo11m.pt `
    --epochs 150 `
    --batch 8
```

### Process Single Image

```powershell
python scripts/12_predict_stageA_stageB_export_json.py `
    --detector-weights ./outputs/runs/detect_train/weights/best.pt `
    --classifier-weights ./outputs/runs/cls_train/weights/best.pt `
    --source ./test_image.jpg `
    --output ./outputs/predictions
```

### Process Video

Videos are supported (Ultralytics handles them automatically):

```powershell
python scripts/12_predict_stageA_stageB_export_json.py `
    --detector-weights ./outputs/runs/detect_train/weights/best.pt `
    --classifier-weights ./outputs/runs/cls_train/weights/best.pt `
    --source ./test_video.mp4 `
    --output ./outputs/predictions
```

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

---

**For questions or issues, check the validation reports and logs in `outputs/reports/`**
