"""Label mapping utilities."""

from pathlib import Path
from typing import Dict, Optional
import yaml


def load_label_mapping(mapping_config_path: Path, dataset_name: str) -> Dict[str, Optional[str]]:
    """
    Load label mapping for a specific dataset.
    
    Args:
        mapping_config_path: Path to label_mapping.yaml
        dataset_name: Name of the dataset
    
    Returns:
        Dictionary mapping dataset labels to unified labels (or None to ignore)
    """
    with open(mapping_config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    mappings = config.get('mappings', {})
    return mappings.get(dataset_name, {})


def map_label(
    dataset_label: str,
    mapping: Dict[str, Optional[str]],
    case_sensitive: bool = False
) -> Optional[str]:
    """
    Map a dataset label to unified label.
    
    Args:
        dataset_label: Original label from dataset
        mapping: Label mapping dictionary
        case_sensitive: Whether mapping is case-sensitive
    
    Returns:
        Unified label name or None if label should be ignored
    """
    if case_sensitive:
        return mapping.get(dataset_label)
    else:
        # Case-insensitive lookup
        dataset_label_lower = dataset_label.lower()
        for key, value in mapping.items():
            if key.lower() == dataset_label_lower:
                return value
        return None
