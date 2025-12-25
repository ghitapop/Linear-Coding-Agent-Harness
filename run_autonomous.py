#!/usr/bin/env python3
"""Entry point for Autonomous Demo."""
import sys
from pathlib import Path

# Add python/src to path
sys.path.insert(0, str(Path(__file__).parent / 'python' / 'src'))

from server.autonomous_agent.main import main

if __name__ == "__main__":
    main()
