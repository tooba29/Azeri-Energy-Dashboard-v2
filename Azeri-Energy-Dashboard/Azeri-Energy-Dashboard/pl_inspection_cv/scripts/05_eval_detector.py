"""Script 05: Evaluate YOLO detector."""

import argparse
from pathlib import Path
from ultralytics import YOLO
from src.utils.io import load_yaml, save_json, ensure_dir


def main():
    parser = argparse.ArgumentParser(description='Evaluate YOLO detector (Stage A)')
    parser.add_argument('--weights', type=str, required=True,
                        help='Path to trained model weights (.pt file)')
    parser.add_argument('--data', type=str, required=True,
                        help='Path to dataset YAML (e.g., yolo_dataset/data.yaml)')
    parser.add_argument('--split', type=str, default='val', choices=['val', 'test'],
                        help='Split to evaluate on (default: val)')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='Image size for evaluation (default: 640)')
    parser.add_argument('--conf', type=float, default=0.001,
                        help='Confidence threshold (default: 0.001)')
    parser.add_argument('--iou', type=float, default=0.6,
                        help='IoU threshold for NMS (default: 0.6)')
    parser.add_argument('--output', type=str, default='./outputs/reports/detect_metrics.json',
                        help='Output path for metrics JSON (default: ./outputs/reports/detect_metrics.json)')
    
    args = parser.parse_args()
    
    weights_path = Path(args.weights)
    if not weights_path.exists():
        print(f"Error: Model weights not found: {weights_path}")
        return 1
    
    # Load model
    model = YOLO(str(weights_path))
    
    # Load dataset config
    data_config = load_yaml(args.data)
    
    print(f"Evaluating detector:")
    print(f"  Weights: {weights_path}")
    print(f"  Dataset: {args.data}")
    print(f"  Split: {args.split}")
    
    # Run validation
    results = model.val(
        data=args.data,
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        split=args.split
    )
    
    # Extract metrics
    metrics = {
        'model_path': str(weights_path),
        'dataset': args.data,
        'split': args.split,
        'metrics': {
            'mAP50': float(results.box.map50) if hasattr(results.box, 'map50') else None,
            'mAP50-95': float(results.box.map) if hasattr(results.box, 'map') else None,
            'precision': float(results.box.mp) if hasattr(results.box, 'mp') else None,
            'recall': float(results.box.mr) if hasattr(results.box, 'mr') else None,
        },
        'per_class': {}
    }
    
    # Per-class metrics
    if hasattr(results, 'names') and hasattr(results.box, 'maps'):
        class_names = results.names
        if hasattr(results.box.maps, '__iter__'):
            for i, class_name in class_names.items():
                if i < len(results.box.maps):
                    metrics['per_class'][class_name] = {
                        'mAP50': float(results.box.maps[i]) if i < len(results.box.maps) else None
                    }
    
    # Save metrics
    output_path = Path(args.output)
    ensure_dir(output_path.parent)
    save_json(metrics, output_path)
    
    print(f"\nEvaluation completed!")
    print(f"  mAP50: {metrics['metrics']['mAP50']:.4f}" if metrics['metrics']['mAP50'] else "  mAP50: N/A")
    print(f"  mAP50-95: {metrics['metrics']['mAP50-95']:.4f}" if metrics['metrics']['mAP50-95'] else "  mAP50-95: N/A")
    print(f"  Precision: {metrics['metrics']['precision']:.4f}" if metrics['metrics']['precision'] else "  Precision: N/A")
    print(f"  Recall: {metrics['metrics']['recall']:.4f}" if metrics['metrics']['recall'] else "  Recall: N/A")
    print(f"\nMetrics saved to: {output_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())
