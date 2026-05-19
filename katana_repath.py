"""
Katana Renderfarm Repath Script.

Loads a synced Katana scene, updates all file-path node parameters to their
server-side target locations, then saves the scene in place.

Called by katana_scene_tool.py or directly:
    katana --batch --script katana_scene_tool.py -- --request <request.json>
"""

import json
import os
import stat
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

from libs.katana_logger import MessageLogger               # noqa: E402
from libs.katana_constants import LOG_DIR, REPATH_LOG_FILE, REPATH_REPORT_FILE  # noqa: E402
from libs.katana_utils import normalize_join, normalize_path  # noqa: E402


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

def _find_node(name):
    """Find a node in the current scene by name."""
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


def _set_param(node, param_path, new_value, logger):
    """Set a string parameter on a node. Returns True on success."""
    try:
        param = node.getParameter(param_path)
        if param is None:
            logger.log("WARNING: param '{}' not found on node '{}'".format(
                param_path, node.getName()))
            return False
        param.setValue(str(new_value), 0)
        return True
    except Exception as exc:
        logger.log("WARNING: Could not set '{}' on '{}': {}".format(
            param_path, node.getName() if node else "?", exc))
        return False


# ---------------------------------------------------------------------------
# Main repath class
# ---------------------------------------------------------------------------

class KatanaRepathAsset:
    def __init__(self, server_project_path, rel_scene_path, json_data_file, logger):
        self.server_project_path = normalize_path(server_project_path)
        self.rel_scene_path = rel_scene_path
        self.scene_path = normalize_join(server_project_path, rel_scene_path)
        self.json_data_file = json_data_file
        self.logger = logger

        self.json_data = {}
        try:
            with open(json_data_file) as fh:
                self.json_data = json.load(fh)
            logger.log("Loaded web_ui_data.json: {}".format(json_data_file))
        except Exception as exc:
            logger.log("ERROR: Could not load JSON: {}".format(exc))

        self.stats = {
            "repathing": {
                "total_assets": 0,
                "successful": 0,
                "failed": 0,
                "missing_files": 0,
                "failed_list": [],
            },
            "settings": {"web_ui_settings_applied": False},
            "execution_time": 0,
        }

    # ------------------------------------------------------------------
    # Scene loading
    # ------------------------------------------------------------------

    def load_scene(self):
        self.logger.add_header("LOADING KATANA SCENE")
        if KatanaFile is None:
            raise RuntimeError("Katana Python modules unavailable. Run inside Katana.")
        if not os.path.exists(self.scene_path):
            raise FileNotFoundError("Scene not found: {}".format(self.scene_path))
        self.logger.log("Scene: {}".format(self.scene_path))
        try:
            KatanaFile.Load(self.scene_path)
        except TypeError:
            KatanaFile.Load(self.scene_path, isCrashFile=False)
        self.logger.log("Scene loaded successfully")

    # ------------------------------------------------------------------
    # Repath node parameters
    # ------------------------------------------------------------------

    def repath_assets(self):
        self.logger.add_header("REPATHING ASSET PARAMETERS")
        assets = self.json_data.get("assets", [])
        self.stats["repathing"]["total_assets"] = len(assets)

        for asset in assets:
            node_name = asset.get("node", "")
            param_path = asset.get("param", "")
            target = asset.get("target", "")

            if not node_name or not param_path or not target:
                continue

            full_target = normalize_join(self.server_project_path, target)
            node = _find_node(node_name)

            if node is None:
                self.logger.log("WARNING: Node '{}' not found — skipping".format(node_name))
                self.stats["repathing"]["failed"] += 1
                self.stats["repathing"]["failed_list"].append(
                    {"node": node_name, "param": param_path, "error": "node not found"})
                continue

            success = _set_param(node, param_path, full_target, self.logger)
            if success:
                self.logger.log("OK  {}:{} -> {}".format(node_name, param_path, full_target))
                self.stats["repathing"]["successful"] += 1
                if not os.path.exists(full_target):
                    self.logger.log(
                        "    WARNING: target does not exist on disk: {}".format(full_target))
                    self.stats["repathing"]["missing_files"] += 1
            else:
                self.stats["repathing"]["failed"] += 1
                self.stats["repathing"]["failed_list"].append(
                    {"node": node_name, "param": param_path, "target": full_target})

        self.logger.log("Repathed {}/{} assets ({} failed)".format(
            self.stats["repathing"]["successful"],
            self.stats["repathing"]["total_assets"],
            self.stats["repathing"]["failed"],
        ))

    # ------------------------------------------------------------------
    # Apply web UI overrides (frame range, resolution, etc.)
    # ------------------------------------------------------------------

    def apply_web_ui_settings(self):
        self.logger.add_header("APPLYING WEB UI SETTING OVERRIDES")
        web_ui_settings = self.json_data.get("web_ui_setting", [])
        if not web_ui_settings:
            self.logger.log("No web_ui_setting entries found")
            return

        skip_names = {
            "app_profile", "render_plugins", "project_name", "scene_file_path",
            "output_path", "render_frames", "frames_per_slice",
            "pretest_first", "pretest_middle", "pretest_last", "pretest_custom_frames",
            "renderPluginsUsed", "is_job_per_render_node",
        }

        frame_map = {
            "startFrame": ("args.renderSettings.startFrame", "startFrame"),
            "endFrame":   ("args.renderSettings.endFrame",   "endFrame"),
            "byFrame":    ("args.renderSettings.byFrame",    "byFrame"),
        }
        res_map = {
            "defaultResolution.width":  ("args.renderSettings.resolutionX", "xRes", "width"),
            "defaultResolution.height": ("args.renderSettings.resolutionY", "yRes", "height"),
        }

        render_settings_nodes = [
            n for n in self.json_data.get("render_nodes", [])
            if n.get("role") == "settings"
        ]

        applied = []
        for setting in web_ui_settings:
            name = setting.get("name", "")
            value = setting.get("current_value")
            if name in skip_names or value is None or value == "":
                continue

            param_candidates = frame_map.get(name) or res_map.get(name)
            if param_candidates and render_settings_nodes:
                for rs in render_settings_nodes:
                    rs_node = _find_node(rs.get("name", ""))
                    if rs_node is None:
                        continue
                    for p in param_candidates:
                        try:
                            param = rs_node.getParameter(p)
                            if param is not None:
                                param.setValue(
                                    float(value) if isinstance(value, (int, float)) else value, 0)
                                self.logger.log("Applied {} = {} on {}.{}".format(
                                    name, value, rs.get("name"), p))
                                applied.append(name)
                                break
                        except Exception:
                            continue
            else:
                for rn in render_settings_nodes:
                    node = _find_node(rn.get("name", ""))
                    if node and _set_param(node, name, value, self.logger):
                        applied.append(name)
                        break

        self.stats["settings"]["web_ui_settings_applied"] = True
        self.logger.log("Web UI overrides applied: {}".format(len(applied)))

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_scene(self):
        self.logger.add_header("SAVING SCENE")
        if KatanaFile is None:
            raise RuntimeError("Katana Python modules unavailable.")
        try:
            if os.path.exists(self.scene_path):
                mode = os.stat(self.scene_path).st_mode
                os.chmod(self.scene_path, mode | stat.S_IWUSR)
            KatanaFile.Save(self.scene_path)
            self.logger.log("Scene saved: {}".format(self.scene_path))
        except Exception as exc:
            self.logger.log("ERROR: Save failed: {}".format(exc))
            raise

    # ------------------------------------------------------------------
    # Validate paths
    # ------------------------------------------------------------------

    def validate_paths(self):
        self.logger.add_header("VALIDATING PATHS")
        missing, found = [], []
        for asset in self.json_data.get("assets", []):
            target = asset.get("target", "")
            if not target:
                continue
            full = normalize_join(self.server_project_path, target)
            if os.path.exists(full):
                found.append(full)
            else:
                missing.append(full)
                self.logger.log("MISSING: {}".format(full))
        self.logger.log("Paths validated — existing: {}  missing: {}".format(
            len(found), len(missing)))

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def generate_report(self):
        report_path = normalize_join(
            self.server_project_path, LOG_DIR, REPATH_REPORT_FILE)
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w") as fh:
                json.dump(self.stats, fh, indent=4)
            self.logger.log("Report saved: {}".format(report_path))
        except Exception as exc:
            self.logger.log("WARNING: Could not write report: {}".format(exc))

        self.logger.add_header("EXECUTION SUMMARY")
        r = self.stats["repathing"]
        self.logger.log("Assets repathed: {}/{}".format(r["successful"], r["total_assets"]))
        self.logger.log("Failed: {}".format(r["failed"]))
        self.logger.log("Missing on disk: {}".format(r["missing_files"]))
        self.logger.log("Execution time: {:.2f}s".format(self.stats["execution_time"]))

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(self):
        start = time.time()
        try:
            self.load_scene()
            self.apply_web_ui_settings()
            self.repath_assets()
            self.validate_paths()
            self.save_scene()
            self.logger.add_header("REPATH COMPLETED SUCCESSFULLY")
            return True
        except Exception as exc:
            self.logger.log("FATAL: {}".format(exc))
            self.logger.log(traceback.format_exc())
            return False
        finally:
            self.stats["execution_time"] = time.time() - start
            try:
                self.generate_report()
            except Exception as exc:
                self.logger.log("WARNING: Report generation failed: {}".format(exc))


# ---------------------------------------------------------------------------
# Public main() — called by katana_scene_tool
# ---------------------------------------------------------------------------

def main(server_project_path, rel_scene_path, web_ui_data_path):
    log_path = normalize_join(server_project_path, LOG_DIR, REPATH_LOG_FILE)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = MessageLogger(log_path, append=True)
    logger.add_header("Katana Repath Script Started")
    logger.log("Server project path: {}".format(server_project_path))
    logger.log("Scene rel path: {}".format(rel_scene_path))
    logger.log("web_ui_data: {}".format(web_ui_data_path))

    handler = KatanaRepathAsset(
        server_project_path=server_project_path,
        rel_scene_path=rel_scene_path,
        json_data_file=web_ui_data_path,
        logger=logger,
    )
    success = handler.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    _args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if len(_args) < 3:
        print("Usage: katana --batch --script katana_repath.py -- "
              "<server_project_path> <rel_scene_path> <web_ui_data.json>")
        sys.exit(1)
    main(_args[0], _args[1], _args[2])
