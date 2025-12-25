#!/usr/bin/env python3
"""Entry point for Orchestrator Framework."""
import asyncio
import sys
from pathlib import Path

# Add python/src to path
sys.path.insert(0, str(Path(__file__).parent / 'python' / 'src'))

from server.harness_agent.main import main

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[Use /quit or /exit to close the application]")
        sys.exit(0)
