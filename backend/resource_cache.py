"""Bounded caches with request leases so concurrent work cannot be evicted."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
import uuid


class CacheCapacityError(RuntimeError):
    pass


class ResourceCache(dict):
    def __init__(self, max_bytes, max_entries, *, size, can_evict, on_evict=lambda key: None):
        super().__init__()
        if max_bytes <= 0 or max_entries <= 0:
            raise ValueError("Cache limits must be positive")
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self.size, self.can_evict, self.on_evict = size, can_evict, on_evict
        self.order = OrderedDict()
        self.leases = {}
        self.current_lease = ContextVar(f"cache-{uuid.uuid4()}", default=None)
        self.lock = RLock()

    @contextmanager
    def lease(self):
        identifier = str(uuid.uuid4())
        with self.lock:
            self.leases[identifier] = set()
        token = self.current_lease.set(identifier)
        try:
            yield
        finally:
            self.current_lease.reset(token)
            with self.lock:
                self.leases.pop(identifier, None)

    def touch(self, key):
        if key in self.order:
            self.order.move_to_end(key)
        lease = self.leases.get(self.current_lease.get())
        if lease is not None:
            lease.add(key)

    def __contains__(self, key):
        with self.lock:
            found = super().__contains__(key)
            if found:
                self.touch(key)
            return found

    def __getitem__(self, key):
        with self.lock:
            value = super().__getitem__(key)
            self.touch(key)
            return value

    def get(self, key, default=None):
        with self.lock:
            return self[key] if key in self else default

    def __setitem__(self, key, value):
        weight = int(self.size(value))
        with self.lock:
            used = sum(self.order.values()) - self.order.get(key, 0) + weight
            count = len(self) + (0 if super().__contains__(key) else 1)
            protected = set().union(*self.leases.values()) if self.leases else set()
            victims = []
            if self.can_evict():
                for candidate, amount in self.order.items():
                    if used <= self.max_bytes and count <= self.max_entries:
                        break
                    if candidate != key and candidate not in protected:
                        victims.append(candidate)
                        used -= amount
                        count -= 1
            if used > self.max_bytes or count > self.max_entries:
                raise CacheCapacityError("Dataset cache capacity reached. Retry when active work finishes, delete unused demo datasets, or enable durable storage.")
            for candidate in victims:
                super().__delitem__(candidate)
                self.order.pop(candidate)
                self.on_evict(candidate)
            super().__setitem__(key, value)
            self.order[key] = weight
            self.touch(key)

    def __delitem__(self, key):
        with self.lock:
            super().__delitem__(key)
            self.order.pop(key, None)

    def pop(self, key, *default):
        with self.lock:
            if super().__contains__(key):
                value = super().__getitem__(key)
                self.__delitem__(key)
                return value
            if default:
                return default[0]
            raise KeyError(key)

    def setdefault(self, key, default=None):
        with self.lock:
            if key not in self:
                self[key] = default
            return self[key]

    def popitem(self):
        with self.lock:
            if not self:
                raise KeyError("popitem(): dictionary is empty")
            key = next(reversed(self.order))
            return key, self.pop(key)

    def __ior__(self, other):
        self.update(other)
        return self

    def clear(self):
        with self.lock:
            super().clear()
            self.order.clear()

    def update(self, *args, **kwargs):
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def copy(self):
        with self.lock:
            return dict(super().items())

    @property
    def used_bytes(self):
        with self.lock:
            return sum(self.order.values())
