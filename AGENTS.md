# Katana Integration Agent Guide

## Critical Requirements
- Scripts MUST run in Katana environment: `katana --script <script.py> <args>`
- Outside Katana, Katana-specific imports (NodegraphAPI, KatanaFile, AssetAPI) will fail
- Helper script (Linux): `./run_katana_analysis.sh input.katana output_dir`

## Core Commands
### Analysis
```bash
katana --script analyze_katana.py -- input.katana output_dir
```
Outputs:
- `create_log.txt` - Process log (all operations, missing assets individually logged)
- `katana_file_list.txt` - CSV: source_path,target_path (only existing sources)
- `web_ui_data.json` - AOVs, assets (sequence patterns only), render settings

### Repath (Class-Based, mapping file IS REQUIRED)
```bash
katana --script repath_katana.py -- <input.katana> <output.katana> <output_dir>/web_ui_data.json

## Key Behaviors (Non-obvious)
- Asset hashes: SHA-256, first 32 chars (matches Maya integration)
- Path normalization: Internal forward slashes, Windows output uses backslashes
- File sequences: Automatically detected (UDIM supported)
- web_ui_data.json contains sequence patterns (e.g., COL_<UDIM>.tx), NOT expanded frames
- Logging: All missing assets listed individually in create_log.txt (no summaries)
- Uses centralized logger class in common/logger.py for consistent logging

## Testing Procedure
1. Analysis: `./run_katana_analysis.sh <input.katana> <output_dir>`
2. Repath: `katana --script repath_katana.py -- <input.katana> <output.katana> <output_dir>/web_ui_data.json`

## Troubleshooting
- "Katana modules not available" = Not running in Katana environment
- Path mapping issues = Check forward/backslash handling (target paths use backslashes)
- Missing dependencies = Verify file parameters contain valid paths