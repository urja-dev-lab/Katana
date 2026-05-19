# SquidNet Katana Integration

**Version:** 0.1.0

Integrates Foundry Katana with the SquidNet render farm. Extracts scene file dependencies, generates submission data for the web UI, and remaps file paths on the render server before a job runs.

Supports Katana 2020–2025 on Windows, Linux, and macOS.

---

## Requirements

- Foundry Katana (2020–2025)
- All scripts must be executed **inside the Katana Python environment** — standard `python` cannot run them.

---

## Two-stage workflow

### Stage 1 — Analyze

Opens the `.katana` scene, collects all file dependencies (textures, caches, geometry, LUTs, light profiles), extracts render globals and AOVs, and writes output artifacts to `<output_dir>/renderfarm/`.

```bash
katana --script katana_analyzer.py -- <input.katana> <output_dir>
```

### Stage 2 — Repath

Loads the synced scene copy on the render server, remaps all file parameters to their server-side target paths, applies any web UI overrides (frame range, resolution), and saves the scene in place.

```bash
katana --script katana_repath.py -- <server_project_path> <rel_scene_path> <web_ui_data.json>
```

| Argument | Description |
|---|---|
| `server_project_path` | Root of the synced project on the render server |
| `rel_scene_path` | Relative path to the `.katana` file within the project |
| `web_ui_data.json` | Output from the analyze step |

---

## Render farm wrapper (production)

The render farm invokes a single entry point for both operations:

```bash
katana --script katana_scene_tool.py -- --request <request.json>
```

> Use `--script`, not `--batch`. Katana's `--batch` mode is for rendering via `--katana-file`; `--script` is required for Python tooling.

### Request JSON format

```json
{
  "operation": "analyze",
  "paths": {
    "scenePath":       "/path/to/scene.katana",
    "syncDir":         "/path/to/project",
    "renderfarmDir":   "/renderfarm/output",
    "statusPath":      "/renderfarm/output/renderfarm/status.json",
    "fileListPath":    "/renderfarm/output/renderfarm/file_list.txt",
    "profileJsonPath": "/renderfarm/output/renderfarm/web_ui_data.json"
  }
}
```

Set `"operation"` to `"analyze"` or `"repath"`.

---

## Output files

All output lands under `<output_dir>/renderfarm/`:

| File | Contents |
|---|---|
| `web_ui_data.json` | Structured data for the render farm web UI (assets, AOVs, render settings, render nodes) |
| `katana_file_list.txt` | CSV: `source_path,target_path` — the file transfer manifest |
| `analysis_log.txt` | Timestamped log of the analysis run |
| `status.json` | Operation result: success/failed, exit code, message |
| `repath_log.txt` | Repath operation details |
| `repath_report.json` | Repath statistics (counts of remapped/failed paths) |

### `web_ui_data.json` shape

```json
{
  "aovs": [
    { "name": "RGBA", "type": 6 }
  ],
  "assets": [
    {
      "node":     "ImageRead",
      "param":    "args.fileSettings.filename.value",
      "source":   "/original/path/texture.<UDIM>.tx",
      "target":   "assets/textures/<md5>/texture.<UDIM>.tx",
      "metadata": { "asset_type": "texture", "is_udim": true }
    }
  ],
  "render_settings": {},
  "render_nodes": {
    "Render": {
      "settings_node": "RenderSettings",
      "render_settings": {}
    }
  }
}
```

- `assets` stores **sequence patterns** (e.g., `texture.<UDIM>.tx`), not expanded per-frame paths.
- `target` paths are relative to `server_project_path`; repath resolves them to absolute before writing.
- The `param` field (full dotted path, e.g., `args.fileSettings.filename.value`) is what repath uses to call `node.getParameter(param).setValue(new_path, 0)`.

---

## Supported renderers

Renderer detection is inferred from node type names present in the scene:

| Renderer | Node type detected |
|---|---|
| Arnold | `ArnoldGlobalSettings` |
| RenderMan | `PrmanGlobalSettings` |
| Redshift | `RedshiftOptions` |
| V-Ray | *(V-Ray for Katana node types)* |

If no known renderer node is found, `renderer` is reported as `unknown` and can be overridden in the web UI.

---

## Known limitations

- AOVs are extracted from `RenderSettings.renderOutputs` groups and `*OutputChannelDefine` nodes only. AOV definitions embedded inside `OpScript` nodes are not parsed.
- Render settings extraction uses known parameter name patterns. Exotic or custom node setups may yield `width=0` or `renderer=unknown`; the web UI allows manual override.
- `apply_web_ui_settings` during repath only targets nodes discovered at analysis time. Nodes absent from `render_nodes` in `web_ui_data.json` are silently skipped.
