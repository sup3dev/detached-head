#!/usr/bin/env python3
"""Convenience wrapper: python build.py [args]"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from detached_head.build import main

if __name__ == "__main__":
    raise SystemExit(main())
