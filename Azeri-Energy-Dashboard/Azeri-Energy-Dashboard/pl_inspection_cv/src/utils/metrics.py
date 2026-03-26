"""Metrics calculation utilities."""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.metrics import confusion_matrix, classification_report, accuracy_score
import matplotlib.pyplot as plt
import seaborn as sns


def calculate_classification_metrics(
    y_true: List[int],
    y_pred: List[int],
    class_names: List[str],
    output_path: Optional[Path] = None
) -> Dict:
    """
    Calculate classification metrics.
    
    Args:
        y_true: True class IDs
        y_pred: Predicted class IDs
        class_names: List of class names
        output_path: Optional path to save metrics JSON
    
    Returns:
        Dictionary with metrics
    """
    accuracy = accuracy_score(y_true, y_pred)
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(class_names))))
    
    # Per-class metrics
    report = classification_report(
        y_true, y_pred,
        target_names=class_names,
        output_dict=True,
        zero_division=0
    )
    
    # Extract per-class metrics
    per_class_metrics = {}
    for i, class_name in enumerate(class_names):
        if class_name in report:
            per_class_metrics[class_name] = {
                'precision': report[class_name]['precision'],
                'recall': report[class_name]['recall'],
                'f1_score': report[class_name]['f1-score'],
                'support': report[class_name]['support']
            }
    
    metrics = {
        'accuracy': float(accuracy),
        'per_class': per_class_metrics,
        'confusion_matrix': cm.tolist(),
        'class_names': class_names
    }
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    return metrics


def plot_confusion_matrix(
    cm: np.ndarray,
    class_names: List[str],
    output_path: Path,
    normalize: bool = True
) -> None:
    """
    Plot and save confusion matrix.
    
    Args:
        cm: Confusion matrix array
        class_names: List of class names
        output_path: Path to save plot
        normalize: Whether to normalize the matrix
    """
    if normalize:
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        fmt = '.2f'
    else:
        fmt = 'd'
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt=fmt,
        cmap='Blues',
        xticklabels=class_names,
        yticklabels=class_names
    )
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150)
    plt.close()
