# Katana Integrations Agent Guide

## Environment
- Scripts MUST run in Katana environment: `katana --script <script.py> <args>`
- Outside Katana, Katana-specific imports (NodegraphAPI, KatanaFile, AssetAPI) will fail
- Use the helper script for Linux: `./run_katana_analysis.sh input.katana output_dir`

## Commands
### Analysis
```bash
katana --script src/analyze/analyze_katana.py -- input.katana output_dir
```
Or using the helper script (Linux):
```bash
./run_katana_analysis.sh input.katana output_dir
```
Outputs:
- `output_dir/create_log.txt` - Process log
- `output_dir/katana_file_list.txt` - CSV: source_path,target_path
- `output_dir/web_ui_data.json` - AOVs, assets, render settings

### Repath
Auto-generate mapping:
```bash
katana --script src/repath/repath_katana.py -- input.katana output.katana
```

With existing mapping:
```bash
katana --script src/repath/repath_katana.py -- input.katana output.katana mapping.csv
```

## Key Behaviors
- Asset hashes: SHA-256, first 32 chars (matches Maya integration)
- Path normalization: Internal forward slashes, Windows output uses backslashes in target paths
- File sequences: Automatically detected and expanded
- Missing AOV/render settings: Defaults to RGBA/Z AOVs, Arnold 1920x1080 1-100x1
- Logging: Scripts log to console and create_log.txt (analysis only)

## Testing
- Test scene: `src/samples/test_scene.katana`
- Batch test: `./run_katana_analysis.sh src/samples/test_scene.katana ./renderfarm`
- Outputs appear in specified output directory (not hardcoded to renderfarm/)

## Dependencies
- Foundry Katana Python API (bundled with Katana)
- Python standard library only
- No external pip packages required

## Troubleshooting
- "Katana modules not available" = Not running in Katana environment
- Path mapping issues = Check forward/backward slash handling (target paths use backslashes)
- Missing dependencies = Verify file parameters contain valid paths
- Script arguments: The helper script expects exactly 2 arguments (input.katana output_dir)