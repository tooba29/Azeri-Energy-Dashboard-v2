"""Script 04: Visualize detection labels."""

import argparse
from pathlib import Path
import random
from src.utils.io import load_yaml, get_image_paths
from src.utils.viz import visualize_detections, COMPONENT_COLORS
from src.utils.image_ops import yolo_to_xyxy, load_image


def read_yolo_label(label_path: Path):
    """Read YOLO format label file."""
    annotations = []
    if not label_path.exists():
        return annotations
    with open(label_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                class_id = int(parts[0])
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
                annotations.append((class_id, x_center, y_center, width, height))
            except ValueError:
                continue
    return annotations


def main():
    parser = argparse.ArgumentParser(description='Visualize detection labels')
    parser.add_argument('--dataset', type=str, required=True, help='Path to unified YOLO dataset')
    parser.add_argument('--split', type=str, default='train', choices=['train', 'val', 'test'])
    parser.add_argument('--output', type=str, default='outputs/reports/detect_label_viz')
    parser.add_argument('--components-config', type=str, default='configs/components.yaml')
    parser.add_argument('--max-images', type=int, default=50)
    parser.add_argument('--sample', action='store_true', help='Randomly sample images')
    parser.add_argument('--filter-class', type=int, default=None, help='Only show images with this class')
    parser.add_argument('--only-with-boxes', action='store_true', default=True,
                        help='Only visualize images with boxes (default: True)')
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    split_dir = dataset_dir / args.split
    images_dir = split_dir / 'images'
    labels_dir = split_dir / 'labels'
    
    if not images_dir.exists():
        print(f"Error: Images directory not found: {images_dir}")
        return 1
    
    components_config = load_yaml(args.components_config)
    class_names = components_config['names']
    
    # Handle --num alias
    max_images = args.num if args.num is not None else args.max_images
    
    images = get_image_paths(images_dir)
    if args.only_with_boxes:
        images = [img for img in images if (labels_dir / f"{img.stem}.txt").exists() and 
                 len(read_yolo_label(labels_dir / f"{img.stem}.txt")) > 0]
    
    if args.sample:
        random.seed(42)
        images = random.sample(images, min(max_images, len(images)))
    else:
        images = images[:max_images]
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Visualizing {len(images)} images from {args.split} split...")
    
    for img_path in images:
        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            continue
        
        img = load_image(img_path)
        if img is None:
            continue
        
        h, w = img.shape[:2]
        annotations = read_yolo_label(label_path)
        
        if args.filter_class is not None:
            annotations = [ann for ann in annotations if ann[0] == args.filter_class]
            if not annotations:
                continue
        
        detections = []
        for class_id, x_center, y_center, width, height in annotations:
            bbox = yolo_to_xyxy(x_center, y_center, width, height, w, h)
            detections.append((class_id, bbox, None))
        
        if detections:
            output_path = output_dir / img_path.name
            visualize_detections(img_path, detections, class_names, COMPONENT_COLORS, output_path)
    
    print(f"Visualizations saved to: {output_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
