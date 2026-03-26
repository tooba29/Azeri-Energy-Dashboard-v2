"""Script 02: Validate YOLO detection dataset."""

import argparse
from pathlib import Path
from collections import defaultdict
from src.utils.io import load_yaml, save_json, get_image_paths
from src.utils.yolo import read_yolo_label, validate_yolo_coords


def main():
    parser = argparse.ArgumentParser(description='Validate YOLO detection dataset')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to YOLO dataset directory (with train/, val/, test/ subdirs)')
    parser.add_argument('--components-config', type=str, default='./configs/components.yaml',
                        help='Path to components config YAML (default: ./configs/components.yaml)')
    parser.add_argument('--output-report', type=str, default='./outputs/reports/detect_dataset_report.json',
                        help='Output path for validation report (default: ./outputs/reports/detect_dataset_report.json)')
    
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
            'class_counts': defaultdict(int),
            'issues': []
        }
        
        for img_path in images:
            label_path = labels_dir / f"{img_path.stem}.txt"
            
            if not label_path.exists():
                split_stats['issues'].append(f"Missing label for {img_path.name}")
                continue
            
            split_stats['labels'] += 1
            annotations = read_yolo_label(label_path)
            
            if len(annotations) == 0:
                split_stats['empty_labels'] += 1
                empty_labels_count += 1
            else:
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
        if split_stats['empty_labels'] > len(images) * 0.5:
            report['warnings'].append(
                f"Split '{split}': {split_stats['empty_labels']}/{len(images)} images have empty labels (>50%)"
            )
        
        if split_stats['boxes'] == 0:
            report['issues'].append(f"Split '{split}': No valid boxes found!")
    
    # Summary
    report['summary'] = {
        'total_images': total_images,
        'total_boxes': total_boxes,
        'empty_labels': empty_labels_count,
        'invalid_coords': invalid_coords_count,
        'invalid_class_ids': invalid_class_count,
        'class_counts': dict(class_counts)
    }
    
    # Check class imbalance
    if class_counts:
        max_count = max(class_counts.values())
        min_count = min(class_counts.values())
        if max_count > 0:
            imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
            if imbalance_ratio > 10:
                report['warnings'].append(
                    f"Severe class imbalance detected: ratio = {imbalance_ratio:.1f}x "
                    f"(max: {max_count}, min: {min_count})"
                )
    
    # Check for fatal issues
    fatal_issues = []
    if total_boxes == 0:
        fatal_issues.append("No valid boxes found in entire dataset!")
    if invalid_coords_count > total_boxes * 0.1:
        fatal_issues.append(f"Too many invalid coordinates: {invalid_coords_count} (>10% of boxes)")
    if invalid_class_count > total_boxes * 0.1:
        fatal_issues.append(f"Too many invalid class IDs: {invalid_class_count} (>10% of boxes)")
    
    report['fatal_issues'] = fatal_issues
    
    # Save report
    output_path = Path(args.output_report)
    save_json(report, output_path)
    print(f"Validation report saved to: {output_path}")
    
    # Print summary
    print("\n=== Dataset Validation Summary ===")
    print(f"Total images: {total_images}")
    print(f"Total boxes: {total_boxes}")
    print(f"Empty labels: {empty_labels_count}")
    print(f"Invalid coordinates: {invalid_coords_count}")
    print(f"Invalid class IDs: {invalid_class_count}")
    print(f"\nClass counts:")
    for class_name, count in sorted(class_counts.items()):
        print(f"  {class_name}: {count}")
    
    if report['warnings']:
        print(f"\nWarnings ({len(report['warnings'])}):")
        for warning in report['warnings']:
            print(f"  - {warning}")
    
    if fatal_issues:
        print(f"\nFATAL ISSUES ({len(fatal_issues)}):")
        for issue in fatal_issues:
            print(f"  - {issue}")
        print("\nDataset validation FAILED. Please fix issues before training.")
        return 1
    
    if report['issues']:
        print(f"\nIssues ({len(report['issues'])}):")
        for issue in report['issues'][:10]:  # Show first 10
            print(f"  - {issue}")
        if len(report['issues']) > 10:
            print(f"  ... and {len(report['issues']) - 10} more (see report)")
    
    print("\nDataset validation PASSED.")
    return 0


if __name__ == '__main__':
    exit(main())
