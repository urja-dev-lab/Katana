# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This package integrates Foundry Katana with a render farm system (SquidNet), mirroring the existing Maya integration workflow. It extracts scene dependencies, generates render farm submission data, and remaps paths for server-side rendering.

**Status:** Production-ready. Analyze, repath, and render operations are fully implemented. `scene_tools.json` is enabled (schemaVersion 1, template ID 40 = TEMPLATE_ID_KATANA).

**Critical constraint:** All scripts must run inside a Katana environment. Katana-specific imports (`NodegraphAPI`, `KatanaFile`, `AssetAPI`) are unavailable outside Katana and will fail with import errors.

## Commands

### Analysis (direct invocation)
```bash
katana --script katana_analyzer.py -- <input.katana> <output_dir> [profile.json] [--relative-paths]
```
`--relative-paths` switches asset target paths from hash-based (`assets/textures/<md5>`) to project-relative directory (`maps`, `scenes`, etc.).

### Repath (direct invocation)
```bash
katana --script katana_repath.py -- <server_project_path> <rel_scene_path> <web_ui_data.json>
```
- `server_project_path` — root of the synced project on the render server
- `rel_scene_path` — relative path to the `.katana` file within the project
- `web_ui_data.json` — path to the JSON produced by the analyze step

### Render (direct invocation)
```bash
katanaBin.exe --batch --script katana_render.py -- <scene.katana>
```
Reads render parameters from env vars; writes output file paths to a JSON file.

| Env var | Content |
|---------|---------|
| `SQN_CLOUD_JOBSLICE_RENDER_PARAMS` | Full `web_ui_data.json` content as a JSON string |
| `SQN_CLOUD_JOBSLICE_OUTPUT_PATH` | Path to a file where rendered output paths are written (JSON array) |

`pretest_custom_frames` accepts: `FML` (first/middle/last), `1-10`, `1:5`, `1,5,10`, or combinations.

### Render farm wrapper (production use)
```bash
katana --script katana_scene_tool.py -- --request <request.json>
```
**Note:** Use `--script` not `--batch`. Katana's `--batch` mode requires `--katana-file` for rendering; `--script` is the correct mode for running Python tools.

The request JSON specifies the `operation` (`"analyze"` or `"repath"`) and a `paths` object with keys: `scenePath`, `syncDir`, `renderfarmDir`, `statusPath`, `fileListPath`, `profileJsonPath`, `sceneRelPath`, `webUiDataPath`.

The `scene_tools.json` manifest drives invocation via this command template:
```
"{tool}" --script "{wrapper}" -- --request "{requestJson}"
```

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
| `libs/katana_constants.py` | Extension sets (textures/caches/geometry/lights/LUTs), output path constants (`LOG_DIR`, `LOG_FILE`, `FILE_LIST`, `WEB_JSON_FILE`, `REPATH_LOG_FILE`, `REPATH_REPORT_FILE`, `RENDER_LOG_FILE`), UDIM token patterns, `FILE_PARAM_KEYWORDS` (21 keywords used for file-param detection) |
| `libs/katana_utils.py` | `is_probable_file_path()` (Katana-safe: filters `/root` scene-graph paths and CEL), path helpers, `dedupe_dicts()` |
| `libs/katana_data_handler.py` | `DataHandler(project_root, is_path_relative=False)` — tracks `assets` list (with `param` field for repath), `path_list` for file transfer, sequence/UDIM expansion via glob; `_target_dir()` computes target path per the `is_path_relative` flag; `classify_asset()` returns a **path prefix string** |
| `libs/katana_scene_utils.py` | `get_project_root()` (walks up for marker dirs: `project.conf`, `.katana`, `scenes`, `assets`, `cache`, `textures`); `resolve_asset_path()` (expands `$VAR`/`~`, strips `@var@`, tries absolute then relative to scene dir / project root / known subdirs); `classify_asset()` also returns a **path prefix string** but covers two extra categories (`assets/color` for LUTs, `assets/lights` for IES) |
| `libs/katana_info_collector.py` | `collect_scene_info()` — scans all nodes for render settings (resolution, frame range, renderer), cameras, AOVs, render nodes |
| `libs/katana_ui_fields.py` | `KatanaUIFields(BaseUIFields)` — builds web UI form: 7 sections mirroring Maya's layout; renderer GPU/OS capabilities defined in `_RENDERER_POOL`; Section 3 (Image Details) includes a `file_extension` select field populated from the first detected extension in `render_nodes` |
| `katana_render.py` | Standalone render script — reads `web_ui_data.json` from `SQN_CLOUD_JOBSLICE_RENDER_PARAMS` env var, applies frame range / resolution / file extension overrides, renders selected nodes via `RenderManager`, collects output paths from `RenderOutputDefine` nodes, writes JSON array to `SQN_CLOUD_JOBSLICE_OUTPUT_PATH` |

> **`classify_asset()` exists in both `katana_data_handler.py` and `katana_scene_utils.py`.** Both return a directory prefix string (e.g., `"assets/textures"`), but `scene_utils` adds `"assets/color"` (for `.ocio`, `.cube`, `.lut`, `.cc`) and `"assets/lights"` (for `.ies`). Do not treat them as interchangeable; each is used in different stages.

### Output files

All outputs land under `<output_dir>/renderfarm/`:

| File | Written by | Purpose |
|------|-----------|---------|
| `analysis_log.txt` | analyzer | Timestamped log of the full analysis run |
| `katana_file_list.txt` | analyzer | CSV: `source_path,target_path` (only entries where source exists on disk) |
| `web_ui_data.json` | analyzer | Structured data for the render farm web UI (see schema below) |
| `status.json` | scene_tool | Operation result: state, exitCode, message, warnings, errors |
| `repath_log.txt` | repath | Timestamped log of the repath run |
| `repath_report.json` | repath | Statistics: total/successful/failed/missing assets, settings applied, execution time |
| `render_log.txt` | render | Timestamped log written to `dirname(scene_path)` |

### Path conventions

- Paths are normalized to forward slashes internally throughout all modules.
- Asset `target` paths have two formats controlled by `DataHandler.is_path_relative`:
  - `False` (default): `assets/{type}/{md5_hash}/{basename}` — hash is a 32-char MD5 of the source path
  - `True`: project-relative directory of the source file, e.g. `maps` or `assets/textures/subdir`
- Both `katana_file_list.txt` and `web_ui_data.json["assets"]` only include paths that exist on disk. Non-existent single files are skipped with a `MISSING (skipped)` log; UDIM sequences with no glob matches are skipped entirely.
- `file_parameter` detection in `katana_utils.py` uses `FILE_PARAM_KEYWORDS` from `katana_constants.py` against parameter names plus hint string inspection; paths starting with `/root` are scene graph locations and are skipped.
- UDIM/sequence patterns are stored as-is in `assets` (e.g., `texture.<UDIM>.tx`); `add_sequence_asset()` expands them via glob and records each resolved file in the CSV file list. Returns `(None, None)` if no files match.

## Assets schema

Each entry in `web_ui_data.json["assets"]` carries:
```json
{
  "node":   "NodeName",
  "param":  "args.fileSettings.filename.value",
  "source": "/original/absolute/path.tx",
  "target": "assets/textures/<md5>/path.tx",   // or "maps/path.tx" when is_path_relative=True
  "metadata": {"asset_type": "texture", "is_udim": true}
}
```
The `param` field is what `katana_repath.py` uses to call `node.getParameter(param).setValue(new_path, 0)`.
Target paths are relative to `server_project_path`; repath resolves them to absolute before writing.
`assets` contains **sequence patterns** (e.g., `texture.<UDIM>.tx`), not expanded per-frame paths.

The full `web_ui_data.json` top-level shape:
```json
{
  "dcc": "katana",
  "scene_path": "...",
  "renderer": "arnold",
  "assets": [...],
  "render_globals": {"startFrame": 1, "endFrame": 100, "byFrame": 1, "width": 1920, "height": 1080, "fps": 24, "renderer": "arnold", "output_path": "..."},
  "aovs": [{"name": "RGBA", "type": "unknown"}],
  "render_nodes": [
    {
      "NodeName": {
        "role": "render",
        "type": "Render",
        "frame_range": {"start_frame": 1.0, "end_frame": 200.0, "nodegraph_in": 1, "nodegraph_out": 100},
        "resolution": {
          "all": [{"node": "RenderSettings226", "raw": "HD", "value": "1920x1080  (HD)", "enabled": true}],
          "enabled": true, "raw": "HD", "source_node": "RenderSettings226", "value": "1920x1080  (HD)"
        },
        "file_extension": {
          "final": "exr", "final_count": 61, "total_outputs": 61,
          "outputs": [{"explicit": false, "extension": "exr", "node": "ROD_primary346", "output_name": "primary"}]
        },
        "upstream_count": 353
      }
    }
  ],
  "cameras": ["camera1"],
  "ocio": {"enabled": true, "custom": true, "path": "...", "valid": true},
  "passes": [],
  "caches": [],
  "bakes": [],
  "web_ui_setting": [...],
  "analysis_metrics": {"total_time": 12.3, "stage_times": {}, "file_count": 150, "dir_count": 5, "total_size_mb": 2345.6}
}
```

## web_ui_setting format

`web_ui_setting` is a flat list of `{"name": str, "current_value": any}` entries — one per form field. The render script maps this to `{name: current_value}` for lookup. Key field names consumed by `katana_render.py`:

| Name | Type | Meaning |
|------|------|---------|
| `render_frames` | str | `"Full Range"` or `"Custom Range"` |
| `pretest_first/middle/last` | bool | Render only first/middle/last frame |
| `pretest_custom_frames` | str | Frame spec string (`FML`, `1-10`, `1,5,10`, etc.) |
| `startFrame` / `endFrame` | int | Override frame range |
| `byFrame` | int | Frame step |
| `defaultResolution.width/height` | int | Resolution override (empty = no override) |
| `file_extension` | str | Extension override (`"exr"`, `"png"`, etc.; empty = no override) |
| `<NodeName>` | bool | Whether to render that Render node (default `true` if absent) |

`render_frames == "Custom Range"` activates the pretest/custom/startFrame/endFrame logic; anything else (including empty string) is treated as Full Range.

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
- `envs/windows.env` / `envs/linux.env` — environment variables (license servers, Katana root, KtoA plugin paths) that must be sourced before invoking any Katana script

## Known limitations

- Render settings extraction relies on known parameter name patterns; exotic node setups may yield `width=0` / `renderer=unknown` — the analyzer still succeeds and the web UI allows manual override.
- Renderer detection in `katana_info_collector.py` is inferred from node type names; unmapped types yield `renderer=unknown`:

  | Renderer | Node type names matched |
  |----------|------------------------|
  | arnold | `ArnoldGlobalSettings` |
  | prman | `PrmanGlobalSettings` |
  | redshift | `RedshiftOptions` |
  | vray | `VRayFarmerSettings` |
  | 3delight | `DlGlobalStatements`, `dl_RenderSettings` |

- AOVs are only extracted from `RenderSettings.renderOutputs` groups and dedicated `*OutputChannelDefine` nodes; inline AOV definitions inside `OpScript` nodes are not parsed.
- `apply_web_ui_settings` in repath pushes overrides only to nodes listed in `render_nodes` with `role=settings`; nodes not discovered during analysis are skipped.
