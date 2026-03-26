"""I/O utilities for file operations."""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    """Load YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(data: Dict[str, Any], path: Union[str, Path]) -> None:
    """Save data to YAML file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_json(path: Union[str, Path]) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: Union[Dict, List], path: Union[str, Path], indent: int = 2) -> None:
    """Save data to JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def get_image_paths(
    directory: Union[str, Path],
    extensions: Optional[List[str]] = None
) -> List[Path]:
    """Get all image file paths from directory."""
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    
    directory = Path(directory)
    image_paths = []
    for ext in extensions:
        image_paths.extend(directory.glob(f'*{ext}'))
        image_paths.extend(directory.glob(f'*{ext.upper()}'))
    
    return sorted(image_paths)


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure directory exists, create if not."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
