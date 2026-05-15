# Katana Render Farm Integration

This package provides integration between Foundry Katana and a render farm system, mirroring the existing Maya integration workflow.

## Progress Update

### Completed Features
- Core analysis functionality for extracting Katana file dependencies
- Path remapping functionality for server-side path adjustments
- Support for file sequence detection (UDIM and frame sequences)
- Asset hashing using SHA-256 (first 32 characters) to match Maya integration
- AOV extraction from render nodes
- Render settings extraction from render nodes
- **NEW**: Render node name extraction for render farm submission

### Recent Enhancements
- Added support for extracting render node names in web_ui_data.json
- Updated web_ui_data.json structure to include render_nodes array
- Enhanced documentation with render farm submission requirements

### Pending Fixes
- Syntax errors in analyze_katana.py (lines ~140+ have extra except statements)
- Need to clean up duplicate code in extract_render_settings function
- Test and validate the updated render node extraction functionality

## Components

### 1. Analysis Script (`analyze_katana.py`)
Client-side script that extracts all dependencies from a Katana file and generates:
- `analysis_log.txt`: Detailed log of the analysis process
- `katana_file_list.txt`: CSV listing of source files and their target hash paths
- `web_ui_data.json`: JSON containing AOVs, assets, render settings, and render node names

### 2. Repath Script (`repath_katana.py`)
Server-side script that modifies a Katana file to adjust paths from client-side to server-side references using the mapping from `web_ui_data.json`.

### 3. Utility Module (`katana_utils.py`)
Shared utility functions used by both scripts.

## Usage

### Analysis
Use the helper script:
```bash
katana --script katana_analyzer.py -- input.katana output_dir
```
Example: 
```bash
katana --script katana_analyzer.py -- "/srv/local/Dev/SQN/Samples/Katana_Sample_Project/Bus_v002.katana" "/srv/local/Dev/GIT/Katana/Katana/output"
```
This generates:
- `analysis_log.txt` in `output_dir`
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
  },
  "render_nodes": ["PrimaryRender", "ShadowRender"]
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
- **NEW**: web_ui_data.json now includes render_nodes array for render farm submission