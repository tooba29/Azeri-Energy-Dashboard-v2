"""Dataset splitting utilities."""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.model_selection import train_test_split
import shutil


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
    from ..utils.io import get_image_paths, ensure_dir
    
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
    
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


def split_dataset(
    source_dir: Path,
    train_dir: Path,
    val_dir: Path,
    test_dir: Optional[Path] = None,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    random_state: int = 42,
    stratify_by_class: bool = True
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
        test_ratio: Test set ratio
        random_state: Random seed
        stratify_by_class: Whether to stratify by class presence (if labels available)
    
    Returns:
        Dictionary with split counts
    """
    from ..utils.io import get_image_paths, ensure_dir
    
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
    
    # Get all images
    all_images = get_image_paths(source_dir)
    
    if not all_images:
        raise ValueError(f"No images found in {source_dir}")
    
    # Try to stratify by class presence
    if stratify_by_class:
        # Check if labels are in same directory structure
        labels_dir = source_dir.parent / "labels"
        if not labels_dir.exists():
            # Try alternative: labels in same directory as images
            labels_dir = source_dir
        if labels_dir.exists():
            # Create stratification groups based on which classes are present
            groups = []
            for img_path in all_images:
                label_path = labels_dir / f"{img_path.stem}.txt"
                if label_path.exists():
                    try:
                        with open(label_path, 'r') as f:
                            annotations = []
                            for line in f:
                                parts = line.strip().split()
                                if len(parts) == 5:
                                    annotations.append((int(parts[0]),))
                            classes = set(ann[0] for ann in annotations)
                            group_key = tuple(sorted(classes))
                            groups.append(group_key)
                    except:
                        groups.append(())
                else:
                    groups.append(())  # Empty label group
        else:
            groups = None
    else:
        groups = None
    
    # Split
    if test_dir:
        train_images, temp_images = train_test_split(
            all_images,
            test_size=(val_ratio + test_ratio),
            random_state=random_state,
            stratify=groups if groups else None
        )
        # Adjust groups for second split
        if groups:
            temp_groups = [groups[all_images.index(img)] for img in temp_images]
        else:
            temp_groups = None
        val_images, test_images = train_test_split(
            temp_images,
            test_size=test_ratio / (val_ratio + test_ratio),
            random_state=random_state,
            stratify=temp_groups
        )
    else:
        train_images, val_images = train_test_split(
            all_images,
            test_size=val_ratio,
            random_state=random_state,
            stratify=groups if groups else None
        )
        test_images = []
    
    # Copy files
    counts = {'train': 0, 'val': 0, 'test': 0}
    
    def copy_image_and_label(img_path, dest_dir):
        # Copy image
        dest_img = dest_dir / "images" / img_path.name
        ensure_dir(dest_img.parent)
        shutil.copy2(img_path, dest_img)
        
        # Copy label if exists
        labels_dir = source_dir.parent / "labels"
        if not labels_dir.exists():
            labels_dir = source_dir  # Try same directory
        if labels_dir.exists():
            label_path = labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                dest_label = dest_dir / "labels" / label_path.name
                ensure_dir(dest_label.parent)
                shutil.copy2(label_path, dest_label)
    
    for img in train_images:
        copy_image_and_label(img, train_dir)
        counts['train'] += 1
    
    for img in val_images:
        copy_image_and_label(img, val_dir)
        counts['val'] += 1
    
    if test_dir:
        for img in test_images:
            copy_image_and_label(img, test_dir)
            counts['test'] += 1
    
    return counts
