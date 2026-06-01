"""
Katana web-UI form fields.  Mirrors the structure of MayaUIFields so the same
render-farm web UI can drive both DCCs.

Section index map:
    0 — Lease / Job Details
    1 — Local Project Settings
    2 — Render Frames
    3 — Image Details
    4 — Render Nodes
    5 — Renderer Pool
    6 — Current Renderer
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from core import BaseUIFields  # noqa: E402


_RENDERER_POOL = {
    "arnold":    {"gpu": False, "win": False, "lin": True},
    "renderman": {"gpu": False, "win": False, "lin": True},
    "prman":     {"gpu": False, "win": False, "lin": True},
    "redshift":  {"gpu": True,  "win": True,  "lin": False},
    "vray":      {"gpu": False, "win": True,  "lin": True},
    "cycles":    {"gpu": True,  "win": False, "lin": True},
}

_KNOWN_RENDERERS = ["ARNOLD", "REDSHIFT", "RENDERMAN", "VRAY", "CYCLES"]


class KatanaUIFields(BaseUIFields):
    def __init__(self, scene_path, render_globals, cameras, render_nodes):
        super().__init__()

        renderer = str(render_globals.get("renderer", "unknown")).lower()
        pool = _RENDERER_POOL.get(renderer, {"gpu": False, "win": False, "lin": True})
        use_gpu = pool["gpu"]
        use_win = pool["win"]
        use_lin = pool["lin"]

        start = render_globals.get("startFrame", 1)
        end   = render_globals.get("endFrame",   1)
        step  = render_globals.get("byFrame",    1)
        width  = render_globals.get("width",  0)
        height = render_globals.get("height", 0)
        output = render_globals.get("output_path", "")

        # ------------------------------------------------------------------
        # SECTION 0 — Lease / Job Details
        # ------------------------------------------------------------------
        self.add_text_field("app_profile",       "Lease / Job Details", "App Profile",    0, 0, "",             0)
        self.add_text_field("renderPluginsUsed",  "Lease / Job Details", "Plugins",        1, 0, renderer.upper() if renderer != "unknown" else "", 0)
        self.add_select_field("project_name",    "Lease / Job Details", "Select Project", 2, 0, [], "default lease", 0)

        # ------------------------------------------------------------------
        # SECTION 1 — Local Project Settings
        # ------------------------------------------------------------------
        self.add_text_field("scene_file_path", "Local Project Settings", "Scene File Path", 0, 0, scene_path, 1)
        self.add_text_field("output_path",     "Local Project Settings", "Output Path",     1, 0, output,     1)

        # ------------------------------------------------------------------
        # SECTION 2 — Render Frames
        # ------------------------------------------------------------------
        self.add_toggle_field(
            "render_frames", "Render Frames", 0, 0, "", 2,
            "Custom Range", "Full Range",
            {
                "onNo":  ["byFrame", "frames_per_slice"],
                "onYes": ["pretest_first", "pretest_middle", "pretest_last",
                          "pretest_custom_frames", "startFrame", "endFrame"],
            },
        )
        self.add_checkbox_field("pretest_first",        "Render Frames", "First",  1, 0, True,  2)
        self.add_checkbox_field("pretest_middle",       "Render Frames", "Middle", 1, 1, True,  2)
        self.add_checkbox_field("pretest_last",         "Render Frames", "Last",   1, 2, True,  2)
        self.add_text_field(   "pretest_custom_frames", "Render Frames", "Custom", 1, 3, "",    2)
        self.add_int_field("startFrame",       "Render Frames", "Start Frame",      2, 4, int(start), 2)
        self.add_int_field("endFrame",         "Render Frames", "End Frame",        3, 5, int(end),   2)
        self.add_int_field("byFrame",          "Render Frames", "Step Frame",       4, 6, int(step),  2)
        self.add_text_field("frames_per_slice","Render Frames", "Frames Per Slice", 5, 7, "1",        2)

        # ------------------------------------------------------------------
        # SECTION 3 — Image Details
        # ------------------------------------------------------------------
        camera_list = cameras if cameras else []
        default_cam = camera_list[0] if camera_list else ""
        self.add_select_field("all_renderable_cameras", "Image Details", "Camera",       0, 0, camera_list, default_cam, 3)
        self.add_text_field("defaultResolution.width",  "Image Details", "Image Width",  1, 0, width,  3)
        self.add_text_field("defaultResolution.height", "Image Details", "Image Height", 2, 0, height, 3)

        # File extension — default from the first render node's detected extension
        _detected_exts = [
            data.get("file_extension", {}).get("final")
            for entry in render_nodes
            for data in entry.values()
            if data.get("file_extension", {}).get("final")
        ]
        _default_ext = _detected_exts[0] if _detected_exts else "exr"
        self.add_select_field(
            "file_extension", "Image Details", "File Extension",
            3, 0, ["exr", "png", "jpeg", "tiff"], _default_ext, 3,
        )

        # ------------------------------------------------------------------
        # SECTION 4 — Render Nodes
        # ------------------------------------------------------------------
        self.add_checkbox_field("is_job_per_render_node", "Render Nodes", "Single Job / Job Per Node", 0, 0, False, 4)
        for i, rnode_entry in enumerate(render_nodes):
            for nname, rnode_data in rnode_entry.items():
                if rnode_data.get("role", "render") == "render":
                    self.add_checkbox_field(nname, "Render Nodes", nname, i + 1, 0, True, 4)

        # ------------------------------------------------------------------
        # SECTION 5 — Renderer Pool
        # ------------------------------------------------------------------
        self.add_checkbox_field("useGpu", "Renderer Pool", "GPU", 0, 0, use_gpu, 5)
        self.add_checkbox_field("useWin", "Renderer Pool", "WIN", 1, 0, use_win, 5)
        self.add_checkbox_field("useLin", "Renderer Pool", "LIN", 2, 0, use_lin, 5)

        # ------------------------------------------------------------------
        # SECTION 6 — Current Renderer
        # ------------------------------------------------------------------
        for i, rdr in enumerate(_KNOWN_RENDERERS):
            self.add_checkbox_field(rdr, "Current Renderer", rdr, i, 0, renderer.upper() == rdr, 6)
