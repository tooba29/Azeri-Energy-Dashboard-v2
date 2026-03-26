"""Script 10: Visualize classification samples."""

import argparse
from pathlib import Path
import random
import cv2
import numpy as np
from src.utils.io import load_yaml, get_image_paths, ensure_dir


def main():
    parser = argparse.ArgumentParser(description='Visualize classification samples')
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--split', type=str, default='train', choices=['train', 'val', 'test', 'all'])
    parser.add_argument('--output', type=str, default='outputs/reports/cls_samples_viz')
    parser.add_argument('--defects-config', type=str, default='configs/defects.yaml')
    parser.add_argument('--samples-per-class', type=int, default=5)
    parser.add_argument('--grid-cols', type=int, default=5)
    
    args = parser.parse_args()
    
    dataset_dir = Path(args.dataset)
    split_dir = dataset_dir / args.split
    
    if not split_dir.exists():
        print(f"Error: Split directory not found: {split_dir}")
        return 1
    
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
    output_dir = Path(args.output)
    ensure_dir(output_dir)
    
    for defect_class in defect_class_names:
        class_dir = split_dir / defect_class
        if not class_dir.exists():
            continue
        
        images = get_image_paths(class_dir)
        if not images:
            continue
        
        sample_images = random.sample(images, min(args.samples_per_class, len(images)))
        
        # Create grid
        grid_rows = (len(sample_images) + args.grid_cols - 1) // args.grid_cols
        grid_height = 224 * grid_rows
        grid_width = 224 * args.grid_cols
        grid_img = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
        
        for idx, img_path in enumerate(sample_images):
            row = idx // args.grid_cols
            col = idx % args.grid_cols
            
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            
            img_resized = cv2.resize(img, (224, 224))
            
            y1 = row * 224
            y2 = y1 + 224
            x1 = col * 224
            x2 = x1 + 224
            grid_img[y1:y2, x1:x2] = img_resized
        
        cv2.putText(grid_img, defect_class, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        output_path = output_dir / f"{defect_class}_samples.jpg"
        cv2.imwrite(str(output_path), grid_img)
    
    print(f"Visualizations saved to: {output_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
