"""
Collects render settings, cameras, AOVs, and render node info from a loaded Katana scene.
All methods are safe to call: they catch exceptions and fall back gracefully.
"""

import re as _re
from collections import Counter as _Counter, deque as _deque

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
# Per-Render-node upstream data helpers (adapted from katana_render_modifier)
# ---------------------------------------------------------------------------

_FRAME_RANGE_PARAM_PAIRS = [
    ("user.start_frame",  "user.end_frame"),
    ("user.startFrame",   "user.endFrame"),
    ("startFrame",        "endFrame"),
    ("start_frame",       "end_frame"),
    ("args.renderSettings.startTime.value", "args.renderSettings.stopTime.value"),
]

_RS_RESOLUTION_VALUE  = "args.renderSettings.resolution.value"
_RS_RESOLUTION_ENABLE = "args.renderSettings.resolution.enable"
_ROD_EXT_VALUE  = "args.renderSettings.outputs.outputName.rendererSettings.fileExtension.value"
_ROD_EXT_ENABLE = "args.renderSettings.outputs.outputName.rendererSettings.fileExtension.enable"
_ROD_OUT_NAME   = "outputName"


def _pget_simple(node, dot_path):
    """Get param value at frame 0 via dot_path; return None if missing."""
    try:
        param = node.getParameter(dot_path)
        if param is None:
            return None
        return param.getValue(0)
    except Exception:
        return None


def _build_all_nodes_map():
    """Recursively walk the full node graph; return {name: node}."""
    if NodegraphAPI is None:
        return {}
    result = {}

    def _walk(n):
        try:
            result[n.getName()] = n
        except Exception:
            return
        try:
            for child in n.getChildren():
                _walk(child)
        except AttributeError:
            pass

    try:
        _walk(NodegraphAPI.GetRootNode())
    except Exception:
        pass
    return result


def _get_upstream_nodes(start_node):
    """BFS upstream from start_node, following input ports and expanding Group children."""
    visited = {}
    queue = _deque([start_node])
    while queue:
        node = queue.popleft()
        try:
            name = node.getName()
        except Exception:
            continue
        if name in visited:
            continue
        visited[name] = node
        try:
            for port in node.getInputPorts():
                conn = port.getConnectedPort(0)
                if conn is not None:
                    up = conn.getNode()
                    if up.getName() not in visited:
                        queue.append(up)
        except Exception:
            pass
        try:
            for child in node.getChildren():
                if child.getName() not in visited:
                    queue.append(child)
        except AttributeError:
            pass
    return visited


def _resolve_resolution_value(value):
    """Return 'WxH' string for a raw resolution value or named preset."""
    if value is None:
        return None
    s = str(value).strip()
    m = _re.match(r'^(\d+)\s*[xX]\s*(\d+)$', s)
    if m:
        return "{}x{}".format(m.group(1), m.group(2))
    try:
        from Katana import ResolutionTable
        table = ResolutionTable.GetResolutionTable()
        entry = table.getResolution(s)
        if entry:
            return "{}x{}  ({})".format(entry.xres(), entry.yres(), s)
    except Exception:
        pass
    return s


def _collect_render_node_data(node_obj, upstream_map):
    """
    Collect frame_range, resolution, and file_extension for one Render node.
    Returns a dict matching the structure produced by katana_render_modifier.get_render_data().
    """
    # --- frame range ---
    node_sf = node_ef = fr_source = None
    for sp, ep in _FRAME_RANGE_PARAM_PAIRS:
        for name, node in upstream_map.items():
            try:
                if node.getType() == "Render":
                    continue
            except Exception:
                continue
            sv = _pget_simple(node, sp)
            ev = _pget_simple(node, ep)
            if sv is not None and ev is not None:
                node_sf, node_ef, fr_source = sv, ev, name
                break
        if node_sf is not None:
            break

    in_t = out_t = win_t = wout_t = None
    if NodegraphAPI is not None:
        try:
            in_t   = NodegraphAPI.GetInTime()
            out_t  = NodegraphAPI.GetOutTime()
            win_t  = NodegraphAPI.GetWorkingInTime()
            wout_t = NodegraphAPI.GetWorkingOutTime()
        except Exception:
            pass

    frame_range = {
        "start_frame":           node_sf,
        "end_frame":             node_ef,
        "source_node":           fr_source,
        "nodegraph_in":          in_t,
        "nodegraph_out":         out_t,
        "nodegraph_working_in":  win_t,
        "nodegraph_working_out": wout_t,
    }

    # --- resolution ---
    res_all = []
    for name, node in upstream_map.items():
        try:
            if node.getType() != "RenderSettings":
                continue
        except Exception:
            continue
        raw     = _pget_simple(node, _RS_RESOLUTION_VALUE)
        enabled = bool(_pget_simple(node, _RS_RESOLUTION_ENABLE))
        res_all.append({
            "node":    name,
            "raw":     raw,
            "value":   _resolve_resolution_value(raw),
            "enabled": enabled,
        })
    primary_res = next((r for r in res_all if r["enabled"]), res_all[0] if res_all else None)
    resolution = {
        "value":       primary_res["value"]   if primary_res else None,
        "raw":         primary_res["raw"]     if primary_res else None,
        "source_node": primary_res["node"]    if primary_res else None,
        "enabled":     primary_res["enabled"] if primary_res else False,
        "all":         res_all,
    }

    # --- file extension ---
    outputs = []
    for name, node in upstream_map.items():
        try:
            if node.getType() != "RenderOutputDefine":
                continue
        except Exception:
            continue
        output_name = _pget_simple(node, _ROD_OUT_NAME) or "?"
        ext_value   = _pget_simple(node, _ROD_EXT_VALUE)
        ext_enable  = bool(_pget_simple(node, _ROD_EXT_ENABLE))
        outputs.append({
            "node":        name,
            "output_name": output_name,
            "extension":   ext_value,
            "explicit":    ext_enable,
        })
    outputs.sort(key=lambda o: o["output_name"])
    enabled_exts = [o["extension"] for o in outputs if o["explicit"] and o["extension"]]
    all_exts     = [o["extension"] for o in outputs if o["extension"]]
    source_exts  = enabled_exts if enabled_exts else all_exts
    if source_exts:
        final_ext, final_count = _Counter(source_exts).most_common(1)[0]
    else:
        final_ext, final_count = None, 0
    file_extension = {
        "final":         final_ext,
        "final_count":   final_count,
        "total_outputs": len(outputs),
        "outputs":       outputs,
    }

    return {
        "upstream_count": len(upstream_map),
        "frame_range":    frame_range,
        "resolution":     resolution,
        "file_extension": file_extension,
    }


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

        # RenderSettings nodes — resolution, frame range, legacy AOVs (not added to render_nodes)
        if ntype == "RenderSettings":
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

        # Only "Render" type nodes go into render_nodes
        elif ntype == "Render":
            render_nodes.append({"name": nname, "type": ntype, "role": "render"})
            try:
                _try_extract_output_path(node, render_globals)
            except Exception:
                pass

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

    # Enrich each Render node with frame_range, resolution, and file_extension
    # via upstream graph traversal (mirrors katana_render_modifier.get_render_data)
    if render_nodes and NodegraphAPI is not None:
        try:
            all_nodes_map = _build_all_nodes_map()
            for rnode in render_nodes:
                node_obj = all_nodes_map.get(rnode["name"])
                if node_obj is not None:
                    upstream = _get_upstream_nodes(node_obj)
                    rnode.update(_collect_render_node_data(node_obj, upstream))
        except Exception as exc:
            log.log("WARNING: Could not collect upstream render data: {}".format(exc))

    # Format as [{node_name: {type, role, frame_range, resolution, file_extension, ...}}]
    formatted_nodes = []
    for rnode in render_nodes:
        nname = rnode["name"]
        entry = {k: v for k, v in rnode.items() if k != "name"}
        formatted_nodes.append({nname: entry})

    return render_globals, unique_aovs, sorted(set(cameras)), formatted_nodes
