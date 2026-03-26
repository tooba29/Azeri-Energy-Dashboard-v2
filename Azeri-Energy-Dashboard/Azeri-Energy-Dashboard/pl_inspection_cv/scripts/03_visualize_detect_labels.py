"""Script 03: Visualize detection labels."""

import argparse
from pathlib import Path
from src.utils.io import load_yaml, get_image_paths
from src.utils.yolo import read_yolo_label, yolo_to_xyxy
from src.utils.viz import visualize_detections, COMPONENT_COLORS
import cv2


def main():
    parser = argparse.ArgumentParser(description='Visualize YOLO detection labels')
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to YOLO dataset directory (with train/, val/, test/ subdirs)')
    parser.add_argument('--split', type=str, default='train', choices=['train', 'val', 'test'],
                        help='Split to visualize (default: train)')
    parser.add_argument('--output', type=str, default='./outputs/visualizations/detect',
                        help='Output directory for visualizations (default: ./outputs/visualizations/detect)')
    parser.add_argument('--components-config', type=str, default='./configs/components.yaml',
                        help='Path to components config YAML (default: ./configs/components.yaml)')
    parser.add_argument('--max-images', type=int, default=50,
                        help='Maximum number of images to visualize (default: 50)')
    parser.add_argument('--sample', action='store_true',
                        help='Randomly sample images instead of taking first N')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    split_dir = dataset_dir / args.split
    
    if not split_dir.exists():
        print(f"Error: Split directory does not exist: {split_dir}")
        return 1
    
    images_dir = split_dir / 'images'
    labels_dir = split_dir / 'labels'
    
    if not images_dir.exists() or not labels_dir.exists():
        print(f"Error: Missing images/ or labels/ in {split_dir}")
        return 1
    
    # Load components config
    components_config = load_yaml(args.components_config)
    class_names = components_config['names']
    
    # Get images
    images = get_image_paths(images_dir)
    
    if not images:
        print(f"Error: No images found in {images_dir}")
        return 1
    
    # Sample if requested
    if args.sample:
        import random
        random.seed(42)
        images = random.sample(images, min(args.max_images, len(images)))
    else:
        images = images[:args.max_images]
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Visualizing {len(images)} images from {args.split} split...")
    
    for img_path in images:
        label_path = labels_dir / f"{img_path.stem}.txt"
        
        if not label_path.exists():
            print(f"Warning: No label for {img_path.name}")
            continue
        
        # Read image to get dimensions
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        
        h, w = img.shape[:2]
        
        # Read labels
        annotations = read_yolo_label(label_path)
        
        # Convert to detections format: (class_id, bbox, confidence)
        detections = []
        for class_id, x_center, y_center, width, height in annotations:
            bbox = yolo_to_xyxy(x_center, y_center, width, height, w, h)
            detections.append((class_id, bbox, None))  # None confidence for GT
        
        # Visualize
        output_path = output_dir / img_path.name
        visualize_detections(
            img_path,
            detections,
            class_names,
            COMPONENT_COLORS,
            output_path
        )
    
    print(f"Visualizations saved to: {output_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
