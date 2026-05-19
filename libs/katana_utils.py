import os
import re

from .katana_constants import ALL_ASSET_EXTENSIONS, UDIM_DIGIT_PATTERN, UDIM_TOKENS


def normalize_path(path):
    if not path:
        return ""
    return str(path).replace("\\", "/")


def normalize_join(*args):
    return normalize_path(os.path.join(*args))


def is_absolute_path(path):
    if not path:
        return False
    value = str(path).strip()
    return (
        os.path.isabs(value)
        or (len(value) >= 2 and value[1] == ":")   # Windows drive letter
        or value.startswith("\\\\")
    )


def is_probable_file_path(value):
    """Return True only if value looks like a real file path, not a Katana scene-graph location."""
    if not value or not isinstance(value, str):
        return False
    value = value.strip()
    if len(value) < 4:
        return False

    # Skip Katana scene-graph locations (/root/..., //root/...)
    if value.startswith("/root") or value.startswith("//"):
        return False

    # Skip CEL expressions and operators
    if value.startswith(("%", "(", "!")) or "(" in value:
        return False

    # Skip bare variable references
    if value.startswith("@") and value.endswith("@"):
        return False

    # Must have a file extension (covers UDIM tokens like texture_<UDIM>.tx)
    _, ext = os.path.splitext(value)
    if ext and len(ext) >= 2 and ext.lower() in ALL_ASSET_EXTENSIONS:
        return True

    return False


def is_udim_path(path):
    if not path:
        return False
    path_str = str(path)
    for token in UDIM_TOKENS:
        if token in path_str:
            return True
    if re.search(UDIM_DIGIT_PATTERN, path_str):
        return True
    return False


def get_seq_search_string(file_path):
    """Convert a UDIM/sequence path into a glob pattern."""
    for token in UDIM_TOKENS:
        if token in file_path:
            return file_path.replace(token, "*")
    if re.search(UDIM_DIGIT_PATTERN, file_path):
        return re.sub(UDIM_DIGIT_PATTERN, ".*.", file_path)
    return file_path


def dedupe_dicts(items, keys):
    seen = set()
    result = []
    for item in items:
        marker = tuple(item.get(k) for k in keys)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result
