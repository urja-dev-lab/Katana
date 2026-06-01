# SquidNet Katana Integration

**Version:** 0.1.0

Integrates Foundry Katana with the SquidNet render farm. Provides three operations run inside the Katana Python environment:

1. **Analyze** — extract file dependencies, render settings, and AOVs from a `.katana` scene
2. **Repath** — update file-path parameters in a server-side copy of the scene
3. **Render** — load the scene and execute selected Render nodes

---

## Requirements

- Foundry Katana 8.0v4 (Windows) or Katana 2020–2025 (Linux/macOS)
- KtoA (Arnold) renderer plugin
- All scripts must run **inside the Katana Python environment** — standard `python` cannot import `NodegraphAPI`, `KatanaFile`, or `RenderManager`

---

## Environment setup

Before invoking `katanaBin.exe` directly, source the environment for your platform. On Windows this sets `KATANA_ROOT`, `KTOA_ROOT`, license servers, and `PATH`:

```bat
call envs\windows.env
```

On the test rig, `W:\Data\Naba\temp\launchKtoA.bat` wraps this and launches `katanaBin.exe` with the correct environment — use it instead of calling `katanaBin.exe` directly.

---

## Script 1 — Analyze (`katana_analyzer.py`)

Opens a `.katana` scene, collects all file dependencies (textures, caches, geometry, LUTs, light profiles), extracts render globals, AOVs, cameras, and render nodes, then writes output to `<output_dir>/renderfarm/`.

### Command

```bat
"W:\Data\Naba\temp\launchKtoA.bat" --script katana_analyzer.py -- <scene.katana> <output_dir> [profile.json] [--relative-paths]
```

| Argument | Required | Description |
|---|---|---|
| `<scene.katana>` | yes | Absolute path to the Katana scene |
| `<output_dir>` | yes | Directory where `renderfarm/` output folder is created |
| `[profile.json]` | no | Optional analysis profile JSON |
| `--relative-paths` | no | Switch target paths from hash-based to project-relative directory (see below) |

### Target path modes

**Default** (`--relative-paths` absent):
```
W:/project/maps/texture.tx  →  assets/textures/8f06c60b47015f08de41cbf635a6c894
```

**Relative** (`--relative-paths` present):
```
W:/project/maps/texture.tx  →  maps
```

Only paths that exist on disk are included in outputs. Missing files are logged as `MISSING (skipped)`.

### Test (Windows — run from Git Bash to avoid UNC path issues)

```bash
"W:/Data/Naba/temp/launchKtoA.bat" --script \
  "//172.17.116.185/renderprod/Data/Naba/GIT/Katana/katana_analyzer.py" \
  -- "W:/Data/Naba/RND/KATANA/sampleData/Katana_To_Yotta/Bus_v001.katana" \
  "W:/Data/Naba/RND/KATANA/sampleData/Katana_To_Yotta"
```

Or via a `.bat` file (set working dir to a local path to avoid UNC `cd` errors):

```bat
@cd /d C:\Temp
"W:\Data\Naba\temp\launchKtoA.bat" --script "\\172.17.116.185\renderprod\Data\Naba\GIT\Katana\katana_analyzer.py" -- "W:\Data\Naba\RND\KATANA\sampleData\Katana_To_Yotta\Bus_v001.katana" "W:\Data\Naba\RND\KATANA\sampleData\Katana_To_Yotta"
echo Exit: %ERRORLEVEL%
```

### Outputs

All written to `<output_dir>/renderfarm/`:

| File | Contents |
|---|---|
| `web_ui_data.json` | Full scene data for the render farm web UI |
| `katana_file_list.txt` | CSV `source_path,target_path` file transfer manifest (existing files only) |
| `analysis_log.txt` | Timestamped run log |

---

## Script 2 — Repath (`katana_repath.py`)

Loads a synced server-side copy of the scene, remaps all file-path node parameters to their server target paths, applies any web UI overrides (frame range, resolution), and saves the scene in place.

### Command

```bat
"W:\Data\Naba\temp\launchKtoA.bat" --script katana_repath.py -- <server_project_path> <rel_scene_path> <web_ui_data.json>
```

| Argument | Description |
|---|---|
| `<server_project_path>` | Root of the synced project on the render server |
| `<rel_scene_path>` | Relative path from `server_project_path` to the `.katana` file |
| `<web_ui_data.json>` | Path to the JSON produced by the analyze step |

### How repath works

For each entry in `assets[]`:
```python
node = NodegraphAPI.GetNode(asset["node"])
node.getParameter(asset["param"]).setValue(server_project_path + "/" + asset["target"], 0)
KatanaFile.Save(scene_path)
```

`apply_web_ui_settings()` also pushes frame range and resolution overrides to nodes with `role=settings` in `render_nodes`.

### Test

```bat
@cd /d C:\Temp
"W:\Data\Naba\temp\launchKtoA.bat" --script "\\172.17.116.185\renderprod\Data\Naba\GIT\Katana\katana_repath.py" -- "W:\Data\Naba\RND\KATANA\sampleData\Katana_To_Yotta" "Bus_v001.katana" "W:\Data\Naba\RND\KATANA\sampleData\Katana_To_Yotta\renderfarm\web_ui_data.json"
echo Exit: %ERRORLEVEL%
```

### Outputs

Written to `<server_project_path>/renderfarm/`:

| File | Contents |
|---|---|
| `repath_log.txt` | Timestamped repath log |
| `repath_report.json` | Stats: total/successful/failed/missing assets, execution time |

---

## Script 3 — Render (`katana_render.py`)

Loads a `.katana` scene and executes the selected Render nodes. Parameters come from environment variables, not command-line arguments.

### Command

```bat
"W:\Data\Naba\temp\launchKtoA.bat" --batch --script katana_render.py -- <scene.katana>
```

> **Note:** Render uses `--batch`, unlike analyze and repath which use `--script`.

### Environment variables

Both must be set before invoking the script:

| Variable | Content |
|---|---|
| `SQN_CLOUD_JOBSLICE_RENDER_PARAMS` | The full `web_ui_data.json` content as a JSON string |
| `SQN_CLOUD_JOBSLICE_OUTPUT_PATH` | Path to a file where rendered output paths are written as a JSON array |

### Test bat file

```bat
@cd /d C:\Temp\katana_run

set SQN_CLOUD_JOBSLICE_OUTPUT_PATH=C:\Temp\katana_run\render_output_paths.json

set SQN_CLOUD_JOBSLICE_RENDER_PARAMS={"web_ui_setting":[{"name":"render_frames","current_value":"Custom Range"},{"name":"pretest_first","current_value":true},{"name":"pretest_middle","current_value":false},{"name":"pretest_last","current_value":false},{"name":"pretest_custom_frames","current_value":""},{"name":"startFrame","current_value":1},{"name":"endFrame","current_value":5},{"name":"byFrame","current_value":1},{"name":"defaultResolution.width","current_value":""},{"name":"defaultResolution.height","current_value":""},{"name":"file_extension","current_value":"exr"},{"name":"Render_TT_BTY","current_value":true}],"render_nodes":[{"Render_TT_BTY":{"role":"render","type":"Render","frame_range":{"start_frame":1.0,"end_frame":200.0},"resolution":{"all":[{"node":"RenderSettings226","raw":"HD","value":"1920x1080  (HD)","enabled":true}]},"file_extension":{"final":"exr","outputs":[{"node":"ROD_BTY_OUT223","output_name":"primary"}]}}}]}

"W:\Data\Naba\temp\launchKtoA.bat" --batch --script "\\172.17.116.185\renderprod\Data\Naba\GIT\Katana\katana_render.py" -- "W:\Data\Naba\RND\KATANA\sampleData\Katana_To_Yotta\Bus_v001.katana"
echo Exit: %ERRORLEVEL%
```

After running, check:
- Log: `<scene_dir>/render_log.txt`
- Output paths: `C:\Temp\katana_run\render_output_paths.json` (JSON array of rendered file paths)

### `web_ui_setting` keys consumed by the render script

| Name | Type | Effect |
|---|---|---|
| `render_frames` | string | `"Full Range"` or `"Custom Range"` |
| `pretest_first` | bool | Render only the first frame of the node's range |
| `pretest_middle` | bool | Render only the middle frame |
| `pretest_last` | bool | Render only the last frame |
| `pretest_custom_frames` | string | Frame spec string (see formats below) |
| `startFrame` / `endFrame` | int | Override frame range (Custom Range mode) |
| `byFrame` | int | Frame step |
| `defaultResolution.width/height` | int | Resolution override; empty string = no override |
| `file_extension` | string | Extension override (`"exr"`, `"png"`, etc.); empty = no override |
| `<NodeName>` | bool | Whether to render that Render node (`true` if key absent) |

`render_frames == "Custom Range"` activates pretest/custom/startFrame/endFrame logic. Anything else is Full Range.

### Frame spec formats (`pretest_custom_frames`)

| Format | Result |
|---|---|
| `FML` | First, middle, last frames of the node's range |
| `1-10` or `1:10` | Frames 1 through 10, stepping by `byFrame` |
| `1,5,10` | Specific frames 1, 5, and 10 |
| `42` | Single frame 42 |
| `1-10,15` | Mix of range and explicit frames |

### Output

`SQN_CLOUD_JOBSLICE_OUTPUT_PATH` receives a JSON array of rendered file paths:
```json
[
  "/render/output/frame.0001.exr",
  "/render/output/frame.0002.exr"
]
```

The log is written to `render_log.txt` in the same directory as the scene file.

---

## Production wrapper (`katana_scene_tool.py`)

The render farm invokes a single entry point for analyze and repath:

```bat
"W:\Data\Naba\temp\launchKtoA.bat" --script katana_scene_tool.py -- --request <request.json>
```

### Request JSON — analyze

```json
{
  "operation": "analyze",
  "paths": {
    "scenePath":       "W:/path/to/scene.katana",
    "syncDir":         "W:/path/to/project",
    "renderfarmDir":   "W:/path/to/project/renderfarm",
    "statusPath":      "W:/path/to/project/renderfarm/status.json",
    "fileListPath":    "W:/path/to/project/renderfarm/katana_file_list.txt",
    "profileJsonPath": "W:/path/to/project/renderfarm/web_ui_data.json"
  }
}
```

### Request JSON — repath

```json
{
  "operation": "repath",
  "paths": {
    "syncDir":        "/server/project/root",
    "sceneRelPath":   "scenes/Bus_v001.katana",
    "webUiDataPath":  "/server/project/root/renderfarm/web_ui_data.json"
  }
}
```

`status.json` is written to `statusPath` after every run:
```json
{
  "schemaVersion": 1,
  "operation": "analyze",
  "state": "success",
  "exitCode": 0,
  "message": "analyze completed.",
  "warnings": [],
  "errors": []
}
```

---

## `web_ui_data.json` schema (key sections)

```json
{
  "dcc": "katana",
  "scene_path": "...",
  "renderer": "arnold",
  "assets": [
    {
      "node":     "ImageRead",
      "param":    "args.fileSettings.filename.value",
      "source":   "/original/path/texture.<UDIM>.tx",
      "target":   "assets/textures/<md5>/texture.<UDIM>.tx",
      "metadata": { "asset_type": "texture", "is_udim": true }
    }
  ],
  "render_nodes": [
    {
      "Render_TT_BTY": {
        "role": "render",
        "type": "Render",
        "frame_range": { "start_frame": 1.0, "end_frame": 200.0, "nodegraph_in": 1, "nodegraph_out": 100 },
        "resolution": {
          "all": [{ "node": "RenderSettings226", "raw": "HD", "value": "1920x1080  (HD)", "enabled": true }],
          "raw": "HD", "value": "1920x1080  (HD)"
        },
        "file_extension": {
          "final": "exr", "final_count": 61,
          "outputs": [{ "node": "ROD_BTY_OUT223", "output_name": "primary", "extension": "exr" }]
        }
      }
    }
  ],
  "web_ui_setting": [
    { "name": "render_frames", "current_value": "Full Range" },
    { "name": "Render_TT_BTY", "current_value": true }
  ],
  "render_globals": { "startFrame": 1, "endFrame": 200, "byFrame": 1, "width": 1920, "height": 1080, "renderer": "arnold" },
  "aovs": [{ "name": "RGBA", "type": "unknown" }],
  "cameras": ["camera1"],
  "ocio": { "enabled": true, "path": "..." }
}
```

- `assets` stores sequence patterns (`texture.<UDIM>.tx`), not expanded per-frame paths.
- `target` is relative to `server_project_path`; repath prepends the server root before writing.
- `param` is the full dotted Katana parameter path used by repath.

---

## Supported renderers

Detection is inferred from node type names in the scene:

| Renderer | Node type |
|---|---|
| Arnold | `ArnoldGlobalSettings` |
| RenderMan | `PrmanGlobalSettings` |
| Redshift | `RedshiftOptions` |
| V-Ray | `VRayFarmerSettings` |
| 3Delight | `DlGlobalStatements`, `dl_RenderSettings` |

If no known renderer node is found, `renderer` is reported as `unknown`.

---

## Known limitations

- AOVs are extracted from `RenderSettings.renderOutputs` groups and `*OutputChannelDefine` nodes only. AOV definitions embedded inside `OpScript` nodes are not parsed.
- Render settings extraction uses known parameter name patterns. Exotic node setups may yield `width=0` or `renderer=unknown`; the web UI allows manual override.
- `apply_web_ui_settings` during repath only targets nodes with `role=settings` in `render_nodes`. Nodes not discovered at analysis time are silently skipped.
- The render API (`RenderManager.StartRenderLegacy`) is tried first; if unavailable, the script falls back through `StartRender` with several method strings, then `node.render()`.
