#!/usr/bin/env python3
"""Entry point: batch-extract all RGHS OPD prescriptions. See src/agents/extractor.py."""
import asyncio

from src.agents.extractor import main

if __name__ == "__main__":
    asyncio.run(main())
