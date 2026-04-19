import tomllib
import tomli_w
from pathlib import Path

CONFIG_PATH = Path.home() / ".jobhunt.toml"

DEFAULTS = {
    "role":      "full stack developer",
    "location":  "india",
    "experience": 0,
    "skills":    [],
    "platforms": ["indeed", "hirist", "internshala"],
    "limit":     20,
}


def load_config() -> dict:
    """Load config from ~/.jobhunt.toml, falling back to defaults."""
    if not CONFIG_PATH.exists():
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
        # Merge with defaults so missing keys always have a value
        return {**DEFAULTS, **data.get("search", {})}
    except Exception:
        return dict(DEFAULTS)


def save_config(cfg: dict) -> None:
    """Save config to ~/.jobhunt.toml."""
    data = {"search": {k: v for k, v in cfg.items() if k in DEFAULTS}}
    CONFIG_PATH.write_bytes(tomli_w.dumps(data).encode())


def show_config() -> None:
    """Print current config to stdout."""
    cfg = load_config()
    print(f"Config file: {CONFIG_PATH}")
    print(f"  role:       {cfg['role']}")
    print(f"  location:   {cfg['location']}")
    print(f"  experience: {cfg['experience']}")
    print(f"  skills:     {', '.join(cfg['skills']) if cfg['skills'] else '(none)'}")
    print(f"  platforms:  {', '.join(cfg['platforms'])}")
    print(f"  limit:      {cfg['limit']}")