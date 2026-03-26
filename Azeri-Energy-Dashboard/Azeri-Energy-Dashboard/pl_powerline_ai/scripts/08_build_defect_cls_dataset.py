"""Script 08: Build defect classification dataset from sorted crops."""

import argparse
from pathlib import Path
import shutil
import pandas as pd
from src.utils.io import load_yaml, ensure_dir, get_image_paths


def main():
    parser = argparse.ArgumentParser(
        description='Build defect classification dataset from sorted crops or CSV mapping'
    )
    parser.add_argument('--mode', type=str, required=True, choices=['manual', 'csv'],
                        help='Mode: manual (crops already sorted) or csv (use CSV mapping)')
    parser.add_argument('--crops-dir', type=str, default='outputs/crops/unlabeled',
                        help='Directory with unlabeled crops (for csv mode)')
    parser.add_argument('--source-dir', type=str, default='data/processed/cls_defects/all',
                        help='Directory with manually sorted crops (for manual mode)')
    parser.add_argument('--csv-path', type=str, default=None,
                        help='CSV file with crop_path,defect_label columns (for csv mode)')
    parser.add_argument('--output', type=str, default='data/processed/cls_defects',
                        help='Output directory for classification dataset')
    parser.add_argument('--defects-config', type=str, default='configs/defects.yaml')
    parser.add_argument('--create-splits', action='store_true',
                        help='Create train/val/test splits after building dataset')
    parser.add_argument('--train-ratio', type=float, default=0.7)
    parser.add_argument('--val-ratio', type=float, default=0.2)
    parser.add_argument('--test-ratio', type=float, default=0.1)
    
    args = parser.parse_args()
    
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
    output_dir = Path(args.output)
    all_dir = output_dir / 'all'
    ensure_dir(all_dir)
    
    # Create defect class directories
    for defect_class in defect_class_names:
        ensure_dir(all_dir / defect_class)
    
    if args.mode == 'manual':
        # Validate manually sorted structure
        source_dir = Path(args.source_dir)
        if not source_dir.exists():
            print(f"Error: Source directory not found: {source_dir}")
            return 1
        
        print(f"Validating manually sorted dataset: {source_dir}")
        
        for defect_class in defect_class_names:
            class_dir = source_dir / defect_class
            if class_dir.exists():
                images = get_image_paths(class_dir)
                print(f"  {defect_class}: {len(images)} images")
                
                # Copy to output
                dest_dir = all_dir / defect_class
                for img_path in images:
                    shutil.copy2(img_path, dest_dir / img_path.name)
        
        print(f"\n✓ Dataset built at: {all_dir}")
    
    else:  # csv mode
        if not args.csv_path:
            print("Error: --csv-path required for csv mode")
            return 1
        
        csv_path = Path(args.csv_path)
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}")
            return 1
        
        crops_dir = Path(args.crops_dir)
        
        # Read CSV
        df = pd.read_csv(csv_path)
        required_cols = ['crop_path', 'defect_label']
        if not all(col in df.columns for col in required_cols):
            print(f"Error: CSV must have columns: {required_cols}")
            return 1
        
        print(f"Processing {len(df)} crops from CSV...")
        
        for _, row in df.iterrows():
            crop_path = Path(row['crop_path'])
            defect_label = str(row['defect_label']).strip()
            
            if defect_label not in defect_class_names:
                print(f"Warning: Unknown defect label '{defect_label}', skipping")
                continue
            
            if not crop_path.exists():
                # Try relative to crops_dir
                crop_path = crops_dir / crop_path
                if not crop_path.exists():
                    print(f"Warning: Crop not found: {row['crop_path']}")
                    continue
            
            # Copy to appropriate class directory
            dest_dir = all_dir / defect_label
            dest_path = dest_dir / crop_path.name
            shutil.copy2(crop_path, dest_path)
        
        print(f"\n✓ Dataset built at: {all_dir}")
    
    # Create splits if requested
    if args.create_splits:
        print("\nCreating train/val/test splits...")
        from src.datasets.splits import split_classification_dataset
        
        split_classification_dataset(
            source_dir=all_dir,
            output_dir=output_dir,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio
        )
        print("✓ Splits created")
    
    print(f"\nClassification dataset ready at: {output_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
