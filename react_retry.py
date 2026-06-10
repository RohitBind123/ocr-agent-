#!/usr/bin/env python3
"""Entry point: ReAct retry on illegible fields. See src/agents/react_agent.py."""
import asyncio

from src.agents.react_agent import main

if __name__ == "__main__":
    asyncio.run(main())
