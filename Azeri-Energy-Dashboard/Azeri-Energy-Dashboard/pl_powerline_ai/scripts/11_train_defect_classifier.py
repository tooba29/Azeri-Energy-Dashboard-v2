"""Script 11: Train Stage B defect classifier."""

import argparse
from pathlib import Path
from ultralytics import YOLO
from src.utils.io import load_yaml, write_text_file


def main():
    parser = argparse.ArgumentParser(description='Train defect classifier (Stage B)')
    parser.add_argument('--config', type=str, default='configs/train_cls.yaml')
    parser.add_argument('--data', type=str, default=None)
    parser.add_argument('--model', type=str, default=None)
    parser.add_argument('--epochs', type=int, default=None)
    parser.add_argument('--imgsz', type=int, default=None)
    parser.add_argument('--batch', type=int, default=None)
    parser.add_argument('--device', type=str, default=None)
    parser.add_argument('--quick', action='store_true',
                        help='Quick mode: 20 epochs for fast testing')
    
    args = parser.parse_args()
    
    config = load_yaml(args.config)
    
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
    
    # Quick mode overrides
    if args.quick:
        config['epochs'] = 20
        print("⚠️  Quick mode enabled: 20 epochs")
    
    model = YOLO(config['model'])
    
    print(f"Training defect classifier:")
    print(f"  Model: {config['model']}")
    print(f"  Dataset: {config['data']}")
    print(f"  Epochs: {config['epochs']}")
    print(f"  Image size: {config['imgsz']}")
    print(f"  Batch size: {config['batch']}")
    print(f"  Device: {config['device']}\n")
    
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
    
    best_weights_path = results.save_dir / 'weights' / 'best.pt'
    if best_weights_path.exists():
        report_path = Path('outputs/reports/best_classifier.txt')
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_file(report_path, str(best_weights_path.absolute()))
        print(f"\n✓ Best weights: {best_weights_path}")
        print(f"✓ Path saved to: {report_path}")
    
    print(f"\nTraining completed! Results: {results.save_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
