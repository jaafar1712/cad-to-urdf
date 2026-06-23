#!/usr/bin/env python3
"""
Standalone CLI validator for a CAD2URDF-exported ROS 2 package.

Usage
-----
  python validate_package.py  <package_directory>
  python validate_package.py  C:/path/to/my_robot_package

Exit codes
----------
  0  all checks passed (no failures)
  1  one or more failures
  2  bad arguments
"""
import sys
import os

# Allow running from repo root without installing
sys.path.insert(0, os.path.dirname(__file__))

from utils.urdf_validator import validate_package


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)

    pkg_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(pkg_dir):
        print(f"Error: not a directory: {pkg_dir}")
        sys.exit(2)

    result = validate_package(pkg_dir)
    print(result['report'])
    sys.exit(0 if result['ok'] else 1)


if __name__ == '__main__':
    main()
