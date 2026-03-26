"""Script 13: Full inference pipeline using model API only."""

import argparse
from pathlib import Path
import cv2
import json
import csv
from tqdm import tqdm
from src.utils.io import load_yaml, save_json, get_image_paths, ensure_dir
from src.utils.image_ops import crop_roi
from src.utils.model_api import ModelAPI
from src.utils.viz import draw_bbox, COMPONENT_COLORS


def main():
    parser = argparse.ArgumentParser(
        description='Full inference using model API: Detection -> Export JSON'
    )
    parser.add_argument('--model-config', type=str, default='configs/model.yaml',
                        help='Path to model config YAML')
    parser.add_argument('--source', type=str, required=True, help='Source directory or file')
    parser.add_argument('--output', type=str, default='outputs/predictions')
    parser.add_argument('--components-config', type=str, default='configs/components.yaml',
                        help='Path to components config YAML (for class mapping)')
    parser.add_argument('--conf-threshold', type=float, default=None,
                        help='Confidence threshold (overrides config)')
    parser.add_argument('--no-annotated', action='store_true',
                        help='Skip saving annotated images')
    parser.add_argument('--no-json', action='store_true',
                        help='Skip saving JSON per image')
    parser.add_argument('--no-csv', action='store_true',
                        help='Skip saving summary CSV')
    
    args = parser.parse_args()
    
    # Load configs
    model_config_path = Path(args.model_config)
    if not model_config_path.exists():
        print(f"Error: model config not found: {model_config_path}")
        return 1
    
    rf_cfg = load_yaml(args.model_config)
    components_config = load_yaml(args.components_config)
    component_class_names = components_config['names']
    
    # Initialize model API
    api = ModelAPI(
        api_key=rf_cfg['api_key'],
        model_id=rf_cfg['model_id'],
        api_url=rf_cfg.get('api_url', 'https://serverless.roboflow.com')
    )
    
    # Get confidence threshold
    conf_threshold = args.conf_threshold if args.conf_threshold is not None else rf_cfg.get('confidence_threshold', 0.25)
    
    # Class mapping
    class_mapping = rf_cfg.get('class_mapping', {})
    class_to_id = {name: idx for idx, name in enumerate(component_class_names)}
    
    # Track all classes dynamically (including unmapped ones)
    all_classes_seen = set()
    next_dynamic_id = len(component_class_names)  # Start dynamic IDs after predefined ones
    
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source path not found: {source_path}")
        return 1
    
    output_dir = Path(args.output)
    ensure_dir(output_dir)
    
    if not args.no_annotated:
        annotated_dir = output_dir / 'annotated'
        ensure_dir(annotated_dir)
    
    if not args.no_json:
        json_dir = output_dir / 'json'
        ensure_dir(json_dir)
    
    # Process images
    if source_path.is_file():
        images = [source_path]
    else:
        images = get_image_paths(source_path)
    
    print(f"Processing {len(images)} image(s) using model API...\n")
    print(f"Model ID: {rf_cfg['model_id']}\n")
    print("Using ALL classes from model (no filtering)\n")
    
    all_results = []
    summary_stats = {
        'total_images': len(images),
        'total_detections': 0,
        'component_counts': {},  # Will be populated dynamically
        'model_class_counts': {}  # Count all model classes
    }
    
    for img_path in tqdm(images, desc="Processing"):
        # Load image
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        
        h, w = img.shape[:2]
        
        # Get predictions from model API
        try:
            api_response = api.predict_from_path(img_path, confidence=conf_threshold)
        except Exception as e:
            print(f"Error processing {img_path.name}: {e}")
            continue
        
        # Parse results
        detections_raw = api.parse_detection_results(api_response, w, h)
        
        detections = []
        for det in detections_raw:
            model_class = det['class']
            
            # Track all classes seen
            all_classes_seen.add(model_class)
            
            # Map model class to unified class name (use mapping if exists, otherwise use original)
            unified_class = class_mapping.get(model_class, model_class)
            
            # Get class ID (try unified class first, then assign dynamic ID if needed)
            class_id = class_to_id.get(unified_class, -1)
            if class_id == -1:
                # If not in mapping, assign a dynamic ID
                if unified_class not in class_to_id:
                    class_to_id[unified_class] = next_dynamic_id
                    next_dynamic_id += 1
                class_id = class_to_id[unified_class]
            
            # Count all classes
            if model_class not in summary_stats['model_class_counts']:
                summary_stats['model_class_counts'][model_class] = 0
            summary_stats['model_class_counts'][model_class] += 1
            
            # Count unified classes
            if unified_class not in summary_stats['component_counts']:
                summary_stats['component_counts'][unified_class] = 0
            summary_stats['component_counts'][unified_class] += 1
            
            bbox = tuple(det['bbox_xyxy'])
            confidence = det['confidence']
            
            detections.append({
                'component_class': unified_class,
                'component_class_id': class_id,
                'component_conf': float(confidence),
                'bbox_xyxy': list(bbox),
                'model_class': model_class  # Keep original class name
            })
        
        summary_stats['total_detections'] += len(detections)
        
        result = {
            'image_name': img_path.name,
            'width': w,
            'height': h,
            'detections': detections
        }
        all_results.append(result)
        
        # Save JSON
        if not args.no_json:
            json_path = json_dir / f"{img_path.stem}.json"
            save_json(result, json_path)
        
        # Save annotated image
        if not args.no_annotated:
            annotated_img = img.copy()
            for det in detections:
                bbox = tuple(det['bbox_xyxy'])
                component_class = det['component_class']
                label = f"{component_class} ({det['component_conf']:.2f})"
                # Use color based on class_id, cycle through colors if needed
                color = COMPONENT_COLORS[det['component_class_id'] % len(COMPONENT_COLORS)]
                annotated_img = draw_bbox(annotated_img, bbox, label, color, det['component_conf'])
            
            annotated_path = annotated_dir / img_path.name
            cv2.imwrite(str(annotated_path), annotated_img)
    
    # Save summary CSV
    if not args.no_csv:
        csv_path = output_dir / 'summary.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Image', 'Component', 'Model Class', 'Confidence'])
            for result in all_results:
                for det in result['detections']:
                    writer.writerow([
                        result['image_name'],
                        det['component_class'],
                        det.get('model_class', 'unknown'),
                        f"{det['component_conf']:.3f}"
                    ])
            writer.writerow([])
            writer.writerow(['Summary'])
            writer.writerow(['Total Images', summary_stats['total_images']])
            writer.writerow(['Total Detections', summary_stats['total_detections']])
            writer.writerow([])
            writer.writerow(['Model Class Counts (All Classes)'])
            for class_name, count in sorted(summary_stats['model_class_counts'].items()):
                writer.writerow([class_name, count])
            writer.writerow([])
            writer.writerow(['Unified Component Counts'])
            for component, count in sorted(summary_stats['component_counts'].items()):
                writer.writerow([component, count])
    
    # Save summary JSON
    summary_json_path = output_dir / 'summary.json'
    save_json(summary_stats, summary_json_path)
    
    print("\n" + "="*70)
    print("INFERENCE SUMMARY")
    print("="*70)
    print(f"Total images: {summary_stats['total_images']}")
    print(f"Total detections: {summary_stats['total_detections']}")
    print(f"\nAll model classes detected:")
    for class_name, count in sorted(summary_stats['model_class_counts'].items()):
        print(f"  {class_name}: {count}")
    print(f"\nUnified component counts:")
    for component, count in sorted(summary_stats['component_counts'].items()):
        print(f"  {component}: {count}")
    print(f"\nResults saved to: {output_dir}")
    
    return 0


if __name__ == '__main__':
    exit(main())
