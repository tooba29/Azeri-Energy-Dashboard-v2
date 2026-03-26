"""Script 10: Train defect classifier (Stage B)."""

import argparse
from pathlib import Path
from ultralytics import YOLO
from src.utils.io import load_yaml


def main():
    parser = argparse.ArgumentParser(description='Train YOLO classifier for defect classification (Stage B)')
    parser.add_argument('--config', type=str, default='./configs/train_cls.yaml',
                        help='Path to training config YAML (default: ./configs/train_cls.yaml)')
    parser.add_argument('--data', type=str, default=None,
                        help='Override dataset path (default: use from config)')
    parser.add_argument('--model', type=str, default=None,
                        help='Override model (default: use from config)')
    parser.add_argument('--epochs', type=int, default=None,
                        help='Override number of epochs (default: use from config)')
    parser.add_argument('--imgsz', type=int, default=None,
                        help='Override image size (default: use from config)')
    parser.add_argument('--batch', type=int, default=None,
                        help='Override batch size (default: use from config)')
    parser.add_argument('--device', type=str, default=None,
                        help='Override device (default: use from config)')
    
    args = parser.parse_args()
    
    # Load config
    config = load_yaml(args.config)
    
    # Override with CLI args
    if args.data:
        config['data'] = args.data
    if args.model:
        config['model'] = args.model
    if args.epochs:
        config['epochs'] = args.epochs
    if args.imgsz:
        config['imgsz'] = args.imgsz
    if args.batch:
        config['batch'] = args.batch
    if args.device:
        config['device'] = args.device
    
    # Load model
    model = YOLO(config['model'])
    
    print(f"Training defect classifier with config:")
    print(f"  Model: {config['model']}")
    print(f"  Dataset: {config['data']}")
    print(f"  Epochs: {config['epochs']}")
    print(f"  Image size: {config['imgsz']}")
    print(f"  Batch size: {config['batch']}")
    print(f"  Device: {config['device']}")
    
    # Train
    results = model.train(
        data=config['data'],
        epochs=config['epochs'],
        imgsz=config['imgsz'],
        batch=config['batch'],
        device=config['device'],
        project=config.get('project', './outputs/runs'),
        name=config.get('name', 'cls_train'),
        exist_ok=config.get('exist_ok', True),
        **{k: v for k, v in config.items() if k not in [
            'data', 'model', 'epochs', 'imgsz', 'batch', 'device', 'project', 'name', 'exist_ok'
        ]}
    )
    
    print(f"\nTraining completed!")
    print(f"Results saved to: {results.save_dir}")
    
    return 0


if __name__ == '__main__':
    exit(main())
