"""Script 01: Create train/val/test splits for YOLO detection dataset."""

import argparse
from pathlib import Path
import shutil
from src.utils.io import load_yaml, save_yaml, get_image_paths, ensure_dir
from src.utils.dataset import split_dataset


def main():
    parser = argparse.ArgumentParser(description='Create train/val/test splits for YOLO detection dataset')
    parser.add_argument('--source', type=str, required=True,
                        help='Source directory with images and labels (flat structure)')
    parser.add_argument('--output', type=str, default='./yolo_dataset',
                        help='Output directory for splits (default: ./yolo_dataset)')
    parser.add_argument('--train-ratio', type=float, default=0.7,
                        help='Training set ratio (default: 0.7)')
    parser.add_argument('--val-ratio', type=float, default=0.2,
                        help='Validation set ratio (default: 0.2)')
    parser.add_argument('--test-ratio', type=float, default=0.1,
                        help='Test set ratio (default: 0.1)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed (default: 42)')
    parser.add_argument('--components-config', type=str, default='./configs/components.yaml',
                        help='Path to components config YAML (default: ./configs/components.yaml)')
    parser.add_argument('--no-test', action='store_true',
                        help='Skip test split (use train/val only)')
    
    args = parser.parse_args()
    
    source_dir = Path(args.source)
    output_dir = Path(args.output)
    
    if not source_dir.exists():
        print(f"Error: Source directory does not exist: {source_dir}")
        return 1
    
    # Load components config
    components_config = load_yaml(args.components_config)
    class_names = components_config['names']
    num_classes = len(class_names)
    
    # Create output structure
    for split in ['train', 'val']:
        ensure_dir(output_dir / split / 'images')
        ensure_dir(output_dir / split / 'labels')
    
    if not args.no_test:
        ensure_dir(output_dir / 'test' / 'images')
        ensure_dir(output_dir / 'test' / 'labels')
    
    # Get all images
    images = get_image_paths(source_dir)
    
    if not images:
        print(f"Error: No images found in {source_dir}")
        return 1
    
    # Find corresponding label files
    images_with_labels = []
    for img_path in images:
        label_path = source_dir / f"{img_path.stem}.txt"
        if label_path.exists():
            images_with_labels.append(img_path)
        else:
            print(f"Warning: No label file for {img_path.name}")
    
    print(f"Found {len(images_with_labels)} images with labels")
    
    # Split images
    from sklearn.model_selection import train_test_split
    
    test_ratio = 0.0 if args.no_test else args.test_ratio
    train_ratio = args.train_ratio
    val_ratio = args.val_ratio
    
    if not args.no_test:
        train_images, temp_images = train_test_split(
            images_with_labels,
            test_size=(val_ratio + test_ratio),
            random_state=args.seed
        )
        val_images, test_images = train_test_split(
            temp_images,
            test_size=test_ratio / (val_ratio + test_ratio),
            random_state=args.seed
        )
    else:
        train_images, val_images = train_test_split(
            images_with_labels,
            test_size=val_ratio,
            random_state=args.seed
        )
        test_images = []
    
    # Copy files
    def copy_image_and_label(img_path, split_name):
        # Copy image
        dest_img = output_dir / split_name / 'images' / img_path.name
        shutil.copy2(img_path, dest_img)
        
        # Copy label
        label_path = source_dir / f"{img_path.stem}.txt"
        dest_label = output_dir / split_name / 'labels' / label_path.name
        shutil.copy2(label_path, dest_label)
    
    for img in train_images:
        copy_image_and_label(img, 'train')
    
    for img in val_images:
        copy_image_and_label(img, 'val')
    
    for img in test_images:
        copy_image_and_label(img, 'test')
    
    print(f"Created splits:")
    print(f"  Train: {len(train_images)} images")
    print(f"  Val: {len(val_images)} images")
    if not args.no_test:
        print(f"  Test: {len(test_images)} images")
    
    # Generate data.yaml for YOLO
    data_yaml = {
        'path': str(output_dir.absolute()),
        'train': 'train/images',
        'val': 'val/images',
        'test': 'test/images' if not args.no_test else None,
        'nc': num_classes,
        'names': class_names
    }
    
    if args.no_test:
        del data_yaml['test']
    
    yaml_path = output_dir / 'data.yaml'
    save_yaml(data_yaml, yaml_path)
    print(f"\nGenerated YOLO dataset config: {yaml_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())
