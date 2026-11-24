"""Shared local model generation coordination and bounded request capacity."""

import asyncio
import os

# One generation runs at a time. A fixed number of additional chat requests may
# wait; excess requests are rejected instead of accumulating indefinitely.
MAX_PENDING_GENERATIONS = int(os.environ.get("ORINOCO_MAX_PENDING_GENERATIONS", "8"))
if not 0 <= MAX_PENDING_GENERATIONS <= 32:
    raise RuntimeError("ORINOCO_MAX_PENDING_GENERATIONS must be between 0 and 32.")

generation_lock = asyncio.Semaphore(1)
generation_capacity = asyncio.BoundedSemaphore(MAX_PENDING_GENERATIONS + 1)
