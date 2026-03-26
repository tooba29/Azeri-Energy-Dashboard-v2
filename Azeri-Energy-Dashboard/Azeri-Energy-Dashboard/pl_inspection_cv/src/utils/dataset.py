"""Dataset utilities."""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil
from sklearn.model_selection import train_test_split


def split_dataset(
    source_dir: Path,
    train_dir: Path,
    val_dir: Path,
    test_dir: Optional[Path] = None,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    random_state: int = 42
) -> Dict[str, int]:
    """
    Split dataset into train/val/test sets.
    
    Args:
        source_dir: Source directory with all data
        train_dir: Training set output directory
        val_dir: Validation set output directory
        test_dir: Optional test set output directory
        train_ratio: Training set ratio
        val_ratio: Validation set ratio
        test_ratio: Test set ratio (must sum to 1.0 with train_ratio + val_ratio)
        random_state: Random seed
    
    Returns:
        Dictionary with split counts
    """
    from .io import get_image_paths, ensure_dir
    
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
    
    # Get all files
    all_files = get_image_paths(source_dir)
    
    if not all_files:
        raise ValueError(f"No images found in {source_dir}")
    
    # Split
    if test_dir:
        train_files, temp_files = train_test_split(
            all_files,
            test_size=(val_ratio + test_ratio),
            random_state=random_state
        )
        val_files, test_files = train_test_split(
            temp_files,
            test_size=test_ratio / (val_ratio + test_ratio),
            random_state=random_state
        )
    else:
        train_files, val_files = train_test_split(
            all_files,
            test_size=val_ratio,
            random_state=random_state
        )
        test_files = []
    
    # Copy files
    counts = {'train': 0, 'val': 0, 'test': 0}
    
    for file in train_files:
        dest = train_dir / file.name
        ensure_dir(dest.parent)
        shutil.copy2(file, dest)
        counts['train'] += 1
    
    for file in val_files:
        dest = val_dir / file.name
        ensure_dir(dest.parent)
        shutil.copy2(file, dest)
        counts['val'] += 1
    
    if test_dir:
        for file in test_files:
            dest = test_dir / file.name
            ensure_dir(dest.parent)
            shutil.copy2(file, dest)
            counts['test'] += 1
    
    return counts


def split_classification_dataset(
    source_dir: Path,
    output_dir: Path,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    random_state: int = 42
) -> Dict[str, Dict[str, int]]:
    """
    Split classification dataset (folder-per-class) into train/val/test.
    
    Args:
        source_dir: Directory with class subdirectories (e.g., all/normal/, all/rust/)
        output_dir: Output directory (will create train/, val/, test/ subdirectories)
        train_ratio: Training set ratio
        val_ratio: Validation set ratio
        test_ratio: Test set ratio
        random_state: Random seed
    
    Returns:
        Dictionary with counts per split and class
    """
    from .io import get_image_paths, ensure_dir
    
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
    
    output_dir = Path(output_dir)
    class_dirs = sorted([d for d in source_dir.iterdir() if d.is_dir()])
    
    if not class_dirs:
        raise ValueError(f"No class directories found in {source_dir}")
    
    counts = {}
    
    for class_dir in class_dirs:
        class_name = class_dir.name
        images = get_image_paths(class_dir)
        
        if not images:
            print(f"Warning: No images in {class_dir}")
            continue
        
        # Split
        if test_ratio > 0:
            train_images, temp_images = train_test_split(
                images,
                test_size=(val_ratio + test_ratio),
                random_state=random_state
            )
            val_images, test_images = train_test_split(
                temp_images,
                test_size=test_ratio / (val_ratio + test_ratio),
                random_state=random_state
            )
        else:
            train_images, val_images = train_test_split(
                images,
                test_size=val_ratio,
                random_state=random_state
            )
            test_images = []
        
        # Copy to output directories
        for img in train_images:
            dest = output_dir / 'train' / class_name / img.name
            ensure_dir(dest.parent)
            shutil.copy2(img, dest)
        
        for img in val_images:
            dest = output_dir / 'val' / class_name / img.name
            ensure_dir(dest.parent)
            shutil.copy2(img, dest)
        
        if test_ratio > 0:
            for img in test_images:
                dest = output_dir / 'test' / class_name / img.name
                ensure_dir(dest.parent)
                shutil.copy2(img, dest)
        
        counts[class_name] = {
            'train': len(train_images),
            'val': len(val_images),
            'test': len(test_images) if test_ratio > 0 else 0
        }
    
    return counts
