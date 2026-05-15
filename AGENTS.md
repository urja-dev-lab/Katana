# Katana Integration Agent Guide

## Critical Requirements
- Scripts MUST run in Katana environment: `katana --script <script.py> <args>`
- Outside Katana, Katana-specific imports (NodegraphAPI, KatanaFile, AssetAPI) will fail

## Core Commands
### Analysis
```bash
katana --script katana_analyzer.py -- <input.katana> <output_dir>
```
Outputs in `<output_dir>/renderfarm/`:
- `analysis_log.txt` - Process log
- `katana_file_list.txt` - CSV: source_path,target_path
- `web_ui_data.json` - AOVs, assets (sequence patterns), render settings, render node names

### Repath
```bash
katana --script katana_repath.py -- <input.katana> <output.katana> <output_dir>/web_ui_data.json
```
Outputs:
- Modified `output.katana` file
- `repath_log.txt` in `<output_dir>/renderfarm/`

## Key Behaviors (Non-obvious)
- Asset hashes: SHA-256, first 32 chars (matches Maya integration)
- Path normalization: Internal forward slashes, Windows output uses backslashes
- File sequences: Automatically detected (UDIM supported)
- web_ui_data.json contains sequence patterns (e.g., COL_<UDIM>.tx), NOT expanded frames
- web_ui_data.json includes render node names for render farm submission
- Logging: All missing assets listed individually in analysis_log.txt (no summaries)
- Uses centralized logger class in common/logger.py

## Testing Procedure
1. Analysis: `katana --script katana_analyzer.py -- <input.katana> <output_dir>`
2. Repath: `katana --script katana_repath.py -- <input.katana> <output.katana> <output_dir>/web_ui_data.json`

## Troubleshooting
- "Katana modules not available" = Not running in Katana environment
- Path mapping issues = Check forward/backslash handling (target paths use backslashes)
- Missing dependencies = Verify file parameters contain valid paths
- Render node issues = Check that render nodes exist in the Katana scene

## Known Issues
- Syntax errors in analyze_katana.py (lines ~140+): extra except statements
- Duplicate code in extract_render_settings function: needs cleanup
- Render node extraction: test and validate the updated functionality
- katana_repath.py currently contains only a placeholder implementation