"""Script 03: Validate unified YOLO detection dataset (CRITICAL - prevents loss=0.0000)."""

import argparse
from pathlib import Path
from collections import defaultdict
from src.utils.io import load_yaml, save_json, get_image_paths
from src.utils.image_ops import yolo_to_xyxy, is_valid_image


def read_yolo_label(label_path: Path) -> list:
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


def validate_yolo_coords(x_center, y_center, width, height):
    """Validate YOLO coordinates are within [0, 1] and dimensions > 0."""
    if not (0 <= x_center <= 1):
        return False
    if not (0 <= y_center <= 1):
        return False
    if not (0 < width <= 1):
        return False
    if not (0 < height <= 1):
        return False
    if not (0 <= x_center - width/2):
        return False
    if not (x_center + width/2 <= 1):
        return False
    if not (0 <= y_center - height/2):
        return False
    if not (y_center + height/2 <= 1):
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Validate unified YOLO detection dataset. '
                    'CRITICAL: This prevents loss=0.0000 by catching missing/empty labels.'
    )
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to unified YOLO dataset directory')
    parser.add_argument('--components-config', type=str, default='configs/components.yaml',
                        help='Path to components.yaml')
    parser.add_argument('--output-report', type=str, default='outputs/reports/detect_dataset_report.json',
                        help='Output path for validation report')
    parser.add_argument('--allow-empty', action='store_true',
                        help='Allow empty label files (default: False)')
    parser.add_argument('--max-empty-ratio', type=float, default=0.7,
                        help='Maximum ratio of empty labels (default: 0.7 = 70%%)')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    
    if not dataset_dir.exists():
        print(f"Error: Dataset directory does not exist: {dataset_dir}")
        return 1
    
    # Load components config
    components_config = load_yaml(args.components_config)
    class_names = components_config['names']
    num_classes = len(class_names)
    
    # Initialize report
    report = {
        'dataset_path': str(dataset_dir),
        'splits': {},
        'issues': [],
        'warnings': [],
        'fatal_issues': [],
        'summary': {}
    }
    
    # Validate each split
    splits = ['train', 'val', 'test']
    total_images = 0
    total_boxes = 0
    class_counts = defaultdict(int)
    empty_labels_count = 0
    invalid_coords_count = 0
    invalid_class_count = 0
    corrupt_images_count = 0
    missing_labels_count = 0
    
    for split in splits:
        split_dir = dataset_dir / split
        if not split_dir.exists():
            continue
        
        images_dir = split_dir / 'images'
        labels_dir = split_dir / 'labels'
        
        if not images_dir.exists() or not labels_dir.exists():
            report['warnings'].append(f"Split '{split}' missing images/ or labels/ directory")
            continue
        
        images = get_image_paths(images_dir)
        split_stats = {
            'images': len(images),
            'labels': 0,
            'boxes': 0,
            'empty_labels': 0,
            'missing_labels': 0,
            'corrupt_images': 0,
            'class_counts': defaultdict(int),
            'issues': []
        }
        
        for img_path in images:
            # Check if image is valid
            if not is_valid_image(img_path):
                split_stats['corrupt_images'] += 1
                corrupt_images_count += 1
                split_stats['issues'].append(f"Corrupt image: {img_path.name}")
                continue
            
            label_path = labels_dir / f"{img_path.stem}.txt"
            
            if not label_path.exists():
                split_stats['missing_labels'] += 1
                missing_labels_count += 1
                if not args.allow_empty:
                    split_stats['issues'].append(f"Missing label for {img_path.name}")
                continue
            
            split_stats['labels'] += 1
            annotations = read_yolo_label(label_path)
            
            if len(annotations) == 0:
                split_stats['empty_labels'] += 1
                empty_labels_count += 1
                if not args.allow_empty:
                    split_stats['issues'].append(f"Empty label file: {label_path.name}")
            else:
                # Get image dimensions for validation
                from src.utils.image_ops import get_image_size
                img_size = get_image_size(img_path)
                if img_size:
                    img_width, img_height = img_size
                else:
                    img_width, img_height = 640, 640  # Default fallback
                
                for class_id, x_center, y_center, width, height in annotations:
                    # Validate class ID
                    if class_id < 0 or class_id >= num_classes:
                        split_stats['issues'].append(
                            f"Invalid class_id {class_id} in {label_path.name} (max: {num_classes-1})"
                        )
                        invalid_class_count += 1
                        continue
                    
                    # Validate coordinates
                    if not validate_yolo_coords(x_center, y_center, width, height):
                        split_stats['issues'].append(
                            f"Invalid coordinates in {label_path.name}: "
                            f"x={x_center:.3f}, y={y_center:.3f}, w={width:.3f}, h={height:.3f}"
                        )
                        invalid_coords_count += 1
                        continue
                    
                    split_stats['boxes'] += 1
                    split_stats['class_counts'][class_names[class_id]] += 1
                    class_counts[class_names[class_id]] += 1
        
        total_images += split_stats['images']
        total_boxes += split_stats['boxes']
        
        # Convert defaultdict to regular dict for JSON
        split_stats['class_counts'] = dict(split_stats['class_counts'])
        report['splits'][split] = split_stats
        
        # Check for issues
        if split_stats['empty_labels'] > len(images) * args.max_empty_ratio:
            report['warnings'].append(
                f"Split '{split}': {split_stats['empty_labels']}/{len(images)} images have empty labels "
                f"(>{args.max_empty_ratio*100:.1f}%)"
            )
        
        if split_stats['boxes'] == 0:
            report['fatal_issues'].append(f"Split '{split}': No valid boxes found!")
    
    # Summary
    report['summary'] = {
        'total_images': total_images,
        'total_boxes': total_boxes,
        'empty_labels': empty_labels_count,
        'missing_labels': missing_labels_count,
        'corrupt_images': corrupt_images_count,
        'invalid_coords': invalid_coords_count,
        'invalid_class_ids': invalid_class_count,
        'class_counts': dict(class_counts)
    }
    
    # Check class imbalance
    if class_counts:
        max_count = max(class_counts.values())
        min_count = min(class_counts.values())
        if max_count > 0 and min_count > 0:
            imbalance_ratio = max_count / min_count
            if imbalance_ratio > 10:
                report['warnings'].append(
                    f"Severe class imbalance detected: ratio = {imbalance_ratio:.1f}x "
                    f"(max: {max_count}, min: {min_count})"
                )
    
    # Check for fatal issues
    if total_boxes == 0:
        report['fatal_issues'].append("FATAL: No valid boxes found in entire dataset! This will cause loss=0.0000")
    if total_boxes > 0:
        if invalid_coords_count > total_boxes * 0.1:
            report['fatal_issues'].append(f"FATAL: Too many invalid coordinates: {invalid_coords_count} (>10% of boxes)")
        if invalid_class_count > total_boxes * 0.1:
            report['fatal_issues'].append(f"FATAL: Too many invalid class IDs: {invalid_class_count} (>10% of boxes)")
    if missing_labels_count > total_images * 0.2:
        report['fatal_issues'].append(f"FATAL: Too many missing labels: {missing_labels_count} (>20% of images)")
    
    # Check empty label ratio
    if total_images > 0:
        empty_ratio = empty_labels_count / total_images
        if empty_ratio > args.max_empty_ratio:
            report['fatal_issues'].append(
                f"FATAL: Too many empty labels: {empty_labels_count}/{total_images} "
                f"({empty_ratio*100:.1f}% > {args.max_empty_ratio*100:.1f}%)"
            )
    
    # Save report
    output_path = Path(args.output_report)
    save_json(report, output_path)
    
    # Print summary table
    print("\n" + "="*70)
    print("DATASET VALIDATION REPORT")
    print("="*70)
    print(f"\nDataset: {dataset_dir}")
    print(f"\nSummary:")
    print(f"  Total images: {total_images}")
    print(f"  Total boxes: {total_boxes}")
    print(f"  Empty labels: {empty_labels_count}")
    print(f"  Missing labels: {missing_labels_count}")
    print(f"  Corrupt images: {corrupt_images_count}")
    print(f"  Invalid coordinates: {invalid_coords_count}")
    print(f"  Invalid class IDs: {invalid_class_count}")
    
    print(f"\nClass counts:")
    for class_name, count in sorted(class_counts.items()):
        print(f"  {class_name}: {count}")
    
    if report['warnings']:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report['warnings'][:10]:
            print(f"  ⚠ {warning}")
        if len(report['warnings']) > 10:
            print(f"  ... and {len(report['warnings']) - 10} more (see report)")
    
    if report['fatal_issues']:
        print(f"\n" + "="*70)
        print("FATAL ISSUES - DATASET VALIDATION FAILED")
        print("="*70)
        for issue in report['fatal_issues']:
            print(f"  ✗ {issue}")
        print("\n⚠️  DO NOT TRAIN until these issues are fixed!")
        print("   Training with this dataset will result in loss=0.0000")
        print(f"\nFull report saved to: {output_path}")
        return 1
    
    if report['issues']:
        print(f"\nIssues ({len(report['issues'])}):")
        print("Top 10 issues:")
        for i, issue in enumerate(report['issues'][:10], 1):
            print(f"  {i}. {issue}")
        if len(report['issues']) > 10:
            print(f"  ... and {len(report['issues']) - 10} more (see full report)")
    
    print("\n" + "="*70)
    print("✓ DATASET VALIDATION PASSED")
    print("="*70)
    print(f"\nReport saved to: {output_path}")
    return 0


if __name__ == '__main__':
    exit(main())
