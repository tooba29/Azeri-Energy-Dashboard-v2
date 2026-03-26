"""Script 12: Evaluate defect classifier."""

import argparse
from pathlib import Path
from ultralytics import YOLO
from tqdm import tqdm
from src.utils.io import load_yaml, save_json, get_image_paths, ensure_dir
from src.utils.metrics import calculate_classification_metrics, plot_confusion_matrix
import numpy as np


def main():
    parser = argparse.ArgumentParser(description='Evaluate defect classifier (Stage B)')
    parser.add_argument('--weights', type=str, required=True)
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--split', type=str, default='val', choices=['val', 'test'])
    parser.add_argument('--defects-config', type=str, default='configs/defects.yaml')
    parser.add_argument('--output', type=str, default='outputs/reports/cls_metrics.json')
    parser.add_argument('--conf-matrix', type=str, default='outputs/reports/cls_confusion_matrix.png')
    
    args = parser.parse_args()
    
    weights_path = Path(args.weights)
    if not weights_path.exists():
        print(f"Error: Model weights not found: {weights_path}")
        return 1
    
    dataset_dir = Path(args.dataset)
    split_dir = dataset_dir / args.split
    
    if not split_dir.exists():
        print(f"Error: Split directory not found: {split_dir}")
        return 1
    
    defects_config = load_yaml(args.defects_config)
    defect_class_names = defects_config['names']
    
    model = YOLO(str(weights_path))
    
    y_true = []
    y_pred = []
    
    for class_id, class_name in enumerate(defect_class_names):
        class_dir = split_dir / class_name
        if not class_dir.exists():
            continue
        
        images = get_image_paths(class_dir)
        
        for img_path in tqdm(images, desc=class_name, leave=False):
            results = model.predict(str(img_path), verbose=False)
            
            if results and len(results) > 0:
                result = results[0]
                if hasattr(result, 'probs') and result.probs is not None:
                    pred_class_id = int(result.probs.top1)
                else:
                    pred_class_id = 0
            else:
                pred_class_id = 0
            
            y_true.append(class_id)
            y_pred.append(pred_class_id)
    
    metrics = calculate_classification_metrics(y_true, y_pred, defect_class_names)
    
    output_path = Path(args.output)
    ensure_dir(output_path.parent)
    save_json(metrics, output_path)
    
    cm = np.array(metrics['confusion_matrix'])
    conf_matrix_path = Path(args.conf_matrix)
    plot_confusion_matrix(cm, defect_class_names, conf_matrix_path)
    
    print(f"\nEvaluation Results:")
    print(f"  Accuracy: {metrics['accuracy']:.4f}")
    print(f"\nPer-class metrics:")
    for class_name, class_metrics in metrics['per_class'].items():
        print(f"  {class_name}:")
        print(f"    Precision: {class_metrics['precision']:.4f}")
        print(f"    Recall: {class_metrics['recall']:.4f}")
        print(f"    F1-Score: {class_metrics['f1_score']:.4f}")
    
    print(f"\nMetrics saved to: {output_path}")
    print(f"Confusion matrix saved to: {conf_matrix_path}")
    
    return 0


if __name__ == '__main__':
    exit(main())
