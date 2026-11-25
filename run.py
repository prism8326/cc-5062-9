#!/usr/bin/env python3 -I
"""Executable entry point so the CLI runs under isolated mode without install."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from idxpaint.cli import main

if __name__ == "__main__":
    sys.exit(main())
