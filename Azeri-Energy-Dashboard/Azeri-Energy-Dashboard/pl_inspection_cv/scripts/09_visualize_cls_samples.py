"""Script 09: Visualize classification samples."""

import argparse
from pathlib import Path
from src.utils.io import load_yaml
from src.utils.viz import visualize_classification_samples


def main():
    parser = argparse.ArgumentParser(description='Visualize classification dataset samples')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to classification dataset directory (with train/, val/, test/ subdirs)')
    parser.add_argument('--split', type=str, default='train', choices=['train', 'val', 'test'],
                        help='Split to visualize (default: train)')
    parser.add_argument('--output', type=str, default='./outputs/visualizations/cls',
                        help='Output directory for visualizations (default: ./outputs/visualizations/cls)')
    parser.add_argument('--defects-config', type=str, default='./configs/defects.yaml',
                        help='Path to defects config YAML (default: ./configs/defects.yaml)')
    parser.add_argument('--samples-per-class', type=int, default=5,
                        help='Number of samples per class to visualize (default: 5)')
    parser.add_argument('--grid-cols', type=int, default=5,
                        help='Number of columns in grid (default: 5)')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    split_dir = dataset_dir / args.split
    
    if not split_dir.exists():
        print(f"Error: Split directory does not exist: {split_dir}")
        return 1
    
    # Load defects config
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Visualizing classification samples from {args.split} split...")
    print(f"  Dataset: {split_dir}")
    print(f"  Output: {output_dir}")
    print(f"  Samples per class: {args.samples_per_class}")
    
    # Visualize
    visualize_classification_samples(
        dataset_dir=split_dir,
        output_dir=output_dir,
        samples_per_class=args.samples_per_class,
        grid_cols=args.grid_cols
    )
    
    print(f"\nVisualizations saved to: {output_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
