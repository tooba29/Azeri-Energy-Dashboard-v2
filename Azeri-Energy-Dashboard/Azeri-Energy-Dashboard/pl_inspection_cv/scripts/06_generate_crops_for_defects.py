"""Script 06: Generate crops for defect labeling (CRITICAL for dataset building)."""

import argparse
from pathlib import Path
from src.utils.io import load_yaml, ensure_dir
from src.utils.crops import generate_crops_from_yolo_labels, generate_crops_from_predictions


def main():
    parser = argparse.ArgumentParser(
        description='Generate component crops for defect labeling. '
                    'This is a CRITICAL script for building the defect classification dataset.'
    )
    parser.add_argument('--from', type=str, required=True, choices=['gt', 'pred'],
                        dest='source_type',
                        help='Source type: "gt" for ground-truth labels, "pred" for detector predictions')
    parser.add_argument('--images', type=str, required=True,
                        help='Directory with images')
    parser.add_argument('--labels', type=str, default=None,
                        help='Directory with YOLO labels (required if --from=gt)')
    parser.add_argument('--detector-weights', type=str, default=None,
                        help='Path to detector weights .pt file (required if --from=pred)')
    parser.add_argument('--output', type=str, default='./outputs/crops/unlabeled',
                        help='Output directory for crops (default: ./outputs/crops/unlabeled)')
    parser.add_argument('--components-config', type=str, default='./configs/components.yaml',
                        help='Path to components config YAML (default: ./configs/components.yaml)')
    parser.add_argument('--padding-ratio', type=float, default=0.1,
                        help='Padding ratio around crops (default: 0.1 = 10%%)')
    parser.add_argument('--min-box-size', type=int, default=32,
                        help='Minimum box size in pixels (default: 32)')
    parser.add_argument('--balance-classes', action='store_true',
                        help='Balance number of crops per component class (use minimum count)')
    parser.add_argument('--conf-threshold', type=float, default=0.25,
                        help='Confidence threshold for predictions (default: 0.25, only for --from=pred)')
    parser.add_argument('--iou-threshold', type=float, default=0.45,
                        help='IoU threshold for NMS (default: 0.45, only for --from=pred)')
    
    args = parser.parse_args()
    
    images_dir = Path(args.images)
    if not images_dir.exists():
        print(f"Error: Images directory does not exist: {images_dir}")
        return 1
    
    # Load components config
    components_config = load_yaml(args.components_config)
    component_class_names = components_config['names']
    
    output_dir = Path(args.output)
    ensure_dir(output_dir)
    
    print(f"Generating crops from {args.source_type}...")
    print(f"  Images: {images_dir}")
    print(f"  Output: {output_dir}")
    print(f"  Component classes: {len(component_class_names)}")
    
    if args.source_type == 'gt':
        # Generate from ground-truth labels
        if args.labels is None:
            print("Error: --labels required when --from=gt")
            return 1
        
        labels_dir = Path(args.labels)
        if not labels_dir.exists():
            print(f"Error: Labels directory does not exist: {labels_dir}")
            return 1
        
        print(f"  Labels: {labels_dir}")
        
        crop_counts = generate_crops_from_yolo_labels(
            images_dir=images_dir,
            labels_dir=labels_dir,
            output_dir=output_dir,
            component_class_names=component_class_names,
            padding_ratio=args.padding_ratio,
            min_box_size=args.min_box_size,
            balance_classes=args.balance_classes
        )
    
    else:  # pred
        # Generate from detector predictions
        if args.detector_weights is None:
            print("Error: --detector-weights required when --from=pred")
            return 1
        
        detector_weights = Path(args.detector_weights)
        if not detector_weights.exists():
            print(f"Error: Detector weights not found: {detector_weights}")
            return 1
        
        print(f"  Detector: {detector_weights}")
        print(f"  Conf threshold: {args.conf_threshold}")
        print(f"  IoU threshold: {args.iou_threshold}")
        
        crop_counts = generate_crops_from_predictions(
            images_dir=images_dir,
            detector_model_path=detector_weights,
            output_dir=output_dir,
            component_class_names=component_class_names,
            conf_threshold=args.conf_threshold,
            iou_threshold=args.iou_threshold,
            padding_ratio=args.padding_ratio,
            min_box_size=args.min_box_size,
            balance_classes=args.balance_classes
        )
    
    # Print summary
    print("\n=== Crop Generation Summary ===")
    total_crops = 0
    for component_class, count in crop_counts.items():
        print(f"  {component_class}: {count} crops")
        total_crops += count
    print(f"\nTotal: {total_crops} crops generated")
    
    print(f"\nCrops saved to: {output_dir}")
    print("\nNext steps:")
    print("1. Manually sort crops into defect folders:")
    print("   cls_dataset/train/normal/")
    print("   cls_dataset/train/rust/")
    print("   cls_dataset/train/broken/")
    print("   cls_dataset/train/missing_part/")
    print("   cls_dataset/train/pollution_flashover/")
    print("2. Run script 07_make_cls_splits.py to create train/val/test splits")
    
    return 0


if __name__ == '__main__':
    exit(main())
