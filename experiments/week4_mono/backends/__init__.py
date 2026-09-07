"""Week 4A backend registry.

Import is LAZY and per-key. Each backend module imports a different model stack,
and several of those stacks cannot coexist in one interpreter — the MoGe family
and Depth Anything 3 disagree about numpy's major version, and the project's
standing rule since Week 3 is one model per process anyway, with process exit as
the authoritative MPS cleanup boundary. Importing this package must therefore
import no model code at all.
"""

from __future__ import annotations

#: key -> (module, attribute). `BACKENDS` modules expose a dict keyed by model.
_REGISTRY = {
    "mapanything_n1": ("experiments.week4_mono.backends.mapanything_n1", "BACKEND"),
    "dav2_small": ("experiments.week4_mono.backends.dav2_small", "BACKEND"),
    "moge2_vitl": ("experiments.week4_mono.backends.moge_family", "BACKENDS"),
    "metricanything_pointmap": ("experiments.week4_mono.backends.moge_family", "BACKENDS"),
    "wat3r_n1": ("experiments.week4_mono.backends.wat3r_n1", "BACKEND"),
    "da3mono_large": ("experiments.week4_mono.backends.da3mono_large", "BACKEND"),
    "foundationgeo_11": ("experiments.week4_mono.backends.foundationgeo_11", "BACKEND"),
}


def get(key: str):
    """Return the backend CLASS for `key`, importing only that model's stack."""
    import importlib
    if key not in _REGISTRY:
        raise KeyError(f"unknown backend {key!r}; known: {sorted(_REGISTRY)}")
    mod_name, attr = _REGISTRY[key]
    mod = importlib.import_module(mod_name)
    obj = getattr(mod, attr)
    return obj[key] if isinstance(obj, dict) else obj


def keys() -> list[str]:
    return list(_REGISTRY)
