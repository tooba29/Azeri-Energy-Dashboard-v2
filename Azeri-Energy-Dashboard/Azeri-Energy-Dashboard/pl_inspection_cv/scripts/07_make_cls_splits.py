"""Script 07: Create train/val/test splits for classification dataset."""

import argparse
from pathlib import Path
from src.utils.io import load_yaml, ensure_dir
from src.utils.dataset import split_classification_dataset


def main():
    parser = argparse.ArgumentParser(description='Create train/val/test splits for classification dataset')
    parser.add_argument('--source', type=str, required=True,
                        help='Source directory with class subdirectories (e.g., cls_dataset/all/normal/, cls_dataset/all/rust/)')
    parser.add_argument('--output', type=str, default='./cls_dataset',
                        help='Output directory for splits (default: ./cls_dataset)')
    parser.add_argument('--train-ratio', type=float, default=0.7,
                        help='Training set ratio (default: 0.7)')
    parser.add_argument('--val-ratio', type=float, default=0.2,
                        help='Validation set ratio (default: 0.2)')
    parser.add_argument('--test-ratio', type=float, default=0.1,
                        help='Test set ratio (default: 0.1)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed (default: 42)')
    parser.add_argument('--defects-config', type=str, default='./configs/defects.yaml',
                        help='Path to defects config YAML (default: ./configs/defects.yaml)')
    parser.add_argument('--no-test', action='store_true',
                        help='Skip test split (use train/val only)')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source)
    output_dir = Path(args.output)
    
    if not source_dir.exists():
        print(f"Error: Source directory does not exist: {source_dir}")
        return 1
    
    # Load defects config
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
    # Adjust ratios if no test
    test_ratio = 0.0 if args.no_test else args.test_ratio
    train_ratio = args.train_ratio
    val_ratio = args.val_ratio
    
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
        print(f"Error: Ratios must sum to 1.0 (got {train_ratio + val_ratio + test_ratio})")
        return 1
    
    print(f"Creating classification dataset splits:")
    print(f"  Source: {source_dir}")
    print(f"  Output: {output_dir}")
    print(f"  Train: {train_ratio*100:.1f}%%, Val: {val_ratio*100:.1f}%%, Test: {test_ratio*100:.1f}%")
    
    # Split dataset
    counts = split_classification_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        random_state=args.seed
    )
    
    # Print summary
    print("\n=== Split Summary ===")
    total_train = 0
    total_val = 0
    total_test = 0
    
    for defect_class, split_counts in counts.items():
        print(f"\n{defect_class}:")
        print(f"  Train: {split_counts['train']}")
        print(f"  Val: {split_counts['val']}")
        if not args.no_test:
            print(f"  Test: {split_counts['test']}")
        total_train += split_counts['train']
        total_val += split_counts['val']
        if not args.no_test:
            total_test += split_counts['test']
    
    print(f"\nTotal:")
    print(f"  Train: {total_train}")
    print(f"  Val: {total_val}")
    if not args.no_test:
        print(f"  Test: {total_test}")
    
    print(f"\nSplits created in: {output_dir}")
    print("Next step: Run script 08_validate_cls_dataset.py to validate the dataset")
    
    return 0


if __name__ == '__main__':
    exit(main())
