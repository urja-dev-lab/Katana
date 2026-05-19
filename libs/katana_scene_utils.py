import os

from .katana_constants import CACHE_EXTENSIONS, GEOMETRY_EXTENSIONS, TEXTURE_EXTENSIONS


def get_project_root(scene_path):
    """Walk up from scene_path looking for a known project root marker."""
    if not scene_path:
        return ""
    current = os.path.dirname(os.path.abspath(scene_path))
    markers = ("project.conf", ".katana", "scenes", "assets", "cache", "textures")
    while True:
        for marker in markers:
            if os.path.exists(os.path.join(current, marker)):
                return current.replace("\\", "/")
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.dirname(os.path.abspath(scene_path)).replace("\\", "/")


def classify_asset(path):
    ext = os.path.splitext(path or "")[1].lower()
    if ext == ".katana":
        return "scenes"
    if ext in CACHE_EXTENSIONS:
        return "assets/caches"
    if ext in GEOMETRY_EXTENSIONS:
        return "assets/geometry"
    if ext in TEXTURE_EXTENSIONS:
        return "assets/textures"
    if ext in (".ocio", ".cube", ".lut", ".cc"):
        return "assets/color"
    if ext in (".ies",):
        return "assets/lights"
    return "assets/misc"


def resolve_asset_path(raw_path, scene_path, project_root):
    """Resolve a raw parameter value to an absolute path."""
    import os as _os
    if not raw_path:
        return ""

    path = _os.path.expandvars(_os.path.expanduser(str(raw_path).strip()))

    # Strip @...@ variable wrappers
    if path.startswith("@") and path.endswith("@"):
        path = path[1:-1]

    if _os.path.isabs(path) or (len(path) >= 2 and path[1] == ":"):
        return path.replace("\\", "/")

    scene_dir = _os.path.dirname(scene_path)
    candidates = [
        _os.path.join(scene_dir, path),
        _os.path.join(project_root, path),
        _os.path.join(project_root, "assets", path),
        _os.path.join(project_root, "textures", path),
        _os.path.join(project_root, "cache", path),
        _os.path.join(project_root, "geo", path),
    ]
    for c in candidates:
        if _os.path.exists(c):
            return c.replace("\\", "/")

    return candidates[0].replace("\\", "/")
