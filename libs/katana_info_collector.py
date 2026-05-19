"""
Collects render settings, cameras, AOVs, and render node info from a loaded Katana scene.
All methods are safe to call: they catch exceptions and fall back gracefully.
"""

try:
    from Katana import NodegraphAPI
except Exception:
    NodegraphAPI = None


# ---------------------------------------------------------------------------
# Node/param helpers (duplicated here so this module is self-contained)
# ---------------------------------------------------------------------------

def _iter_nodes():
    if NodegraphAPI is None:
        return []
    try:
        return list(NodegraphAPI.GetAllNodes())
    except Exception:
        return []


def _node_type(node):
    try:
        return str(node.getType())
    except Exception:
        return ""


def _node_name(node):
    try:
        return str(node.getName())
    except Exception:
        return str(node)


def _get_param_value(node, *paths):
    """Try each parameter path in order; return (value, path_used) or (None, None)."""
    for path in paths:
        try:
            param = node.getParameter(path)
            if param is not None:
                val = param.getValue(0)
                if val is not None and val != "":
                    return val, path
        except Exception:
            continue
    return None, None


# ---------------------------------------------------------------------------
# Renderer detection — inferred from renderer-specific settings node types
# ---------------------------------------------------------------------------

_RENDERER_NODE_TYPES = {
    "ArnoldGlobalSettings":    "arnold",
    "ArnoldGlobalStatements":  "arnold",
    "PrmanGlobalStatements":   "prman",
    "PrmanGlobalSettings":     "prman",
    "RedshiftOptions":         "redshift",
    "RedshiftMaterial":        "redshift",
    "VRayFarmerSettings":      "vray",
    "DlGlobalStatements":      "3delight",
    "dl_RenderSettings":       "3delight",
}


# ---------------------------------------------------------------------------
# Resolution lookup via Katana's ResolutionTable API
# ---------------------------------------------------------------------------

def _resolve_named_resolution(res_name, render_globals):
    """Convert a named Katana resolution preset (e.g. 'HD') to pixel dimensions."""
    if not isinstance(res_name, str) or not res_name:
        return
    # If it looks numeric, parse directly
    try:
        render_globals["width"] = int(res_name)
        return
    except (ValueError, TypeError):
        pass
    try:
        from Katana import ResolutionTable
        table = ResolutionTable.GetResolutionTable()
        entry = table.getResolution(res_name)
        if entry:
            render_globals["width"]  = entry.xres()
            render_globals["height"] = entry.yres()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# RenderSettings node extraction
# ---------------------------------------------------------------------------

_START_FRAME_PATHS = ["args.renderSettings.startFrame", "startFrame", "start_frame"]
_END_FRAME_PATHS   = ["args.renderSettings.endFrame",   "endFrame",   "end_frame"]
_FPS_PATHS         = ["args.renderSettings.fps", "fps", "framesPerSecond"]
_RENDERER_PATHS    = ["args.renderSettings.renderer.value", "args.renderSettings.renderer",
                      "renderer", "rendererName"]
_RESOLUTION_NAME_PATHS = ["args.renderSettings.resolution.value", "args.renderSettings.resolution"]
_RESOLUTION_X_PATHS = ["args.renderSettings.resolutionX", "xRes", "resolutionX", "width"]
_RESOLUTION_Y_PATHS = ["args.renderSettings.resolutionY", "yRes", "resolutionY", "height"]


def _try_extract_from_render_settings_node(node, render_globals, log):
    # Frame range
    start, _ = _get_param_value(node, *_START_FRAME_PATHS)
    end,   _ = _get_param_value(node, *_END_FRAME_PATHS)
    fps,   _ = _get_param_value(node, *_FPS_PATHS)
    if start is not None:
        render_globals["startFrame"] = float(start)
    if end is not None:
        render_globals["endFrame"] = float(end)
    if fps is not None and fps:
        render_globals["fps"] = float(fps)

    # Renderer (empty string is common — inferred from ArnoldGlobalSettings instead)
    renderer, _ = _get_param_value(node, *_RENDERER_PATHS)
    if renderer and render_globals.get("renderer", "unknown") == "unknown":
        render_globals["renderer"] = str(renderer).lower()

    # Resolution — try named preset first, then direct integer paths
    if render_globals.get("width", 0) == 0:
        res_name, _ = _get_param_value(node, *_RESOLUTION_NAME_PATHS)
        if res_name:
            _resolve_named_resolution(res_name, render_globals)

    if render_globals.get("width", 0) == 0:
        w, _ = _get_param_value(node, *_RESOLUTION_X_PATHS)
        h, _ = _get_param_value(node, *_RESOLUTION_Y_PATHS)
        if w:
            render_globals["width"]  = int(w)
        if h:
            render_globals["height"] = int(h)

    # Legacy renderOutputs group (older Katana AOV style)
    aovs = []
    try:
        outputs_param = node.getParameter("renderOutputs")
        if outputs_param is not None:
            for i in range(outputs_param.getNumChildren()):
                child = outputs_param.getChild(i)
                if child is None:
                    continue
                name_p = child.getChild("name")
                type_p = child.getChild("type")
                aov_name = name_p.getValue(0) if name_p else str(i)
                aov_type = type_p.getValue(0) if type_p else "unknown"
                aovs.append({"name": str(aov_name), "type": str(aov_type)})
    except Exception:
        pass
    return aovs


def _try_extract_output_path(node, render_globals):
    for path in ("outputLocation", "outputPath", "location", "outputDirectory",
                 "args.renderSettings.outputLocation"):
        try:
            param = node.getParameter(path)
            if param is not None:
                val = param.getValue(0)
                if val and str(val).strip():
                    render_globals["output_path"] = str(val).replace("\\", "/")
                    return
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect_scene_info(log):
    """
    Walk all loaded Katana nodes and extract render globals, cameras, AOVs, render nodes.
    Returns: (render_globals dict, aovs list, cameras list, render_nodes list)
    """
    render_globals = {
        "startFrame": 1.0,
        "endFrame": 1.0,
        "byFrame": 1.0,
        "width": 0,
        "height": 0,
        "fps": 24.0,
        "renderer": "unknown",
        "output_path": "",
    }
    aovs = []
    render_nodes = []
    cameras = []

    for node in _iter_nodes():
        ntype = _node_type(node)
        nname = _node_name(node)
        ntype_lower = ntype.lower()

        # Renderer inference from renderer-specific settings nodes
        if ntype in _RENDERER_NODE_TYPES and render_globals.get("renderer", "unknown") == "unknown":
            render_globals["renderer"] = _RENDERER_NODE_TYPES[ntype]

        # Camera detection — only actual Camera node types, not nodes with "cam" in name
        if ntype in ("CameraCreate", "Camera") or ntype_lower == "camera":
            cameras.append(nname)

        # RenderSettings nodes — resolution, frame range, legacy AOVs
        if ntype == "RenderSettings":
            render_nodes.append({"name": nname, "type": ntype, "role": "settings"})
            try:
                node_aovs = _try_extract_from_render_settings_node(node, render_globals, log)
                aovs.extend(node_aovs)
            except Exception as exc:
                log.log("WARNING: Could not extract render settings from '{}': {}".format(nname, exc))

        # RenderOutputDefine nodes — primary AOV source in Katana 7+
        elif ntype == "RenderOutputDefine":
            try:
                name_val, _ = _get_param_value(node, "outputName", "name")
                # Extract output type from renderer+type hint stored on the node
                type_str = "unknown"
                try:
                    p = node.getParameter("args.__lastRendererAndOutputType")
                    if p:
                        raw = p.getValue(0)
                        type_str = raw.split(":")[-1] if raw and ":" in raw else (raw or "unknown")
                except Exception:
                    pass
                if name_val and str(name_val).strip():
                    aovs.append({"name": str(name_val), "type": type_str})
            except Exception:
                pass

        # Render execution nodes
        elif ntype in ("Render", "RenderNode", "DeferredRender"):
            render_nodes.append({"name": nname, "type": ntype, "role": "render"})
            try:
                _try_extract_output_path(node, render_globals)
            except Exception:
                pass

        # Catch-all for any render-related nodes not covered above
        elif "render" in ntype_lower and "settings" not in ntype_lower and \
                "filter" not in ntype_lower and "output" not in ntype_lower:
            render_nodes.append({"name": nname, "type": ntype, "role": "render"})

    log.log("Render globals collected: {}".format(render_globals))
    log.log("Render nodes: {}".format(len(render_nodes)))
    log.log("Cameras: {}".format(cameras))
    log.log("AOVs: {}".format(len(aovs)))

    # Deduplicate AOVs
    seen_aovs = set()
    unique_aovs = []
    for a in aovs:
        key = (a.get("name"), a.get("type"))
        if key not in seen_aovs:
            seen_aovs.add(key)
            unique_aovs.append(a)

    return render_globals, unique_aovs, sorted(set(cameras)), render_nodes
