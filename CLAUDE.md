# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This package integrates Foundry Katana with a render farm system (SquidNet), mirroring the existing Maya integration workflow. It extracts scene dependencies, generates render farm submission data, and remaps paths for server-side rendering.

**Status:** Production-ready. Both analyze and repath operations are fully implemented. `scene_tools.json` is enabled (schemaVersion 1, template ID 40 = TEMPLATE_ID_KATANA).

**Critical constraint:** All scripts must run inside a Katana environment. Katana-specific imports (`NodegraphAPI`, `KatanaFile`, `AssetAPI`) are unavailable outside Katana and will fail with import errors.

## Commands

### Analysis (direct invocation)
```bash
katana --script katana_analyzer.py -- <input.katana> <output_dir>
```

### Repath (direct invocation)
```bash
katana --script katana_repath.py -- <server_project_path> <rel_scene_path> <web_ui_data.json>
```
- `server_project_path` — root of the synced project on the render server
- `rel_scene_path` — relative path to the `.katana` file within the project
- `web_ui_data.json` — path to the JSON produced by the analyze step

### Render farm wrapper (production use)
```bash
katana --script katana_scene_tool.py -- --request <request.json>
```
**Note:** Use `--script` not `--batch`. Katana's `--batch` mode requires `--katana-file` for rendering; `--script` is the correct mode for running Python tools.

The request JSON specifies the `operation` (`"analyze"` or `"repath"`) and a `paths` object with keys: `scenePath`, `syncDir`, `renderfarmDir`, `statusPath`, `fileListPath`, `profileJsonPath`.

## Architecture

### Entry points and dispatch

`katana_scene_tool.py` is the production entry point used by the render farm system. It reads a request JSON and dispatches to `katana_analyzer.main()` or `katana_repath.main()` by dynamically importing those modules. It also writes a `status.json` with the operation result and calls `_normalize_outputs()` to copy log/file list to the paths the farm system expects.

`katana_analyzer.py` instantiates `KatanaAnalyzer` and calls `.run()`, which orchestrates the full pipeline:
1. Load the `.katana` file via `KatanaFile.Load()`
2. Traverse all nodes with `NodegraphAPI.GetAllNodes()` to collect file dependencies
3. Extract AOVs and render node names from `Render`-type nodes
4. Extract render settings by following input port connections from `Render` nodes upstream
5. Write three output files to `<output_dir>/renderfarm/`

Progress is reported via `Messenger` (local socket on port 17374 to SquidNet streamer) with a `NullMessenger` fallback if the streamer is unavailable. The `Messenger` class lives in `../core/streamer_com.py` relative to this package root.

### Module responsibilities

| Module | Role |
|--------|------|
| `libs/katana_logger.py` | `MessageLogger` — file + stdout logging with timestamps; `get_logger()` factory; Python 2/3 `to_unicode()`/`to_bytes()` helpers |
| `libs/katana_constants.py` | Extension sets (textures/caches/geometry), output path constants, UDIM tokens, `FILE_PARAM_KEYWORDS` (15 keywords used for file-param detection) |
| `libs/katana_utils.py` | `is_probable_file_path()` (Katana-safe: filters `/root` scene-graph paths and CEL), path helpers, `dedupe_dicts()` |
| `libs/katana_data_handler.py` | `DataHandler` — tracks `assets` list (with `param` field for repath), `path_list` for file transfer, sequence/UDIM expansion via glob; `classify_asset()` returns a **path prefix string** |
| `libs/katana_scene_utils.py` | `get_project_root()` (walks up for marker dirs), `resolve_asset_path()` (handles relative/absolute/`@` variables); `classify_asset()` returns a **metadata dict** — not interchangeable with the `data_handler` version |
| `libs/katana_info_collector.py` | `collect_scene_info()` — scans all nodes for render settings (resolution, frame range, renderer), cameras, AOVs, render nodes |
| `libs/katana_ui_fields.py` | `KatanaUIFields(BaseUIFields)` — builds web UI form: 7 sections mirroring Maya's layout |

> **`classify_asset()` exists in both `katana_data_handler.py` and `katana_scene_utils.py` with different return types.** The `data_handler` version returns a directory prefix string; `scene_utils` returns a metadata dict with `asset_type`. They are not interchangeable.

### Output files (all under `<output_dir>/renderfarm/`)

- `analysis_log.txt` — timestamped log of the full analysis run
- `katana_file_list.txt` — CSV: `source_path,target_path` (only entries where source exists on disk)
- `web_ui_data.json` — structured data for the render farm web UI:
  ```json
  {
    "aovs": [{"name": "RGBA", "type": 6}],
    "assets": [{"metadata": {}, "node": "NodeName", "param": "args.fileSettings.filename.value", "source": "...", "target": "..."}],
    "render_settings": {},
    "render_nodes": {"RenderNodeName": {"settings_node": "...", "render_settings": {}}}
  }
  ```
  > `assets` contains **sequence patterns** (e.g., `texture.<UDIM>.tx`), not expanded per-frame paths.

### Path conventions

- Paths are normalized to forward slashes internally throughout all modules.
- Asset `target` paths are relative to the scene file's parent directory (not absolute, not hash-based).
- Asset hashes (`generate_asset_hash`) use SHA-256 truncated to 32 characters — matches the Maya integration format but is not currently used in target path generation.
- `file_parameter` detection in `katana_utils.py` uses `FILE_PARAM_KEYWORDS` from `katana_constants.py` against parameter names plus hint string inspection; paths starting with `/root` are scene graph locations and are skipped.

## Assets schema

Each entry in `web_ui_data.json["assets"]` carries:
```json
{
  "node":   "NodeName",
  "param":  "args.fileSettings.filename.value",
  "source": "/original/absolute/path.tx",
  "target": "assets/textures/<md5>/path.tx",
  "metadata": {"asset_type": "texture", "is_udim": true}
}
```
The `param` field is what `katana_repath.py` uses to call `node.getParameter(param).setValue(new_path, 0)`.
Target paths are relative to `server_project_path`; repath resolves them to absolute before writing.

## How repath works in Katana

Unlike Maya (which uses `cmds.setAttr`), Katana repath uses the Python parameter API:
```python
node = NodegraphAPI.GetNode(node_name)   # or iteration fallback
param = node.getParameter(param_path)    # full dotted path e.g. "args.filename.value"
param.setValue(new_absolute_path, 0)     # 0 = frame time
KatanaFile.Save(scene_path)             # save in place
```
`apply_web_ui_settings()` pushes frame range and resolution overrides only to nodes listed in `render_nodes` with `role=settings`; nodes not discovered during analysis are silently skipped.

## Configuration

- `config/default_params.json` — supported Katana versions (2020–2025), `output_folder: "renderfarm"`, `headless: true`
- `scene_tools.json` — render farm integration manifest: template ID, tool definitions (analyze/repath), OS-specific Katana executable paths, and expected output file keys

## Known limitations

- Render settings extraction relies on known parameter name patterns; exotic node setups may yield `width=0` / `renderer=unknown` — the analyzer still succeeds and the web UI allows manual override.
- Renderer detection in `katana_info_collector.py` is inferred from node type names (e.g., `ArnoldGlobalSettings`, `PrmanGlobalSettings`, `RedshiftOptions`); custom renderer integrations using non-standard node names will yield `renderer=unknown`.
- AOVs are only extracted from `RenderSettings.renderOutputs` groups and dedicated `*OutputChannelDefine` nodes; inline AOV definitions inside `OpScript` nodes are not parsed.
- `apply_web_ui_settings` in repath pushes overrides only to nodes listed in `render_nodes` with `role=settings`; nodes not discovered during analysis are skipped.
