import glob
import hashlib
import os

from .katana_constants import CACHE_EXTENSIONS, GEOMETRY_EXTENSIONS, TEXTURE_EXTENSIONS
from .katana_utils import get_seq_search_string, is_udim_path, normalize_join, normalize_path


def md5_hash(s):
    return hashlib.md5(s.encode("utf-8") if isinstance(s, str) else s).hexdigest()


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
    return "assets/misc"


class DataHandler:
    def __init__(self, project_root):
        self.project_root = project_root
        self.path_list = set()
        self.assets = []
        self.file_count = 0
        self.dir_count = 0
        self.total_size_bytes = 0

    def _update_stats(self, src):
        try:
            if os.path.isfile(src):
                self.file_count += 1
                self.total_size_bytes += os.path.getsize(src)
            elif os.path.isdir(src):
                self.dir_count += 1
        except Exception:
            pass

    def add_path(self, source, target):
        if not source:
            return
        src = normalize_path(str(source))
        trg = normalize_path(str(target)) if target else ""
        self._update_stats(src)
        self.path_list.add("{},{}".format(src, trg))

    def add_path_and_asset(self, source, node, param, meta=None):
        """Add a single-file asset.  Returns (src, target_dir)."""
        src = normalize_path(str(source))
        asset_dir = classify_asset(src)
        hash_val = md5_hash(src)
        target_dir = normalize_join(asset_dir, hash_val)
        target_file = normalize_join(target_dir, os.path.basename(src))

        self.add_path(src, target_dir)
        self.assets.append({
            "node": node or "",
            "param": param or "",
            "source": src,
            "target": target_file,
            "metadata": meta or {},
        })
        return src, target_dir

    def add_sequence_asset(self, pattern_path, node, param, logger, meta=None):
        """Expand a UDIM/sequence pattern, add each file to path_list, store pattern in assets."""
        src_pattern = normalize_path(str(pattern_path))
        asset_dir = classify_asset(src_pattern)
        hash_val = md5_hash(src_pattern)
        target_dir = normalize_join(asset_dir, hash_val)
        target_file = normalize_join(target_dir, os.path.basename(src_pattern))

        search = get_seq_search_string(src_pattern)
        matched = glob.glob(search) if "*" in search else []

        if matched:
            logger.log("Sequence '{}': found {} files".format(src_pattern, len(matched)))
            for f in matched:
                self.add_path(normalize_path(f), target_dir)
        else:
            logger.log("WARNING: No files matched for sequence pattern: {}".format(search))
            self.add_path(src_pattern, target_dir)

        self.assets.append({
            "node": node or "",
            "param": param or "",
            "source": src_pattern,
            "target": target_file,
            "metadata": dict(meta or {}, is_sequence=True),
        })
        return src_pattern, target_dir

    def write_file_list(self, file_path):
        with open(file_path, "w") as fh:
            for entry in sorted(self.path_list):
                fh.write(entry + "\n")
