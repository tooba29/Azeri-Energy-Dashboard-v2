"""Script 01b: List available labels in datasets (helper for label_mapping.yaml)."""

import argparse
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from src.utils.io import load_yaml, get_image_paths


def list_coco_labels(dataset_path: Path, ann_path: str):
    """List labels from COCO format dataset."""
    ann_file = dataset_path / ann_path
    if not ann_file.exists():
        return None
    
    with open(ann_file, 'r', encoding='utf-8') as f:
        coco_data = json.load(f)
    
    categories = coco_data.get('categories', [])
    labels = {}
    for cat in categories:
        labels[cat['name']] = cat.get('id', None)
    
    return labels


def list_voc_labels(dataset_path: Path, ann_dir: str):
    """List labels from VOC format dataset."""
    ann_path = dataset_path / ann_dir
    if not ann_path.exists():
        return None
    
    labels = set()
    xml_files = list(ann_path.glob('*.xml'))
    
    for xml_file in xml_files[:100]:  # Sample first 100
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            for obj in root.findall('object'):
                name = obj.find('name')
                if name is not None:
                    labels.add(name.text)
        except Exception:
            continue
    
    return {label: None for label in sorted(labels)}


def list_yolo_labels(dataset_path: Path, labels_dir: str, images_dir: str):
    """List labels from YOLO format dataset."""
    labels_path = dataset_path / labels_dir
    images_path = dataset_path / images_dir
    
    if not labels_path.exists():
        return None
    
    # Try to find a class names file
    class_file = dataset_path / 'classes.txt'
    if class_file.exists():
        with open(class_file, 'r') as f:
            class_names = [line.strip() for line in f if line.strip()]
        return {name: idx for idx, name in enumerate(class_names)}
    
    # Otherwise, scan label files for class IDs
    class_ids = set()
    label_files = list(labels_path.glob('*.txt'))[:100]  # Sample first 100
    
    for label_file in label_files:
        try:
            with open(label_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_ids.add(int(parts[0]))
        except Exception:
            continue
    
    if class_ids:
        # Return as class_0, class_1, etc. (user needs to map these)
        return {f"class_{cid}": cid for cid in sorted(class_ids)}
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='List available labels in registered datasets. '
                    'Use this output to fill configs/label_mapping.yaml'
    )
    parser.add_argument('--dataset-sources', type=str, default='configs/dataset_sources.yaml',
                        help='Path to dataset_sources.yaml')
    parser.add_argument('--dataset-name', type=str, default=None,
                        help='Specific dataset name to list (default: all enabled datasets)')
    
    args = parser.parse_args()
    
    dataset_sources = load_yaml(args.dataset_sources)
    datasets = dataset_sources.get('datasets', [])
    
    if args.dataset_name:
        datasets = [ds for ds in datasets if ds['name'] == args.dataset_name]
    else:
        datasets = [ds for ds in datasets if ds.get('enabled', True)]
    
    if not datasets:
        print("No datasets found. Check dataset_sources.yaml")
        return 1
    
    print("="*70)
    print("DATASET LABEL DISCOVERY")
    print("="*70)
    print("\nUse this information to fill configs/label_mapping.yaml\n")
    
    for dataset_config in datasets:
        dataset_name = dataset_config['name']
        dataset_path = Path(dataset_config['path'])
        dataset_format = dataset_config['format']
        
        print(f"\nDataset: {dataset_name}")
        print(f"  Path: {dataset_path}")
        print(f"  Format: {dataset_format}")
        
        if not dataset_path.exists():
            print(f"  ⚠️  Path does not exist!")
            continue
        
        labels = None
        
        if dataset_format == 'coco':
            labels = list_coco_labels(dataset_path, dataset_config['ann_path'])
        elif dataset_format == 'voc':
            labels = list_voc_labels(dataset_path, dataset_config['ann_dir'])
        elif dataset_format == 'yolo':
            labels = list_yolo_labels(
                dataset_path,
                dataset_config['labels_dir'],
                dataset_config['images_dir']
            )
        else:
            print(f"  ⚠️  Format '{dataset_format}' not supported for label discovery")
            continue
        
        if labels is None:
            print(f"  ⚠️  Could not read labels (check paths in dataset_sources.yaml)")
            continue
        
        if not labels:
            print(f"  ⚠️  No labels found")
            continue
        
        print(f"  Available labels ({len(labels)}):")
        for label_name, label_id in sorted(labels.items()):
            if label_id is not None:
                print(f"    '{label_name}' (ID: {label_id})")
            else:
                print(f"    '{label_name}'")
        
        # Suggest mapping
        print(f"\n  Suggested mapping for label_mapping.yaml:")
        print(f"    {dataset_name}:")
        for label_name in sorted(labels.keys()):
            # Try to suggest a mapping based on name similarity
            label_lower = label_name.lower()
            suggestion = None
            if 'glass' in label_lower and 'insulator' in label_lower:
                suggestion = "glass_insulator"
            elif 'polymer' in label_lower and 'insulator' in label_lower:
                suggestion = "polymer_insulator"
            elif 'yoke' in label_lower:
                suggestion = "yoke_suspension"
            elif 'clamp' in label_lower:
                suggestion = "clamp"
            elif 'vari' in label_lower or 'grip' in label_lower:
                suggestion = "vari_grip"
            elif 'lightning' in label_lower or 'rod' in label_lower:
                suggestion = "lightning_rod_suspension"
            
            if suggestion:
                print(f"      \"{label_name}\": \"{suggestion}\"")
            else:
                print(f"      \"{label_name}\": null  # TODO: Map to unified class or ignore")
    
    print("\n" + "="*70)
    print("\nNext steps:")
    print("1. Copy the suggested mappings above")
    print("2. Edit configs/label_mapping.yaml")
    print("3. Map all labels to unified classes (or null to ignore)")
    print("4. Run: python scripts/02_convert_to_unified_detect_yolo.py")
    print("="*70)
    
    return 0


if __name__ == '__main__':
    exit(main())
