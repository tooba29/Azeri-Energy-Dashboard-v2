"""Script 05: Train Stage A detector."""

import argparse
from pathlib import Path
from ultralytics import YOLO
from src.utils.io import load_yaml, write_text_file


def main():
    parser = argparse.ArgumentParser(description='Train YOLO detector for component detection (Stage A)')
    parser.add_argument('--config', type=str, default='configs/train_detect.yaml')
    parser.add_argument('--data', type=str, default=None, help='Override dataset YAML path')
    parser.add_argument('--model', type=str, default=None, help='Override model')
    parser.add_argument('--epochs', type=int, default=None)
    parser.add_argument('--imgsz', type=int, default=None)
    parser.add_argument('--batch', type=int, default=None)
    parser.add_argument('--device', type=str, default=None)
    
    args = parser.parse_args()
    
    config = load_yaml(args.config)
    
    if args.data:
        config['path'] = args.data
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
        config['imgsz'] = 640
        print("⚠️  Quick mode enabled: 20 epochs, imgsz=640")
    
    # Validate dataset before training (CRITICAL safeguard)
    print("\nValidating dataset before training...")
    dataset_path = config.get('path', 'data/processed/detect_yolo/data.yaml')
    if isinstance(dataset_path, str) and dataset_path.endswith('.yaml'):
        dataset_dir = Path(dataset_path).parent
    else:
        dataset_dir = Path('data/processed/detect_yolo')
    
    # Run validation programmatically
    import subprocess
    import sys
    from pathlib import Path as PathLib
    
    val_script = PathLib('scripts/03_validate_detect_dataset.py')
    if not val_script.exists():
        # Try relative to current working directory
        val_script = PathLib(__file__).parent.parent / 'scripts' / '03_validate_detect_dataset.py'
    
    result = subprocess.run(
        [sys.executable, str(val_script),
         '--dataset', str(dataset_dir),
         '--output-report', 'outputs/reports/pre_train_validation.json'],
        capture_output=True,
        text=True,
        cwd=PathLib.cwd()
    )
    
    if result.returncode != 0:
        print("\n" + "="*70)
        print("⚠️  DATASET VALIDATION FAILED - ABORTING TRAINING")
        print("="*70)
        print("\nValidation output:")
        print(result.stdout)
        if result.stderr:
            print("\nErrors:")
            print(result.stderr)
        print("\nPlease fix dataset issues before training.")
        print(f"Run manually: python scripts/03_validate_detect_dataset.py --dataset {dataset_dir}")
        return 1
    
    print("✓ Dataset validation passed\n")
    
    model = YOLO(config['model'])
    
    print(f"Training detector:")
    print(f"  Model: {config['model']}")
    print(f"  Dataset: {config['path']}")
    print(f"  Epochs: {config['epochs']}")
    print(f"  Image size: {config['imgsz']}")
    print(f"  Batch size: {config['batch']}")
    print(f"  Device: {config['device']}\n")
    
    results = model.train(
        data=config['path'],
        epochs=config['epochs'],
        imgsz=config['imgsz'],
        batch=config['batch'],
        device=config['device'],
        project=config.get('project', './outputs/runs'),
        name=config.get('name', 'detect_train'),
        exist_ok=config.get('exist_ok', True),
        **{k: v for k, v in config.items() if k not in [
            'path', 'model', 'epochs', 'imgsz', 'batch', 'device', 'project', 'name', 'exist_ok'
        ]}
    )
    
    # Save best weights path
    best_weights_path = results.save_dir / 'weights' / 'best.pt'
    if best_weights_path.exists():
        report_path = Path('outputs/reports/best_detector.txt')
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_file(report_path, str(best_weights_path.absolute()))
        print(f"\n✓ Best weights saved to: {best_weights_path}")
        print(f"✓ Path saved to: {report_path}")
    
    # Print final metrics
    if hasattr(results, 'results_dict'):
        metrics = results.results_dict
        print(f"\nFinal metrics:")
        if 'metrics/mAP50(B)' in metrics:
            print(f"  mAP50: {metrics['metrics/mAP50(B)']:.4f}")
        if 'metrics/mAP50-95(B)' in metrics:
            print(f"  mAP50-95: {metrics['metrics/mAP50-95(B)']:.4f}")
    
    print(f"\nTraining completed! Results: {results.save_dir}")
    return 0


if __name__ == '__main__':
    exit(main())
