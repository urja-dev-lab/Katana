"""
Katana Render Script.

Loads a Katana scene, applies web UI overrides (frame range, resolution,
file extension) from a JSON payload in SQN_CLOUD_JOBSLICE_RENDER_PARAMS,
then renders the selected Render nodes.

After render, writes output file paths (one per line, JSON array) to the
file specified by SQN_CLOUD_JOBSLICE_OUTPUT_PATH.

Frame spec formats (pretest_custom_frames field):
    FML        ->  first, middle, last frames of the node's range
    1-10       ->  frames 1 through 10 (byFrame step)
    1:5        ->  frames 1 through 5  (byFrame step, ':' treated same as '-')
    1,5,10     ->  specific frames 1, 5, and 10
    42         ->  single frame 42
    1-10,15    ->  mix of range and explicit frames

Usage:
    katanaBin.exe --batch --script katana_render.py -- <scene.katana>

Environment variables:
    SQN_CLOUD_JOBSLICE_RENDER_PARAMS   JSON string with web_ui_data content
    SQN_CLOUD_JOBSLICE_OUTPUT_PATH     File path to write rendered output paths
"""

import json
import os
import re
import sys
import time
import traceback

try:
    from Katana import KatanaFile, NodegraphAPI
except Exception:
    KatanaFile = None
    NodegraphAPI = None

try:
    from Katana import RenderManager
except Exception:
    RenderManager = None

try:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    CURRENT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

LIBS_DIR = os.path.join(CURRENT_DIR, "libs")
REPO_ROOT = os.path.dirname(CURRENT_DIR)

for _p in (CURRENT_DIR, LIBS_DIR, REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.katana_logger import MessageLogger                               # noqa: E402
from libs.katana_constants import LOG_DIR, RENDER_LOG_FILE                 # noqa: E402
from libs.katana_utils import normalize_join, normalize_path               # noqa: E402

ENV_RENDER_PARAMS = "SQN_CLOUD_JOBSLICE_RENDER_PARAMS"
ENV_OUTPUT_PATH   = "SQN_CLOUD_JOBSLICE_OUTPUT_PATH"

# Katana frame token patterns: ### or #### or # -> zero-padded frame number
_FRAME_TOKEN_RE = re.compile(r'#+')

# Param path on RenderOutputDefine for the output file location
_ROD_LOCATION_PARAM = (
    "args.renderSettings.outputs.outputName"
    ".locationSettings.renderLocation.value"
)


# ---------------------------------------------------------------------------
# Frame spec parsing
# ---------------------------------------------------------------------------

def parse_frame_spec(spec_str, full_start, full_end, by_frame=1):
    """
    Parse a frame specification string into a deduplicated list of
    (start, end, step) tuples, ready to pass to RenderManager.

    Supported tokens (comma or space separated, mixed allowed):
        FML          ->  [(first,first,1), (mid,mid,1), (last,last,1)]
        N-M  / N:M   ->  [(N, M, by_frame)]
        N            ->  [(N, N, 1)]
    """
    if spec_str is None:
        return []
    spec = str(spec_str).strip()
    if not spec:
        return []

    step = max(1, int(by_frame) if by_frame else 1)

    if spec.upper() == "FML":
        first  = int(full_start)
        last   = int(full_end)
        middle = int((full_start + full_end) / 2.0)
        seen_frames = set()
        result = []
        for f in (first, middle, last):
            if f not in seen_frames:
                seen_frames.add(f)
                result.append((f, f, 1))
        return result

    results = []
    seen = set()
    for token in re.split(r'[,\s]+', spec):
        token = token.strip()
        if not token:
            continue
        m = re.match(r'^(-?\d+)[-:](-?\d+)$', token)
        if m:
            s, e = int(m.group(1)), int(m.group(2))
            key = (s, e, step)
            if key not in seen:
                seen.add(key)
                results.append(key)
            continue
        try:
            f = int(float(token))
            key = (f, f, 1)
            if key not in seen:
                seen.add(key)
                results.append(key)
        except ValueError:
            pass

    return results


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

def _find_node(name):
    """Find a node anywhere in the scene graph by name."""
    if NodegraphAPI is None:
        return None
    fn = getattr(NodegraphAPI, "GetNode", None)
    if callable(fn):
        try:
            node = fn(name)
            if node is not None:
                return node
        except Exception:
            pass
    try:
        for node in NodegraphAPI.GetAllNodes():
            try:
                if node.getName() == name:
                    return node
            except Exception:
                pass
    except Exception:
        pass
    return None


def _set_param(node, param_path, value, logger):
    """Set a single param. Returns True on success."""
    try:
        param = node.getParameter(param_path)
        if param is None:
            return False
        param.setValue(value, 0)
        return True
    except Exception as exc:
        logger.log("    WARN set {}.{}: {}".format(
            node.getName() if node else "?", param_path, exc))
        return False


def _get_param_value(node, param_path):
    """Read a param value. Returns None on failure."""
    try:
        param = node.getParameter(param_path)
        if param is not None:
            return param.getValue(0)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Override helpers
# ---------------------------------------------------------------------------

def apply_resolution_override(rnode_data, width, height, logger):
    """
    Push width/height to all RenderSettings nodes listed in
    rnode_data['resolution']['all'].  Tries resolutionX/Y params first,
    then falls back to writing a 'WxH' string to resolution.value.
    """
    res_nodes = rnode_data.get("resolution", {}).get("all", [])
    if not res_nodes:
        logger.log("  No RenderSettings nodes in resolution data — skipping")
        return

    w, h = float(width), float(height)
    res_str = "{}x{}".format(int(w), int(h))

    for entry in res_nodes:
        node_name = entry.get("node", "")
        node = _find_node(node_name)
        if node is None:
            logger.log("  WARN: RenderSettings node '{}' not found".format(node_name))
            continue

        set_x = (
            _set_param(node, "args.renderSettings.resolutionX", w, logger) or
            _set_param(node, "xRes", w, logger) or
            _set_param(node, "width", w, logger)
        )
        set_y = (
            _set_param(node, "args.renderSettings.resolutionY", h, logger) or
            _set_param(node, "yRes", h, logger) or
            _set_param(node, "height", h, logger)
        )

        if set_x and set_y:
            logger.log("  Resolution {}x{} -> {}".format(int(w), int(h), node_name))
        else:
            if _set_param(node, "args.renderSettings.resolution.value", res_str, logger):
                logger.log("  Resolution {} -> {} (value fallback)".format(res_str, node_name))
            else:
                logger.log("  WARN: Could not set resolution on {}".format(node_name))


def apply_file_extension_override(rnode_data, ext, logger):
    """
    Set file extension on every RenderOutputDefine node listed in
    rnode_data['file_extension']['outputs'].
    Also enables the fileExtension override flag so the param takes effect.
    """
    outputs = rnode_data.get("file_extension", {}).get("outputs", [])
    if not outputs:
        logger.log("  No RenderOutputDefine outputs in data — skipping")
        return

    ext_clean = ext.lstrip(".").lower()
    _EXT_VALUE  = "args.renderSettings.outputs.outputName.rendererSettings.fileExtension.value"
    _EXT_ENABLE = "args.renderSettings.outputs.outputName.rendererSettings.fileExtension.enable"

    for output in outputs:
        node_name = output.get("node", "")
        node = _find_node(node_name)
        if node is None:
            logger.log("  WARN: RenderOutputDefine '{}' not found".format(node_name))
            continue
        _set_param(node, _EXT_ENABLE, 1, logger)
        if _set_param(node, _EXT_VALUE, ext_clean, logger):
            logger.log("  Extension '{}' -> {} [{}]".format(
                ext_clean, node_name, output.get("output_name", "?")))
        else:
            logger.log("  WARN: Could not set extension on {}".format(node_name))


# ---------------------------------------------------------------------------
# Output path collection
# ---------------------------------------------------------------------------

def _expand_frame_token(path_pattern, frame):
    """Replace Katana # tokens with zero-padded frame number."""
    def replace(m):
        width = max(len(m.group(0)), 4)
        return str(frame).zfill(width)
    return _FRAME_TOKEN_RE.sub(replace, path_pattern)


def collect_output_paths(node_data, frame_ranges, logger):
    """
    Read renderLocation params from each RenderOutputDefine node and
    expand frame tokens for all rendered frames.
    Returns a list of file path strings.
    """
    outputs = node_data.get("file_extension", {}).get("outputs", [])
    paths = []
    for output in outputs:
        rod_name = output.get("node", "")
        rod_node = _find_node(rod_name)
        if rod_node is None:
            continue
        pattern = _get_param_value(rod_node, _ROD_LOCATION_PARAM)
        if not pattern:
            continue
        if "#" in pattern:
            for start, end, step in frame_ranges:
                frame = start
                while frame <= end:
                    paths.append(_expand_frame_token(pattern, frame))
                    frame += step
        else:
            paths.append(pattern)
    return paths


# ---------------------------------------------------------------------------
# Render trigger
# ---------------------------------------------------------------------------

def _do_render(node_name, start, end, step, logger):
    """
    Try every known Katana batch-render API in order.
    Returns True on success.
    """
    node_obj = _find_node(node_name)

    if RenderManager is not None:
        # StartRenderLegacy — blocking disk render (Katana 8)
        if node_obj is not None:
            for kwargs in [
                dict(node=node_obj, frame=start, interactive=False, asynch=False),
                dict(node=node_obj, interactive=False, asynch=False),
                dict(node=node_obj, asynch=False),
            ]:
                try:
                    RenderManager.StartRenderLegacy(**kwargs)
                    return True
                except Exception:
                    pass

        # StartRender — try common method name strings
        for method in ("Disk Render", "Interactive", "Process", "Batch"):
            for extra in (
                dict(serialDiskRenderNodeList=[node_obj]) if node_obj else {},
                dict(node=node_obj) if node_obj else {},
                {},
            ):
                try:
                    RenderManager.StartRender(method, **extra)
                    return True
                except Exception:
                    pass

    if node_obj is not None:
        try:
            node_obj.render(start, end, step)
            return True
        except Exception:
            pass

    logger.log("  ERROR: No working render API found for '{}'".format(node_name))
    return False


def trigger_render(node_name, frame_ranges, logger):
    """Render a list of (start, end, step) tuples. Returns True if all succeed."""
    all_ok = True
    for start, end, step in frame_ranges:
        logger.log("  Rendering '{}' frames {}-{} step {}".format(node_name, start, end, step))
        if NodegraphAPI is not None:
            try:
                NodegraphAPI.SetWorkingInTime(start)
                NodegraphAPI.SetWorkingOutTime(end)
            except Exception:
                pass
        ok = _do_render(node_name, start, end, step, logger)
        if ok:
            logger.log("  Done: {}-{}".format(start, end))
        else:
            logger.log("  FAILED: {}-{}".format(start, end))
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Main job class
# ---------------------------------------------------------------------------

class KatanaRenderJob:
    def __init__(self, scene_path, logger):
        self.scene_path = normalize_path(scene_path)
        self.logger = logger
        self.json_data = {}
        self.settings = {}  # flat {name: current_value}
        self.output_paths = []

        params_str = os.environ.get(ENV_RENDER_PARAMS, "")
        if not params_str:
            logger.log("ERROR: {} env var is empty or not set".format(ENV_RENDER_PARAMS))
        else:
            try:
                self.json_data = json.loads(params_str)
                logger.log("Loaded render params from {}".format(ENV_RENDER_PARAMS))
            except Exception as exc:
                logger.log("ERROR: Could not parse {}: {}".format(ENV_RENDER_PARAMS, exc))

        for entry in self.json_data.get("web_ui_setting", []):
            name = entry.get("name", "")
            if name:
                self.settings[name] = entry.get("current_value")

        self.stats = {
            "nodes_rendered": 0,
            "nodes_failed": 0,
            "frames_total": 0,
            "execution_time": 0.0,
        }

    # ------------------------------------------------------------------
    # Scene load
    # ------------------------------------------------------------------

    def load_scene(self):
        self.logger.add_header("LOADING SCENE")
        if KatanaFile is None:
            raise RuntimeError("Katana Python modules unavailable — run inside Katana")
        if not os.path.exists(self.scene_path):
            raise FileNotFoundError("Scene not found: {}".format(self.scene_path))
        try:
            KatanaFile.Load(self.scene_path)
        except TypeError:
            KatanaFile.Load(self.scene_path, isCrashFile=False)
        self.logger.log("Loaded: {}".format(self.scene_path))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_render_nodes(self):
        """Return [(node_name, node_data)] for render nodes with checked=True."""
        selected = []
        for entry in self.json_data.get("render_nodes", []):
            for node_name, node_data in entry.items():
                if node_data.get("role") != "render":
                    continue
                # Default True when no explicit checkbox entry exists
                checked = self.settings.get(node_name, True)
                if checked:
                    selected.append((node_name, node_data))
        return selected

    def _build_frame_ranges(self, node_start, node_end):
        """
        Build frame ranges for one render node using web_ui_setting overrides.

        Decision tree:
          1. render_frames == "Full Range"   -> (node_start, node_end, byFrame)
          2. pretest checkboxes selected     -> FML subset
          3. pretest_custom_frames has text  -> parse the spec string
          4. startFrame / endFrame in settings -> use those
          5. fallback                        -> (node_start, node_end, byFrame)
        """
        by_frame = max(1, int(self.settings.get("byFrame", 1) or 1))
        toggle   = str(self.settings.get("render_frames", "Full Range") or "Full Range")

        if toggle == "Full Range":
            return [(int(node_start), int(node_end), by_frame)]

        # --- Custom Range ---
        use_first  = bool(self.settings.get("pretest_first",  False))
        use_middle = bool(self.settings.get("pretest_middle", False))
        use_last   = bool(self.settings.get("pretest_last",   False))
        custom_spec = str(self.settings.get("pretest_custom_frames", "") or "").strip()

        if use_first or use_middle or use_last:
            first  = int(node_start)
            last   = int(node_end)
            middle = int((node_start + node_end) / 2.0)
            seen   = set()
            ranges = []
            for flag, frame in ((use_first, first), (use_middle, middle), (use_last, last)):
                if flag and frame not in seen:
                    seen.add(frame)
                    ranges.append((frame, frame, 1))
            return ranges

        if custom_spec:
            parsed = parse_frame_spec(custom_spec, node_start, node_end, by_frame)
            if parsed:
                return parsed

        # startFrame / endFrame overrides
        s = self.settings.get("startFrame", node_start)
        e = self.settings.get("endFrame",   node_end)
        return [(int(s), int(e), by_frame)]

    # ------------------------------------------------------------------
    # Core render loop
    # ------------------------------------------------------------------

    def _render_all(self):
        self.logger.add_header("RENDER SETTINGS")

        selected = self._selected_render_nodes()
        if not selected:
            self.logger.log("No Render nodes selected — nothing to render")
            return

        width  = self.settings.get("defaultResolution.width")
        height = self.settings.get("defaultResolution.height")
        has_res = bool(width and height)

        ext_override = (self.settings.get("file_extension") or
                        self.settings.get("fileExtension") or "")
        has_ext = bool(ext_override)

        self.logger.log("Selected nodes: {}".format([n for n, _ in selected]))
        if has_res:
            self.logger.log("Resolution override: {}x{}".format(int(width), int(height)))
        if has_ext:
            self.logger.log("Extension override: {}".format(ext_override))

        self.logger.add_header("RENDERING")

        for node_name, node_data in selected:
            self.logger.log("=== {} ===".format(node_name))

            fr = node_data.get("frame_range", {})
            node_start = fr.get("start_frame") or self.settings.get("startFrame", 1)
            node_end   = fr.get("end_frame")   or self.settings.get("endFrame",   1)

            frame_ranges = self._build_frame_ranges(node_start, node_end)
            self.logger.log("  Frame ranges: {}".format(frame_ranges))

            frames_count = sum((e - s) // step + 1 for s, e, step in frame_ranges)
            self.stats["frames_total"] += frames_count

            if has_res:
                apply_resolution_override(node_data, width, height, self.logger)

            if has_ext:
                apply_file_extension_override(node_data, ext_override, self.logger)

            ok = trigger_render(node_name, frame_ranges, self.logger)
            if ok:
                self.stats["nodes_rendered"] += 1
                paths = collect_output_paths(node_data, frame_ranges, self.logger)
                self.output_paths.extend(paths)
                self.logger.log("  Output paths collected: {}".format(len(paths)))
            else:
                self.stats["nodes_failed"] += 1

    # ------------------------------------------------------------------
    # Write output paths
    # ------------------------------------------------------------------

    def _write_output_paths(self):
        out_file = os.environ.get(ENV_OUTPUT_PATH, "")
        if not out_file:
            self.logger.log(
                "WARN: {} not set — output paths not written".format(ENV_OUTPUT_PATH)
            )
            return
        try:
            out_dir = os.path.dirname(out_file)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(out_file, "w") as fh:
                json.dump(self.output_paths, fh, indent=2)
            self.logger.log("Output paths written to: {}".format(out_file))
            self.logger.log("  {} path(s)".format(len(self.output_paths)))
        except Exception as exc:
            self.logger.log("ERROR: Could not write output paths: {}".format(exc))

    # ------------------------------------------------------------------
    # Report + orchestration
    # ------------------------------------------------------------------

    def _report(self):
        self.logger.add_header("RENDER SUMMARY")
        self.logger.log("Nodes rendered : {}".format(self.stats["nodes_rendered"]))
        self.logger.log("Nodes failed   : {}".format(self.stats["nodes_failed"]))
        self.logger.log("Frames total   : {}".format(self.stats["frames_total"]))
        self.logger.log("Execution time : {:.2f}s".format(self.stats["execution_time"]))

    def run(self):
        t0 = time.time()
        success = False
        try:
            self.load_scene()
            self._render_all()
            self._write_output_paths()
            success = self.stats["nodes_failed"] == 0
            if success:
                self.logger.add_header("RENDER COMPLETED SUCCESSFULLY")
            else:
                self.logger.add_header("RENDER COMPLETED WITH ERRORS")
        except Exception as exc:
            self.logger.log("FATAL: {}".format(exc))
            self.logger.log(traceback.format_exc())
        finally:
            self.stats["execution_time"] = time.time() - t0
            self._report()
        return success


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def main(scene_path):
    log_dir  = os.path.dirname(os.path.abspath(scene_path))
    log_path = normalize_join(log_dir, RENDER_LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)

    logger = MessageLogger(log_path, append=True)
    logger.add_header("Katana Render Script Started")
    logger.log("Scene: {}".format(scene_path))
    logger.log("{}: {}".format(
        ENV_RENDER_PARAMS,
        "(set, {} chars)".format(len(os.environ.get(ENV_RENDER_PARAMS, "")))
        if os.environ.get(ENV_RENDER_PARAMS) else "(NOT SET)"
    ))
    logger.log("{}: {}".format(
        ENV_OUTPUT_PATH,
        os.environ.get(ENV_OUTPUT_PATH, "(NOT SET)")
    ))

    job = KatanaRenderJob(scene_path, logger)
    success = job.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    _args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if len(_args) < 1:
        print("Usage: katanaBin.exe --batch --script katana_render.py -- <scene.katana>")
        print("Env:   {} = <json string>".format(ENV_RENDER_PARAMS))
        print("Env:   {} = <output file path>".format(ENV_OUTPUT_PATH))
        sys.exit(1)
    main(_args[0])
