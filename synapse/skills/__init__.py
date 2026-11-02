"""Skills package – sub‑packages are imported lazily.
This prevents optional heavy dependencies (e.g., aiofiles) from being required when the package is imported.
"""
# Users can import needed sub‑packages explicitly, e.g.:
# from synapse.skills.system import file_ops
PROTOCOL_VERSION: str = "1.0"
