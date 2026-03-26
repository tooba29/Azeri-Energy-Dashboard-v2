"""Script 08: Validate classification dataset."""

import argparse
from pathlib import Path
from collections import defaultdict
from src.utils.io import load_yaml, save_json, get_image_paths
import cv2


def main():
    parser = argparse.ArgumentParser(description='Validate classification dataset')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to classification dataset directory (with train/, val/, test/ subdirs)')
    parser.add_argument('--defects-config', type=str, default='./configs/defects.yaml',
                        help='Path to defects config YAML (default: ./configs/defects.yaml)')
    parser.add_argument('--output-report', type=str, default='./outputs/reports/cls_dataset_report.json',
                        help='Output path for validation report (default: ./outputs/reports/cls_dataset_report.json)')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    
    if not dataset_dir.exists():
        print(f"Error: Dataset directory does not exist: {dataset_dir}")
        return 1
    
    # Load defects config
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
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
    class_counts = defaultdict(int)
    corrupt_images = []
    
    for split in splits:
        split_dir = dataset_dir / split
        if not split_dir.exists():
            continue
        
        split_stats = {
            'images': 0,
            'class_counts': defaultdict(int),
            'empty_classes': [],
            'issues': []
        }
        
        # Check each class directory
        for defect_class in defect_class_names:
            class_dir = split_dir / defect_class
            
            if not class_dir.exists():
                split_stats['empty_classes'].append(defect_class)
                split_stats['issues'].append(f"Missing directory for class '{defect_class}'")
                continue
            
            images = get_image_paths(class_dir)
            
            if len(images) == 0:
                split_stats['empty_classes'].append(defect_class)
                split_stats['warnings'] = split_stats.get('warnings', [])
                split_stats['warnings'].append(f"Empty class directory: {defect_class}")
            
            # Validate images
            valid_images = 0
            for img_path in images:
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        corrupt_images.append(str(img_path))
                        split_stats['issues'].append(f"Corrupt image: {img_path.name}")
                    else:
                        valid_images += 1
                except Exception as e:
                    corrupt_images.append(str(img_path))
                    split_stats['issues'].append(f"Error reading {img_path.name}: {str(e)}")
            
            split_stats['class_counts'][defect_class] = valid_images
            split_stats['images'] += valid_images
            class_counts[defect_class] += valid_images
            total_images += valid_images
        
        # Convert defaultdict to regular dict
        split_stats['class_counts'] = dict(split_stats['class_counts'])
        report['splits'][split] = split_stats
        
        # Check for issues
        if split_stats['empty_classes']:
            report['warnings'].append(
                f"Split '{split}': Empty classes: {', '.join(split_stats['empty_classes'])}"
            )
    
    # Summary
    report['summary'] = {
        'total_images': total_images,
        'class_counts': dict(class_counts),
        'corrupt_images': len(corrupt_images)
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
    fatal_issues = []
    if total_images == 0:
        fatal_issues.append("No valid images found in entire dataset!")
    if len(corrupt_images) > total_images * 0.1:
        fatal_issues.append(f"Too many corrupt images: {len(corrupt_images)} (>10% of total)")
    
    # Check if all classes have at least some images
    empty_classes = [name for name, count in class_counts.items() if count == 0]
    if empty_classes:
        fatal_issues.append(f"Classes with no images: {', '.join(empty_classes)}")
    
    report['fatal_issues'] = fatal_issues
    
    # Save report
    output_path = Path(args.output_report)
    save_json(report, output_path)
    print(f"Validation report saved to: {output_path}")
    
    # Print summary
    print("\n=== Classification Dataset Validation Summary ===")
    print(f"Total images: {total_images}")
    print(f"Corrupt images: {len(corrupt_images)}")
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
