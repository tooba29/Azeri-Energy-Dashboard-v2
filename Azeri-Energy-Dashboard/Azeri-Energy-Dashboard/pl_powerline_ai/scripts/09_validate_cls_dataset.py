"""Script 09: Validate classification dataset."""

import argparse
from pathlib import Path
from collections import defaultdict
from src.utils.io import load_yaml, save_json, get_image_paths
from src.utils.image_ops import is_valid_image


def main():
    parser = argparse.ArgumentParser(description='Validate classification dataset')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to classification dataset directory')
    parser.add_argument('--defects-config', type=str, default='configs/defects.yaml')
    parser.add_argument('--output-report', type=str, default='outputs/reports/cls_dataset_report.json')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        print(f"Error: Dataset directory not found: {dataset_dir}")
        return 1
    
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
    report = {
        'dataset_path': str(dataset_dir),
        'splits': {},
        'issues': [],
        'warnings': [],
        'fatal_issues': [],
        'summary': {}
    }
    
    splits = ['train', 'val', 'test', 'all']
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
            'corrupt_images': 0,
            'issues': []
        }
        
        for defect_class in defect_class_names:
            class_dir = split_dir / defect_class
            
            if not class_dir.exists():
                split_stats['empty_classes'].append(defect_class)
                continue
            
            images = get_image_paths(class_dir)
            valid_count = 0
            
            for img_path in images:
                if is_valid_image(img_path):
                    valid_count += 1
                else:
                    corrupt_images.append(str(img_path))
                    split_stats['corrupt_images'] += 1
                    split_stats['issues'].append(f"Corrupt image: {img_path.name}")
            
            split_stats['class_counts'][defect_class] = valid_count
            split_stats['images'] += valid_count
            class_counts[defect_class] += valid_count
            total_images += valid_count
        
        split_stats['class_counts'] = dict(split_stats['class_counts'])
        report['splits'][split] = split_stats
        
        if split_stats['empty_classes']:
            report['warnings'].append(f"Split '{split}': Empty classes: {', '.join(split_stats['empty_classes'])}")
    
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
                report['warnings'].append(f"Severe class imbalance: ratio = {imbalance_ratio:.1f}x")
    
    # Fatal issues
    if total_images == 0:
        report['fatal_issues'].append("No valid images found!")
    empty_classes = [name for name, count in class_counts.items() if count == 0]
    if empty_classes:
        report['fatal_issues'].append(f"Classes with no images: {', '.join(empty_classes)}")
    
    output_path = Path(args.output_report)
    save_json(report, output_path)
    
    print("\n" + "="*70)
    print("CLASSIFICATION DATASET VALIDATION REPORT")
    print("="*70)
    print(f"\nTotal images: {total_images}")
    print(f"Corrupt images: {len(corrupt_images)}")
    print(f"\nClass counts:")
    for class_name, count in sorted(class_counts.items()):
        print(f"  {class_name}: {count}")
    
    if report['fatal_issues']:
        print("\n" + "="*70)
        print("FATAL ISSUES - VALIDATION FAILED")
        print("="*70)
        for issue in report['fatal_issues']:
            print(f"  ✗ {issue}")
        print(f"\nReport saved to: {output_path}")
        return 1
    
    print("\n" + "="*70)
    print("✓ VALIDATION PASSED")
    print("="*70)
    print(f"\nReport saved to: {output_path}")
    return 0


if __name__ == '__main__':
    exit(main())
