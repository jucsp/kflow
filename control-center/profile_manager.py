"""KFlow — Gestor de perfiles persistidos en ~/.config/kflow/profiles.json (HU-06).

Almacena únicamente los perfiles con nombre elegidos por el usuario en el
Control Center. Al "aplicar" un perfil, quien llama a este módulo (la GUI)
es responsable de volcarlo a kwinrc vía dbus_service — ver technical_memory.md.
"""
import json
import os

PROFILES_DIR = os.path.expanduser("~/.config/kflow")
PROFILES_PATH = os.path.join(PROFILES_DIR, "profiles.json")

DEFAULT_PROFILE = {
    "name": "default",
    "inner_gap": 8,
    "outer_margins": {"top": 24, "bottom": 8, "left": 8, "right": 8},
    "auto_virtual_desktop": True,
}


class ProfileManager:
    def __init__(self, path=PROFILES_PATH):
        self.path = path

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def load_all(self):
        if not os.path.isfile(self.path):
            return {"active": "default", "profiles": {"default": dict(DEFAULT_PROFILE)}}
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                return {"active": "default", "profiles": {"default": dict(DEFAULT_PROFILE)}}
        data.setdefault("active", "default")
        data.setdefault("profiles", {})
        data["profiles"].setdefault("default", dict(DEFAULT_PROFILE))
        return data

    def save_all(self, data):
        self._ensure_dir()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_profile(self, name, inner_gap, outer_margins, auto_virtual_desktop):
        data = self.load_all()
        data["profiles"][name] = {
            "name": name,
            "inner_gap": inner_gap,
            "outer_margins": dict(outer_margins),
            "auto_virtual_desktop": auto_virtual_desktop,
        }
        self.save_all(data)

    def delete_profile(self, name):
        if name == "default":
            raise ValueError("No se puede eliminar el perfil 'default'")
        data = self.load_all()
        data["profiles"].pop(name, None)
        if data.get("active") == name:
            data["active"] = "default"
        self.save_all(data)

    def get_profile(self, name):
        return self.load_all()["profiles"].get(name)

    def set_active(self, name):
        data = self.load_all()
        data["active"] = name
        self.save_all(data)

    def list_names(self):
        return list(self.load_all()["profiles"].keys())
