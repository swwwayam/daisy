"""Server-owned resource identities; browser-supplied owner IDs are never trusted."""
from threading import RLock


class ResourceOwners:
    """Track immutable ownership for resources held by this API process."""

    def __init__(self):
        self._owners: dict[str, str] = {}
        self._lock = RLock()

    def register(self, resource_id: str, owner_id: str) -> None:
        if not isinstance(resource_id, str) or not resource_id:
            raise ValueError("A resource ID is required")
        if not isinstance(owner_id, str) or not owner_id:
            raise ValueError("An authenticated owner is required")
        with self._lock:
            existing = self._owners.get(resource_id)
            if existing is not None and existing != owner_id:
                raise ValueError("Resource ownership cannot be reassigned")
            self._owners[resource_id] = owner_id

    def permits(self, resource_id: str, owner_id: str) -> bool:
        with self._lock:
            return bool(owner_id) and self._owners.get(resource_id) == owner_id

    def owner(self, resource_id: str) -> str | None:
        with self._lock:
            return self._owners.get(resource_id)

    def forget(self, resource_id: str) -> None:
        """Drop a cache entry only; durable ownership remains authoritative."""
        with self._lock:
            self._owners.pop(resource_id, None)

