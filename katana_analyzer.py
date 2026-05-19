"""
Katana Renderfarm Analyzer.

Production entry point (via scene tool wrapper):
    katana --batch --script katana_scene_tool.py -- --request <request.json>

Direct invocation (development / testing):
    katana --batch --script katana_analyzer.py -- <scene.katana> <sync_dir> <profile_json>
"""

import json
import os
import sys
import time
import traceback

try:
    from Katana import KatanaFile, NodegraphAPI
except Exception:
    KatanaFile = None
    NodegraphAPI = None

try:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    CURRENT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
LIBS_DIR = os.path.join(CURRENT_DIR, "libs")
REPO_ROOT = os.path.dirname(CURRENT_DIR)

for _p in (CURRENT_DIR, LIBS_DIR, REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.katana_logger import MessageLogger, get_logger          # noqa: E402
from libs.katana_constants import (                               # noqa: E402
    LOG_DIR, FILE_LIST, WEB_JSON_FILE, REPATH_LOG_FILE,
)
from libs.katana_data_handler import DataHandler                  # noqa: E402
from libs.katana_scene_utils import get_project_root, resolve_asset_path  # noqa: E402
from libs.katana_utils import (                                   # noqa: E402
    normalize_path, normalize_join, is_probable_file_path,
    is_udim_path, dedupe_dicts,
)
from libs.katana_info_collector import collect_scene_info         # noqa: E402
from libs.katana_ui_fields import KatanaUIFields                  # noqa: E402

try:
    from core.streamer_com import Messenger                       # noqa: E402
except Exception:
    Messenger = None


# ---------------------------------------------------------------------------
# Node / parameter traversal helpers
# ---------------------------------------------------------------------------

def _iter_nodes():
    if NodegraphAPI is None:
        return []
    try:
        fn = getattr(NodegraphAPI, "GetAllNodes", None)
        if callable(fn):
            return list(fn())
    except Exception:
        pass
    root = getattr(NodegraphAPI, "GetRootNode", lambda: None)()
    if root is None:
        return []
    nodes = []
    def _walk(n):
        nodes.append(n)
        for c in (getattr(n, "getChildren", lambda: [])() or []):
            _walk(c)
    _walk(root)
    return nodes


def _node_name(node):
    for attr in ("getName",):
        fn = getattr(node, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    return str(node)


def _node_type(node):
    fn = getattr(node, "getType", None)
    if callable(fn):
        try:
            return str(fn())
        except Exception:
            pass
    return ""


def _param_value(param):
    for frame in (0, 1):
        try:
            return param.getValue(frame)
        except Exception:
            pass
    try:
        return param.getValue()
    except Exception:
        return None


def _param_full_name(param):
    for attr in ("getFullName", "getName"):
        fn = getattr(param, attr, None)
        if callable(fn):
            try:
                return str(fn())
            except Exception:
                pass
    return ""


def _iter_params(param):
    if param is None:
        return
    yield param
    fn = getattr(param, "getChildren", None)
    if callable(fn):
        try:
            children = fn() or []
        except Exception:
            children = []
        for child in children:
            for nested in _iter_params(child):
                yield nested


# ---------------------------------------------------------------------------
# Asset collection
# ---------------------------------------------------------------------------

def _collect_assets(scene_path, project_root, dh, logger):
    logger.add_header("COLLECTING ASSETS")
    seen_paths = set()

    for node in _iter_nodes():
        nname = _node_name(node)
        fn = getattr(node, "getParameters", None)
        root_param = None
        if callable(fn):
            try:
                root_param = fn()
            except Exception:
                pass

        for param in _iter_params(root_param):
            value = _param_value(param)
            if not is_probable_file_path(value):
                continue

            param_path = _param_full_name(param)
            resolved = resolve_asset_path(str(value), scene_path, project_root)
            if not resolved or resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            if is_udim_path(resolved):
                meta = {"asset_type": _asset_type(resolved), "is_udim": True}
                dh.add_sequence_asset(resolved, nname, param_path, logger, meta)
                logger.log("UDIM asset: {} [{}:{}]".format(resolved, nname, param_path))
            else:
                meta = {"asset_type": _asset_type(resolved)}
                dh.add_path_and_asset(resolved, nname, param_path, meta)
                logger.log("Asset: {} [{}:{}] exists={}".format(
                    resolved, nname, param_path, os.path.exists(resolved)))

    # Always include the scene file itself
    scene_rel = os.path.relpath(os.path.dirname(scene_path), project_root)
    dh.add_path(scene_path, scene_rel.replace("\\", "/"))

    logger.log("Total assets collected: {}".format(len(dh.assets)))
    logger.log("Total path entries: {}".format(len(dh.path_list)))


def _asset_type(path):
    from libs.katana_constants import (
        CACHE_EXTENSIONS, GEOMETRY_EXTENSIONS, TEXTURE_EXTENSIONS,
    )
    ext = os.path.splitext(path or "")[1].lower()
    if ext in TEXTURE_EXTENSIONS:
        return "texture"
    if ext in CACHE_EXTENSIONS:
        return "cache"
    if ext in GEOMETRY_EXTENSIONS:
        return "geometry"
    return "misc"


# ---------------------------------------------------------------------------
# Caches / bakes split
# ---------------------------------------------------------------------------

def _split_caches_bakes(assets, logger):
    from libs.katana_constants import CACHE_EXTENSIONS, GEOMETRY_EXTENSIONS
    caches, bakes = [], []
    for a in assets:
        src = a.get("source", "")
        ext = os.path.splitext(src)[1].lower()
        item = {
            "path": src, "node": a.get("node", ""),
            "exists": os.path.exists(src),
            "source": a.get("source", ""),
        }
        if ext in CACHE_EXTENSIONS or ext in GEOMETRY_EXTENSIONS:
            item["type"] = "cache" if ext in CACHE_EXTENSIONS else "geometry"
            caches.append(item)
        elif "bake" in src.lower() or "lightmap" in src.lower():
            item["type"] = "texture"
            bakes.append(item)
    logger.log("Caches: {}  Bakes: {}".format(len(caches), len(bakes)))
    return caches, bakes


# ---------------------------------------------------------------------------
# OCIO
# ---------------------------------------------------------------------------

def _collect_ocio(logger):
    ocio_env = os.environ.get("OCIO", "")
    data = {
        "enabled": bool(ocio_env),
        "custom": bool(ocio_env),
        "path": normalize_path(ocio_env),
        "valid": os.path.exists(ocio_env) if ocio_env else False,
    }
    logger.log("OCIO: {}".format(data))
    return data


# ---------------------------------------------------------------------------
# Main analyzer class
# ---------------------------------------------------------------------------

class KatanaAnalyzer:
    def __init__(self, scene_path, sync_dir, profile_json_path, logger, logger_path):
        self.scene_path = normalize_path(scene_path)
        self.sync_dir = normalize_path(sync_dir)
        self.profile_json_path = profile_json_path
        self.logger = logger
        self.logger_path = logger_path

        self._profile_json = {}
        if profile_json_path and os.path.exists(profile_json_path):
            try:
                with open(profile_json_path) as fh:
                    self._profile_json = json.load(fh)
            except Exception as exc:
                logger.log("WARNING: Could not load profile JSON: {}".format(exc))

        self.project_root = get_project_root(scene_path)
        self.dh = DataHandler(self.project_root)

        renderfarm_dir = os.path.join(sync_dir, LOG_DIR)
        os.makedirs(renderfarm_dir, exist_ok=True)

        self.web_json_path = normalize_join(sync_dir, LOG_DIR, WEB_JSON_FILE)
        self.file_list_path = normalize_join(sync_dir, LOG_DIR, FILE_LIST)

        # Register renderfarm output files in the file list
        self.dh.add_path(logger_path, LOG_DIR)
        self.dh.add_path(self.web_json_path, LOG_DIR)
        self.dh.add_path(self.file_list_path, LOG_DIR)

        self.messenger = self._build_messenger()

    def _build_messenger(self):
        if Messenger is None:
            return _NullMessenger()
        m = Messenger()
        m.request_type = "ANALYSIS_PROGRESS"
        m.analysis_profile_key = self._profile_json.get("analysisProfileKey")
        return m

    def run(self):
        self.logger.add_header("KATANA ANALYZER STARTED")
        total_start = time.time()
        stage_times = {}

        def timed(name, fn):
            t = time.time()
            result = fn()
            stage_times[name] = round(time.time() - t, 4)
            return result

        output_data = {}
        try:
            self.messenger.set_progress(5, "Initializing")
            self.logger.log("Scene: {}".format(self.scene_path))
            self.logger.log("Project root: {}".format(self.project_root))
            self.logger.log("Sync dir: {}".format(self.sync_dir))

            # Load scene
            self.messenger.set_progress(10, "Loading scene")
            timed("load_scene", lambda: self._load_scene())

            # Render settings / cameras / AOVs
            self.messenger.set_progress(30, "Collecting render settings")
            render_globals, aovs, cameras, render_nodes = timed(
                "collect_scene_info",
                lambda: collect_scene_info(self.logger),
            )

            # Assets
            self.messenger.set_progress(45, "Collecting assets")
            timed("collect_assets",
                  lambda: _collect_assets(self.scene_path, self.project_root, self.dh, self.logger))

            # OCIO / caches / bakes
            self.messenger.set_progress(65, "Collecting OCIO / caches / bakes")
            ocio_data = timed("collect_ocio", lambda: _collect_ocio(self.logger))
            caches, bakes = timed("split_caches_bakes",
                                  lambda: _split_caches_bakes(self.dh.assets, self.logger))

            # Passes (output EXRs already captured in assets; surface them separately)
            passes = [
                {"name": a.get("node", ""), "path": a.get("source", ""), "type": "output"}
                for a in self.dh.assets
                if os.path.splitext(a.get("source", ""))[1].lower() == ".exr"
                and "out" in a.get("source", "").lower()
            ]

            # UI fields
            self.messenger.set_progress(85, "Generating web UI fields")
            ui_fields_obj = KatanaUIFields(
                self.scene_path, render_globals, cameras, render_nodes,
            )

            # Compose output
            output_data = {
                "dcc": "katana",
                "scene_path": self.scene_path,
                "scene_project_path": self.project_root,
                "assets": self.dh.assets,
                "render_globals": render_globals,
                "renderer": render_globals.get("renderer", "unknown"),
                "device_type": False,
                "aovs": aovs,
                "render_nodes": render_nodes,
                "cameras": cameras,
                "ocio": ocio_data,
                "passes": passes,
                "caches": caches,
                "bakes": bakes,
            }
            output_data.update(ui_fields_obj.serialize())

        except Exception as exc:
            self.logger.log("ERROR in analyzer: {}".format(exc))
            self.logger.log(traceback.format_exc())

        finally:
            output_data["analysis_metrics"] = {
                "total_time": round(time.time() - total_start, 4),
                "stage_times": stage_times,
                "file_count": self.dh.file_count,
                "dir_count": self.dh.dir_count,
                "total_size_mb": round(self.dh.total_size_bytes / (1024 * 1024), 2),
            }

            timed("write_json", lambda: self._write_json(output_data))
            timed("write_file_list", lambda: self.dh.write_file_list(self.file_list_path))

            self.logger.log("Files collected: {}".format(self.dh.file_count))
            self.logger.log("Total size MB: {:.2f}".format(
                self.dh.total_size_bytes / (1024 * 1024)))

            self.messenger.set_progress(100, "Analysis completed")
            self.logger.add_header("KATANA ANALYZER COMPLETED SUCCESSFULLY")

    def _load_scene(self):
        if KatanaFile is None:
            raise RuntimeError("Katana Python modules unavailable. Run inside Katana.")
        self.logger.log("Loading: {}".format(self.scene_path))
        try:
            KatanaFile.Load(self.scene_path)
        except TypeError:
            KatanaFile.Load(self.scene_path, isCrashFile=False)
        self.logger.log("Scene loaded successfully")

    def _write_json(self, data):
        try:
            with open(self.web_json_path, "w") as fh:
                json.dump(data, fh, indent=4, sort_keys=True, default=str)
            self.logger.log("JSON written: {}".format(self.web_json_path))
        except Exception as exc:
            self.logger.log("ERROR writing JSON: {}".format(exc))


# ---------------------------------------------------------------------------
# Null messenger (fallback when core.streamer_com unavailable)
# ---------------------------------------------------------------------------

class _NullMessenger:
    analysis_profile_key = None

    def set_progress(self, pct, status):
        print("Progress: {}% - {}".format(pct, status))


# ---------------------------------------------------------------------------
# Public main() — called by katana_scene_tool or directly
# ---------------------------------------------------------------------------

def main(scene_path, sync_dir, profile_json_path=None):
    logger, logger_path = get_logger(scene_path, sync_dir)
    try:
        analyzer = KatanaAnalyzer(
            scene_path=scene_path,
            sync_dir=sync_dir,
            profile_json_path=profile_json_path,
            logger=logger,
            logger_path=logger_path,
        )
        analyzer.run()
        logger.add_header("SUCCESS")
    except Exception as exc:
        logger.log("FATAL: {}".format(exc))
        logger.log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    _args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if len(_args) < 2:
        print("Usage: katana --batch --script katana_analyzer.py -- <scene.katana> <sync_dir> [profile_json]")
        sys.exit(1)
    main(
        scene_path=os.path.abspath(_args[0]),
        sync_dir=os.path.abspath(_args[1]),
        profile_json_path=_args[2] if len(_args) > 2 else None,
    )
