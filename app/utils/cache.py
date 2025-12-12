# app/utils/cache.py
from typing import Any, Optional
from datetime import datetime, timedelta
from functools import wraps

class SimpleCache:
    def __init__(self, default_ttl: int = 300):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        value, expiry = self._cache[key]
        if datetime.utcnow() > expiry:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        ttl = ttl or self._default_ttl
        expiry = datetime.utcnow() + timedelta(seconds=ttl)
        self._cache[key] = (value, expiry)

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        self._cache.clear()

    def cleanup(self) -> int:
        now = datetime.utcnow()
        expired = [k for k, (_, exp) in self._cache.items() if now > exp]
        for key in expired:
            del self._cache[key]
        return len(expired)

cache = SimpleCache()

def cached(ttl: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
