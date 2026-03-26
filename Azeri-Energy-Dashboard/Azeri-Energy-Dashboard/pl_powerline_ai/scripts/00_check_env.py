"""Script 00: Check environment and dependencies."""

import argparse
import sys
from pathlib import Path


def check_python_version():
    """Check Python version."""
    if sys.version_info < (3, 10):
        print("ERROR: Python 3.10+ required. Current version:", sys.version)
        return False
    print(f"✓ Python version: {sys.version.split()[0]}")
    return True


def check_package(package_name, import_name=None):
    """Check if a package is installed."""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"✓ {package_name}")
        return True
    except ImportError:
        print(f"✗ {package_name} (not installed)")
        return False


def main():
    parser = argparse.ArgumentParser(description='Check environment and dependencies')
    args = parser.parse_args()
    
    print("Checking environment...\n")
    
    all_ok = True
    
    # Check Python version
    if not check_python_version():
        all_ok = False
    
    print("\nChecking required packages:")
    packages = [
        ('ultralytics', 'ultralytics'),
        ('opencv-python', 'cv2'),
        ('numpy', 'numpy'),
        ('pyyaml', 'yaml'),
        ('pandas', 'pandas'),
        ('scikit-learn', 'sklearn'),
        ('matplotlib', 'matplotlib'),
        ('seaborn', 'seaborn'),
        ('tqdm', 'tqdm'),
        ('pillow', 'PIL'),
    ]
    
    for pkg_name, import_name in packages:
        if not check_package(pkg_name, import_name):
            all_ok = False
    
    print("\nChecking directories:")
    dirs_to_check = [
        'configs',
        'scripts',
        'src',
        'data/raw',
        'data/processed',
        'outputs'
    ]
    
    for dir_path in dirs_to_check:
        path = Path(dir_path)
        if path.exists():
            print(f"✓ {dir_path}")
        else:
            print(f"✗ {dir_path} (will be created when needed)")
    
    print("\n" + "="*50)
    if all_ok:
        print("Environment check PASSED ✓")
        return 0
    else:
        print("Environment check FAILED ✗")
        print("\nInstall missing packages with:")
        print("  pip install -r requirements.txt")
        return 1


if __name__ == '__main__':
    exit(main())
