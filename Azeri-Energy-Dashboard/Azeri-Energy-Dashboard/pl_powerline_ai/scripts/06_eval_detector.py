"""Script 06: Evaluate Stage A detector."""

import argparse
from pathlib import Path
from ultralytics import YOLO
from src.utils.io import load_yaml, save_json, ensure_dir


def main():
    parser = argparse.ArgumentParser(description='Evaluate YOLO detector (Stage A)')
    parser.add_argument('--weights', type=str, required=True, help='Path to trained model weights')
    parser.add_argument('--data', type=str, required=True, help='Path to dataset YAML')
    parser.add_argument('--split', type=str, default='val', choices=['val', 'test'])
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--conf', type=float, default=0.001)
    parser.add_argument('--iou', type=float, default=0.6)
    parser.add_argument('--output', type=str, default='outputs/reports/detect_metrics.json')
    
    args = parser.parse_args()
    
    weights_path = Path(args.weights)
    if not weights_path.exists():
        print(f"Error: Model weights not found: {weights_path}")
        return 1
    
    model = YOLO(str(weights_path))
    
    print(f"Evaluating detector:")
    print(f"  Weights: {weights_path}")
    print(f"  Dataset: {args.data}")
    print(f"  Split: {args.split}\n")
    
    results = model.val(
        data=args.data,
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        split=args.split
    )
    
    metrics = {
        'model_path': str(weights_path),
        'dataset': args.data,
        'split': args.split,
        'metrics': {}
    }
    
    if hasattr(results, 'box'):
        if hasattr(results.box, 'map50'):
            metrics['metrics']['mAP50'] = float(results.box.map50)
        if hasattr(results.box, 'map'):
            metrics['metrics']['mAP50-95'] = float(results.box.map)
        if hasattr(results.box, 'mp'):
            metrics['metrics']['precision'] = float(results.box.mp)
        if hasattr(results.box, 'mr'):
            metrics['metrics']['recall'] = float(results.box.mr)
    
    output_path = Path(args.output)
    ensure_dir(output_path.parent)
    save_json(metrics, output_path)
    
    print(f"\nEvaluation completed!")
    if 'mAP50' in metrics['metrics']:
        print(f"  mAP50: {metrics['metrics']['mAP50']:.4f}")
    if 'mAP50-95' in metrics['metrics']:
        print(f"  mAP50-95: {metrics['metrics']['mAP50-95']:.4f}")
    print(f"\nMetrics saved to: {output_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())
