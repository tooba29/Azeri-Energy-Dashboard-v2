"""Script 07: Generate component crops for defect labeling (CRITICAL for human-in-the-loop)."""

import argparse
from pathlib import Path
import cv2
import json
from tqdm import tqdm
from src.utils.io import load_yaml, ensure_dir, get_image_paths
from src.utils.image_ops import crop_roi, yolo_to_xyxy, load_image, get_image_size
from ultralytics import YOLO


def read_yolo_label(label_path: Path):
    """Read YOLO format label file."""
    annotations = []
    if not label_path.exists():
        return annotations
    with open(label_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
                annotations.append((class_id, x_center, y_center, width, height))
            except ValueError:
                continue
    return annotations


def main():
    parser = argparse.ArgumentParser(
        description='Generate component crops for defect labeling. '
                    'CRITICAL: This creates unlabeled crops for human sorting.'
    )
    parser.add_argument('--from', type=str, required=True, choices=['gt', 'pred'],
                        dest='source_type', help='Source: gt (ground-truth) or pred (detector predictions)')
    parser.add_argument('--images', type=str, required=True, help='Directory with images')
    parser.add_argument('--labels', type=str, default=None, help='Directory with YOLO labels (for --from=gt)')
    parser.add_argument('--detector-weights', type=str, default=None, help='Path to detector weights (for --from=pred)')
    parser.add_argument('--weights', type=str, default=None, help='Alias for --detector-weights (for convenience)')
    parser.add_argument('--source', type=str, default=None, help='Alias for --images (for convenience)')
    parser.add_argument('--output', type=str, default='outputs/crops/unlabeled', help='Output directory for crops')
    parser.add_argument('--components-config', type=str, default='configs/components.yaml')
    parser.add_argument('--padding-ratio', type=float, default=0.10,
                        help='Padding ratio around crops (default: 0.10 = 10%%)')
    parser.add_argument('--min-box-size', type=int, default=24,
                        help='Minimum box size in pixels (default: 24, crops smaller will be skipped)')
    parser.add_argument('--max-crops-per-class', type=int, default=None, help='Limit crops per component class')
    parser.add_argument('--balance-classes', action='store_true', help='Balance crops per class')
    parser.add_argument('--skip-low-conf', type=float, default=0.0, help='Skip predictions below this confidence')
    parser.add_argument('--conf-threshold', type=float, default=0.25, help='Detection confidence threshold (for pred)')
    parser.add_argument('--iou-threshold', type=float, default=0.45, help='IoU threshold for NMS (for pred)')
    
    args = parser.parse_args()
    
    # Handle aliases
    images_dir = Path(args.source if args.source else args.images)
    detector_weights = args.weights if args.weights else args.detector_weights
    if not images_dir.exists():
        print(f"Error: Images directory not found: {images_dir}")
        return 1
    
    components_config = load_yaml(args.components_config)
    component_class_names = components_config['names']
    
    output_dir = Path(args.output)
    ensure_dir(output_dir)
    
    # Create output directories for each component class
    for class_name in component_class_names:
        ensure_dir(output_dir / class_name)
    
    print(f"Generating crops from {args.source_type}...")
    print(f"  Images: {images_dir}")
    print(f"  Output: {output_dir}\n")
    
    crop_counts = {name: 0 for name in component_class_names}
    all_crops = {name: [] for name in component_class_names}
    
    if args.source_type == 'gt':
        if not args.labels:
            print("Error: --labels required when --from=gt")
            return 1
        labels_dir = Path(args.labels)
        
        images = get_image_paths(images_dir)
        for img_path in tqdm(images, desc="Processing images"):
            label_path = labels_dir / f"{img_path.stem}.txt"
            if not label_path.exists():
                continue
            
            img = load_image(img_path)
            if img is None:
                continue
            
            h, w = img.shape[:2]
            annotations = read_yolo_label(label_path)
            
            for class_id, x_center, y_center, width, height in annotations:
                if class_id >= len(component_class_names):
                    continue
                
                component_class = component_class_names[class_id]
                bbox = yolo_to_xyxy(x_center, y_center, width, height, w, h)
                
                box_w = bbox[2] - bbox[0]
                box_h = bbox[3] - bbox[1]
                if box_w < args.min_box_size or box_h < args.min_box_size:
                    continue
                
                crop = crop_roi(img, bbox, args.padding_ratio, args.min_box_size)
                if crop is None:
                    continue
                
                crop_info = {
                    'crop': crop,
                    'component_class': component_class,
                    'component_class_id': class_id,
                    'bbox_xyxy': list(bbox),
                    'original_image': str(img_path),
                    'confidence': 1.0
                }
                all_crops[component_class].append(crop_info)
    
    else:  # pred
        if not detector_weights:
            print("Error: --detector-weights (or --weights) required when --from=pred")
            return 1
        
        model = YOLO(detector_weights)
        images = get_image_paths(images_dir)
        
        for img_path in tqdm(images, desc="Processing images"):
            results = model.predict(str(img_path), conf=args.conf_threshold, iou=args.iou_threshold, verbose=False)
            img = load_image(img_path)
            if img is None:
                continue
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    if class_id >= len(component_class_names):
                        continue
                    
                    confidence = float(box.conf[0])
                    if confidence < args.skip_low_conf:
                        continue
                    
                    component_class = component_class_names[class_id]
                    bbox = box.xyxy[0].cpu().numpy().astype(int)
                    bbox = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                    
                    box_w = bbox[2] - bbox[0]
                    box_h = bbox[3] - bbox[1]
                    if box_w < args.min_box_size or box_h < args.min_box_size:
                        continue
                    
                    crop = crop_roi(img, bbox, args.padding_ratio, args.min_box_size)
                    if crop is None:
                        continue
                    
                    crop_info = {
                        'crop': crop,
                        'component_class': component_class,
                        'component_class_id': class_id,
                        'bbox_xyxy': list(bbox),
                        'original_image': str(img_path),
                        'confidence': confidence
                    }
                    all_crops[component_class].append(crop_info)
    
    # Balance or limit crops
    if args.balance_classes:
        min_count = min(len(crops) for crops in all_crops.values() if crops) if any(all_crops.values()) else 0
        for class_name in all_crops:
            if len(all_crops[class_name]) > min_count:
                import random
                random.seed(42)
                all_crops[class_name] = random.sample(all_crops[class_name], min_count)
    
    if args.max_crops_per_class:
        for class_name in all_crops:
            if len(all_crops[class_name]) > args.max_crops_per_class:
                import random
                random.seed(42)
                all_crops[class_name] = random.sample(all_crops[class_name], args.max_crops_per_class)
    
    # Save crops
    print("\nSaving crops...")
    for component_class, crops in all_crops.items():
        for idx, crop_info in enumerate(tqdm(crops, desc=f"Saving {component_class}", leave=False)):
                crop_filename = f"{Path(crop_info['original_image']).stem}_{crop_info['component_class_id']}_{idx}.jpg"
            crop_path = output_dir / component_class / crop_filename
            
            cv2.imwrite(str(crop_path), crop_info['crop'])
            
            # Save metadata (sidecar JSON) - CRITICAL for traceability
            metadata = {
                'original_image': crop_info['original_image'],
                'component_class': crop_info['component_class'],
                'component_class_id': crop_info['component_class_id'],
                'bbox_xyxy': crop_info['bbox_xyxy'],
                'confidence': crop_info['confidence'],
                'crop_path': str(crop_path),
                'timestamp': str(Path(crop_path).stat().st_mtime) if crop_path.exists() else None
            }
            json_path = crop_path.with_suffix('.json')
            with open(json_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            crop_counts[component_class] += 1
    
    print("\n" + "="*50)
    print("Crop Generation Summary:")
    total = 0
    for class_name, count in crop_counts.items():
        print(f"  {class_name}: {count} crops")
        total += count
    print(f"\nTotal: {total} crops")
    print(f"\nCrops saved to: {output_dir}")
    print("\nNext steps:")
    print("1. Manually sort crops into defect folders:")
    print("   data/processed/cls_defects/all/normal/")
    print("   data/processed/cls_defects/all/rust/")
    print("   data/processed/cls_defects/all/broken/")
    print("   data/processed/cls_defects/all/missing_part/")
    print("   data/processed/cls_defects/all/pollution_flashover/")
    print("2. Run script 08_build_defect_cls_dataset.py to validate and create splits")
    
    return 0


if __name__ == '__main__':
    exit(main())
