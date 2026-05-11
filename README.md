# Katana Render Farm Integration

This package provides integration between Foundry Katana and a render farm system, mirroring the existing Maya integration workflow.

## Components

### 1. Analysis Script (`analyze_katana.py`)
Client-side script that extracts all dependencies from a Katana file and generates:
- `create_log.txt`: Detailed log of the analysis process
- `katana_file_list.txt`: CSV listing of source files and their target hash paths
- `web_ui_data.json`: JSON containing AOVs, assets, and render settings

### 2. Repath Script (`repath_katana.py`)
Server-side script that modifies a Katana file to adjust paths from client-side to server-side references using the mapping from `web_ui_data.json`.

### 3. Utility Module (`katana_utils.py`)
Shared utility functions used by both scripts.

## Usage

### Analysis
Use the helper script:
```bash
./run_katana_analysis.sh input.katana output_dir
```
This generates:
- `create_log.txt` in `output_dir`
- `katana_file_list.txt` in `output_dir`
- `web_ui_data.json` in `output_dir`

### Repath
```bash
katana --script repath_katana.py -- input.katana output.katana output_dir/web_ui_data.json
```
This reads the mapping from `output_dir/web_ui_data.json` and generates:
- A modified `output.katana` file
- A `repath_log.txt` file in `output_dir` logging all path replacements

## Output Format

### katana_file_list.txt
Each line contains: `source_path,target_path`
Example:
```
V:/textures/stone_diffuse.exr,assets/file/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6/stone_diffuse.exr
```

### web_ui_data.json
```json
{
"aovs": [
{"name": "RGBA", "type": 6},
{"name": "Z", "type": 4}
],
"assets": [
{
"metadata": {"node_type": "file"},
"node": "Constant1",
"source": "V:/textures/stone_diffuse.exr",
"target": "assets/file/a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6/stone_diffuse.exr"
}
],
"render_settings": {
"renderer": "arnold",
"resolution_width": 1920,
"resolution_height": 1080,
"frame_start": 1,
"frame_end": 100,
"frame_step": 1
}
}
```

## Dependencies
- Foundry Katana Python API (NodegraphAPI, KatanaFile, AssetAPI)
- Python standard library

## Notes
- All scripts must be run within a Katana environment (using `katana --script`)
- Path separators are normalized to forward slashes internally but output uses backslashes for Windows compatibility
- Asset hashes are generated using SHA-256 (first 32 characters) to match the Maya integration format
- File sequences are automatically detected and processed
- The `repath_log.txt` file is generated in the output directory during repath operations and logs all source-target path replacements