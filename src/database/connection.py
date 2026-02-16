"""Prisma database client management."""

from __future__ import annotations

from prisma import Prisma

_client: Prisma | None = None


async def get_client() -> Prisma:
    """Get or create the Prisma client (connects on first call)."""
    global _client
    if _client is None or not _client.is_connected():
        _client = Prisma()
        await _client.connect()
    return _client


async def disconnect():
    """Disconnect the Prisma client."""
    global _client
    if _client is not None and _client.is_connected():
        await _client.disconnect()
        _client = None
