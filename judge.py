#!/usr/bin/env python3
"""Entry point: AI-vs-human clinical equivalence judge. See src/analysis/judge.py."""
import asyncio

from src.analysis.judge import main

if __name__ == "__main__":
    asyncio.run(main())
