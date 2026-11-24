"""Shared local model generation coordination."""

import asyncio

generation_lock = asyncio.Semaphore(1)
