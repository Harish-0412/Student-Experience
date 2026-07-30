"""Phase 2 goal intelligence package.

This package is intentionally importable without wiring it into the Phase 1
application. Phase 1 can later include ``phase2_router`` and replace the actor
dependency with its authenticated principal.
"""

from astrapath.phase2.api import phase2_router

__all__ = ["phase2_router"]
