"""Script 01: Register datasets in dataset_sources.yaml."""

import argparse
from pathlib import Path
from src.utils.io import load_yaml, save_yaml


def main():
    parser = argparse.ArgumentParser(
        description='Register datasets in dataset_sources.yaml. '
                    'This script helps you add dataset entries interactively.'
    )
    parser.add_argument('--name', type=str, required=True,
                        help='Dataset name (e.g., insplad_det)')
    parser.add_argument('--path', type=str, required=True,
                        help='Path to dataset root directory')
    parser.add_argument('--format', type=str, required=True,
                        choices=['yolo', 'coco', 'voc', 'custom'],
                        help='Annotation format')
    parser.add_argument('--images-dir', type=str, required=True,
                        help='Relative path to images directory (e.g., images, JPEGImages)')
    parser.add_argument('--labels-dir', type=str, default=None,
                        help='Relative path to labels directory (for YOLO format)')
    parser.add_argument('--ann-path', type=str, default=None,
                        help='Relative path to annotation file (for COCO format, e.g., annotations/instances.json)')
    parser.add_argument('--ann-dir', type=str, default=None,
                        help='Relative path to annotations directory (for VOC format, e.g., Annotations)')
    parser.add_argument('--max-images', type=int, default=None,
                        help='Maximum images to use (null = all)')
    parser.add_argument('--enabled', action='store_true', default=True,
                        help='Enable this dataset (default: True)')
    parser.add_argument('--config', type=str, default='configs/dataset_sources.yaml',
                        help='Path to dataset_sources.yaml')
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    
    # Load existing config
    if config_path.exists():
        config = load_yaml(config_path)
    else:
        config = {'datasets': []}
    
    # Validate format-specific arguments
    if args.format == 'yolo' and not args.labels_dir:
        print("Error: --labels-dir required for YOLO format")
        return 1
    if args.format == 'coco' and not args.ann_path:
        print("Error: --ann-path required for COCO format")
        return 1
    if args.format == 'voc' and not args.ann_dir:
        print("Error: --ann-dir required for VOC format")
        return 1
    
    # Check if dataset already exists
    existing_names = [ds['name'] for ds in config.get('datasets', [])]
    if args.name in existing_names:
        print(f"Warning: Dataset '{args.name}' already exists. Updating...")
        # Remove existing entry
        config['datasets'] = [ds for ds in config['datasets'] if ds['name'] != args.name]
    
    # Create dataset entry
    dataset_entry = {
        'name': args.name,
        'path': args.path,
        'format': args.format,
        'images_dir': args.images_dir,
        'enabled': args.enabled,
        'max_images': args.max_images
    }
    
    if args.format == 'yolo':
        dataset_entry['labels_dir'] = args.labels_dir
    elif args.format == 'coco':
        dataset_entry['ann_path'] = args.ann_path
    elif args.format == 'voc':
        dataset_entry['ann_dir'] = args.ann_dir
    
    # Add to config
    if 'datasets' not in config:
        config['datasets'] = []
    config['datasets'].append(dataset_entry)
    
    # Save config
    save_yaml(config, config_path)
    
    print(f"✓ Registered dataset '{args.name}' in {config_path}")
    print(f"  Path: {args.path}")
    print(f"  Format: {args.format}")
    
    return 0


if __name__ == '__main__':
    exit(main())
