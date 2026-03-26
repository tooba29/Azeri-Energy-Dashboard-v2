"""Script 02: Convert all registered datasets to unified YOLO detection format."""

import argparse
from pathlib import Path
from tqdm import tqdm
from src.utils.io import load_yaml, save_yaml, ensure_dir
from src.converters.coco_to_yolo import convert_coco_dataset
from src.converters.voc_to_yolo import convert_voc_dataset
from src.converters.yolo_to_yolo import convert_yolo_dataset


def main():
    parser = argparse.ArgumentParser(
        description='Convert all registered datasets to unified YOLO detection format'
    )
    parser.add_argument('--dataset-sources', type=str, default='configs/dataset_sources.yaml',
                        help='Path to dataset_sources.yaml')
    parser.add_argument('--label-mapping', type=str, default='configs/label_mapping.yaml',
                        help='Path to label_mapping.yaml')
    parser.add_argument('--components-config', type=str, default='configs/components.yaml',
                        help='Path to components.yaml')
    parser.add_argument('--output', type=str, default='data/processed/detect_yolo',
                        help='Output directory for unified dataset')
    parser.add_argument('--skip-splits', action='store_true',
                        help='Skip creating train/val/test splits (assume already split)')
    parser.add_argument('--quick', action='store_true',
                        help='Quick mode: limit to 500 images per dataset for testing')
    
    args = parser.parse_args()
    
    # Load configs
    dataset_sources = load_yaml(args.dataset_sources)
    components_config = load_yaml(args.components_config)
    
    dataset_sources_path = Path(args.dataset_sources)
    label_mapping_path = Path(args.label_mapping)
    components_config_path = Path(args.components_config)
    output_dir = Path(args.output)
    
    # Create output structure
    all_labels_dir = output_dir / "all" / "labels"
    all_images_dir = output_dir / "all" / "images"
    ensure_dir(all_labels_dir)
    ensure_dir(all_images_dir)
    
    # Process each dataset
    datasets = dataset_sources.get('datasets', [])
    enabled_datasets = [ds for ds in datasets if ds.get('enabled', True)]
    
    if not enabled_datasets:
        print("No enabled datasets found. Check dataset_sources.yaml")
        return 1
    
    print(f"Converting {len(enabled_datasets)} dataset(s) to unified YOLO format...\n")
    
    all_stats = {}
    
    for dataset_config in tqdm(enabled_datasets, desc="Datasets"):
        dataset_name = dataset_config['name']
        dataset_path = Path(dataset_config['path'])
        dataset_format = dataset_config['format']
        max_images = dataset_config.get('max_images')
        
        # Quick mode: limit to 500 images
        if args.quick and (max_images is None or max_images > 500):
            max_images = 500
            print(f"  Quick mode: limiting to {max_images} images")
        
        if not dataset_path.exists():
            print(f"\nWarning: Dataset path does not exist: {dataset_path}")
            print(f"  Skipping dataset: {dataset_name}")
            continue
        
        print(f"\nProcessing: {dataset_name} ({dataset_format})")
        
        try:
            if dataset_format == 'yolo':
                stats = convert_yolo_dataset(
                    dataset_path=dataset_path,
                    images_dir=dataset_config['images_dir'],
                    labels_dir=dataset_config['labels_dir'],
                    output_dir=all_labels_dir,
                    dataset_name=dataset_name,
                    mapping_config_path=label_mapping_path,
                    components_config_path=components_config_path,
                    max_images=max_images
                )
            elif dataset_format == 'coco':
                stats = convert_coco_dataset(
                    dataset_path=dataset_path,
                    images_dir=dataset_config['images_dir'],
                    ann_path=dataset_config['ann_path'],
                    output_dir=all_labels_dir,
                    dataset_name=dataset_name,
                    mapping_config_path=label_mapping_path,
                    components_config_path=components_config_path,
                    max_images=max_images
                )
            elif dataset_format == 'voc':
                stats = convert_voc_dataset(
                    dataset_path=dataset_path,
                    images_dir=dataset_config['images_dir'],
                    ann_dir=dataset_config['ann_dir'],
                    output_dir=all_labels_dir,
                    dataset_name=dataset_name,
                    mapping_config_path=label_mapping_path,
                    components_config_path=components_config_path,
                    max_images=max_images
                )
            else:
                print(f"  Error: Unsupported format '{dataset_format}' for {dataset_name}")
                print(f"  Add a converter in src/converters/ or set format to 'custom'")
                continue
            
            all_stats[dataset_name] = stats
            print(f"  ✓ Converted: {stats['converted_images']} images, "
                  f"{stats['mapped_boxes']} boxes mapped, "
                  f"{stats['ignored_boxes']} boxes ignored")
        
        except Exception as e:
            print(f"  ✗ Error converting {dataset_name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Create splits if needed
    if not args.skip_splits:
        print("\nCreating train/val/test splits...")
        from src.datasets.splits import split_dataset
        
        default_splits = dataset_sources.get('default_splits', {
            'train': 0.7,
            'val': 0.2,
            'test': 0.1
        })
        
        split_dataset(
            source_dir=all_images_dir,
            train_dir=output_dir / "train",
            val_dir=output_dir / "val",
            test_dir=output_dir / "test",
            train_ratio=default_splits['train'],
            val_ratio=default_splits['val'],
            test_ratio=default_splits['test']
        )
        print("  ✓ Splits created")
    
    # Generate data.yaml
    class_names = components_config['names']
    data_yaml = {
        'path': str(output_dir.absolute()),
        'train': 'train/images',
        'val': 'val/images',
        'test': 'test/images',
        'nc': len(class_names),
        'names': class_names
    }
    
    yaml_path = output_dir / 'data.yaml'
    save_yaml(data_yaml, yaml_path)
    print(f"\n✓ Generated YOLO dataset config: {yaml_path}")
    
    # Print summary
    print("\n" + "="*70)
    print("CONVERSION SUMMARY")
    print("="*70)
    total_images = sum(s['converted_images'] for s in all_stats.values())
    total_boxes = sum(s['mapped_boxes'] for s in all_stats.values())
    total_labels = sum(s.get('labels', s['converted_images']) for s in all_stats.values())
    
    print(f"\nTotal images converted: {total_images}")
    print(f"Total labels created: {total_labels}")
    print(f"Total boxes mapped: {total_boxes}")
    
    # Per-class box counts
    from collections import defaultdict
    class_box_counts = defaultdict(int)
    # Note: We can't easily get per-class counts here without re-reading labels
    # But we can at least show per-dataset stats
    
    print(f"\nPer-dataset breakdown:")
    for dataset_name, stats in all_stats.items():
        print(f"  {dataset_name}:")
        print(f"    Images: {stats['converted_images']}")
        print(f"    Boxes mapped: {stats['mapped_boxes']}")
        print(f"    Boxes ignored: {stats['ignored_boxes']}")
    
    print(f"\nUnified dataset saved to: {output_dir}")
    
    # CRITICAL CHECK: If total boxes == 0, exit with error
    if total_boxes == 0:
        print("\n" + "="*70)
        print("⚠️  FATAL ERROR: No boxes were mapped!")
        print("="*70)
        print("\nThis usually means:")
        print("  1. Labels in datasets don't match entries in label_mapping.yaml")
        print("  2. All labels were ignored (mapped to null)")
        print("  3. Dataset annotation format is incorrect")
        print("\nAction required:")
        print("  1. Run: python scripts/01b_list_dataset_labels.py")
        print("  2. Check available labels in your datasets")
        print("  3. Update configs/label_mapping.yaml to map those labels")
        print("  4. Re-run this conversion script")
        print("\nDO NOT PROCEED TO TRAINING - dataset has no valid boxes!")
        return 1
    
    if total_boxes < 100:
        print(f"\n⚠️  WARNING: Very few boxes ({total_boxes}). Consider:")
        print("  - Checking label_mapping.yaml for missing mappings")
        print("  - Verifying dataset annotation files are correct")
    
    print("\n" + "="*70)
    return 0


if __name__ == '__main__':
    exit(main())
