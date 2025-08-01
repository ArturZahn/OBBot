from pathlib import Path
import json

class ConfigManager:
    def __init__(self, file_path , default_configs={}, autosave=True):

        super().__setattr__("_file_path", file_path)
        super().__setattr__("_default_configs", default_configs)
        super().__setattr__("_data", default_configs.copy())
        super().__setattr__("_autosave", autosave)

    def load(self):
        config_path = Path(self._file_path)
        self._data = self._default_configs.copy()
        if not config_path.exists():
            # write a config file
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(self._data, indent=4), encoding='utf-8')

        with open(config_path, 'r') as f:
            read_config = json.load(f)
            for key in read_config:
                self._data[key] = read_config[key]
                    
    def save(self):
        config_path = Path(self._file_path)
        with open(config_path, 'w') as f:
            json.dump(self._data, f, indent=4)

    def set_autosave(self, value: bool):
        self._autosave = value
            
    def __getattr__(self, name):
        # called only if 'name' not found on the normal attributes
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"{type(self).__name__!r} has no attribute {name!r}")

    def __setattr__(self, name, value):
        # any "private" or internal attr goes to the instance
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            # everything else becomes part of the config data
            self._data[name] = value
            if self._autosave:
                self.save()