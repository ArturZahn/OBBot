# from pathlib import Path
# import json

# class ConfigManager:
#     def __init__(self, file_path , default_configs={}, autosave=True):

#         super().__setattr__("_file_path", file_path)
#         super().__setattr__("_default_configs", default_configs)
#         super().__setattr__("_data", default_configs.copy())
#         super().__setattr__("_autosave", autosave)

#     def load(self):
#         config_path = Path(self._file_path)
#         self._data = self._default_configs.copy()
#         if not config_path.exists():
#             # write a config file
#             config_path.parent.mkdir(parents=True, exist_ok=True)
#             config_path.write_text(json.dumps(self._data, indent=4), encoding='utf-8')

#         with open(config_path, 'r') as f:
#             read_config = json.load(f)
#             for key in read_config:
#                 self._data[key] = read_config[key]
                    
#     def save(self):
#         config_path = Path(self._file_path)
#         with open(config_path, 'w') as f:
#             json.dump(self._data, f, indent=4)

#     def set_autosave(self, value: bool):
#         self._autosave = value
            
#     def __getattr__(self, name):
#         # called only if 'name' not found on the normal attributes
#         if name in self._data:
#             return self._data[name]
#         raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

#     def __setattr__(self, name, value):
#         # any "private" or internal attr goes to the instance
#         if name.startswith("_"):
#             super().__setattr__(name, value)
#         else:
#             # everything else becomes part of the config data
#             self._data[name] = value
#             if self._autosave:
#                 self.save()

from __future__ import annotations
from pathlib import Path
import json
import copy

# ---------- autosaving wrappers ----------

class _AutoSaveList(list):
    def __init__(self, iterable, owner: "ConfigManager"):
        super().__init__(owner._wrap_mutables(x) for x in iterable)
        self._owner = owner

    # mutations
    def __setitem__(self, i, v):
        super().__setitem__(i, self._owner._wrap_mutables(v)); self._owner._maybe_save()
    def __delitem__(self, i):
        super().__delitem__(i); self._owner._maybe_save()
    def append(self, v):
        super().append(self._owner._wrap_mutables(v)); self._owner._maybe_save()
    def extend(self, it):
        super().extend(self._owner._wrap_mutables(x) for x in it); self._owner._maybe_save()
    def insert(self, i, v):
        super().insert(i, self._owner._wrap_mutables(v)); self._owner._maybe_save()
    def pop(self, i=-1):
        val = super().pop(i); self._owner._maybe_save(); return val
    def remove(self, v):
        super().remove(v); self._owner._maybe_save()
    def clear(self):
        super().clear(); self._owner._maybe_save()
    def sort(self, *a, **kw):
        super().sort(*a, **kw); self._owner._maybe_save()
    def reverse(self):
        super().reverse(); self._owner._maybe_save()
    def __iadd__(self, it):
        return type(self)(list(self) + [self._owner._wrap_mutables(x) for x in it], self._owner)
    def __imul__(self, n):
        return type(self)(list(self) * n, self._owner)


class _AutoSaveDict(dict):
    def __init__(self, mapping, owner: "ConfigManager"):
        super().__init__({k: owner._wrap_mutables(v) for k, v in mapping.items()})
        self._owner = owner

    # mutations
    def __setitem__(self, k, v):
        super().__setitem__(k, self._owner._wrap_mutables(v)); self._owner._maybe_save()
    def __delitem__(self, k):
        super().__delitem__(k); self._owner._maybe_save()
    def clear(self):
        super().clear(); self._owner._maybe_save()
    def pop(self, k, *d):
        val = super().pop(k, *d); self._owner._maybe_save(); return val
    def popitem(self):
        kv = super().popitem(); self._owner._maybe_save(); return kv
    def setdefault(self, k, default=None):
        if k not in self:
            super().__setitem__(k, self._owner._wrap_mutables(default)); self._owner._maybe_save()
        return super().get(k)
    def update(self, other=None, **kw):
        if other:
            if hasattr(other, "items"):
                for k, v in other.items():
                    super().__setitem__(k, self._owner._wrap_mutables(v))
            else:
                for k, v in other:
                    super().__setitem__(k, self._owner._wrap_mutables(v))
        for k, v in kw.items():
            super().__setitem__(k, self._owner._wrap_mutables(v))
        self._owner._maybe_save()


# ---------- your ConfigManager with autosave on any mutation ----------

class ConfigManager:
    def __init__(self, file_path: str, default_configs: dict | None = None, autosave: bool = True):
        # avoid mutable default arg pitfall
        default_configs = copy.deepcopy(default_configs) if default_configs is not None else {}
        super().__setattr__("_file_path", file_path)
        super().__setattr__("_default_configs", default_configs)
        super().__setattr__("_autosave", autosave)
        # wrap mutables so in-place changes trigger saves
        super().__setattr__("_data", self._wrap_mutables(copy.deepcopy(default_configs)))

    # ----- helpers -----
    def _wrap_mutables(self, value):
        """Recursively wrap lists/dicts so mutations trigger save."""
        if isinstance(value, _AutoSaveList) or isinstance(value, _AutoSaveDict):
            return value
        if isinstance(value, list):
            return _AutoSaveList(value, owner=self)
        if isinstance(value, dict):
            return _AutoSaveDict(value, owner=self)
        return value

    def _maybe_save(self):
        if self._autosave:
            self.save()

    # ----- public API -----
    def load(self):
        config_path = Path(self._file_path)
        # start from defaults
        base = copy.deepcopy(self._default_configs)
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(base, indent=4, ensure_ascii=False), encoding="utf-8")
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    loaded = json.load(f)
                    if not isinstance(loaded, dict):
                        raise ValueError("Config file must contain a JSON object at top level.")
                    base.update(loaded)
                except json.JSONDecodeError:
                    # keep defaults if file is corrupt
                    pass

        # wrap everything so later mutations autosave
        super().__setattr__("_data", self._wrap_mutables(base))

    def save(self):
        config_path = Path(self._file_path)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False)

    def set_autosave(self, value: bool):
        self._autosave = bool(value)

    # attribute access proxies into _data
    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = self._wrap_mutables(value)  # triggers save via _AutoSaveDict.__setitem__
            # If _data is a plain dict (e.g., name not yet present), ensure save:
            self._maybe_save()
