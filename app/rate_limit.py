"""Shared slowapi Limiter instance.

Extracted from ``app.main`` so individual routers can apply
``@limiter.limit(...)`` decorators without triggering a circular import
with ``app.main`` during module load.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
