"""
Edge storage package
Resilient local storage for edge device with append-only JSON files and SQLite index
"""

from .edge_storage import EdgeStorage

__all__ = ['EdgeStorage']