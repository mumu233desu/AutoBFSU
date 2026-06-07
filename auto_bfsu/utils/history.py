import json
import threading
from pathlib import Path
from ..config import Config

class HistoryManager:
    _lock = threading.RLock()
    
    @classmethod
    def get_cache_path(cls) -> Path:
        return Path(Config.BASE_DIR / "history_cache.json")

    @classmethod
    def load_history_cache(cls) -> list:
        """Load history cache from JSON safely."""
        path = cls.get_cache_path()
        with cls._lock:
            if not path.exists():
                return []
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[HistoryManager] Failed to load history cache: {e}")
                return []

    @classmethod
    def save_history_cache(cls, cache_list: list):
        """Save history cache list to JSON safely."""
        path = cls.get_cache_path()
        with cls._lock:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cache_list, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[HistoryManager] Failed to save history cache: {e}")

    @classmethod
    def load_history_ids(cls) -> set:
        """Load all IDs currently in cache as a set for O(1) checks."""
        cache = cls.load_history_cache()
        return {item['id'] for item in cache}

    @classmethod
    def add_to_history_cache(cls, item: dict):
        """Append an item to the history cache if it doesn't already exist."""
        with cls._lock:
            cache = cls.load_history_cache()
            if not any(i['id'] == item['id'] for i in cache):
                cache.append(item)
                # Keep cache size bounded
                if len(cache) > Config.MAX_HISTORY_CACHE:
                    cache = cache[-Config.MAX_HISTORY_CACHE:]
                cls.save_history_cache(cache)

    @classmethod
    def mark_acknowledged(cls, notice_id: str):
        """Mark a specific notice as acknowledged."""
        with cls._lock:
            cache = cls.load_history_cache()
            updated = False
            for item in cache:
                if item['id'] == notice_id:
                    item['acknowledged'] = True
                    updated = True
                    break
            if updated:
                cls.save_history_cache(cache)
