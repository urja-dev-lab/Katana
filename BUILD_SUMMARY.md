# Katana Integration Build Summary

## Overview
This document summarizes the implementation of the Katana integration for the render farm system. The implementation follows a modular design with shared utility functions.

## Files Created

### 1. katana_utils.py
Contains shared utility functions used by both analysis and repath scripts:
- `setup_logging()`: Configures logging to console and file
- `is_file_parameter()`: Determines if a parameter references a file asset
- `resolve_asset_path()`: Resolves asset paths using Katana's AssetAPI
- `generate_asset_hash()`: Creates consistent hash for asset organization
- `process_file_sequence()`: Detects and expands file sequences
- `get_aovs_from_render_nodes()`: Extracts AOV information from render nodes
- `get_render_settings()`: Extracts render settings from render nodes
- `collect_all_dependencies()`: Main function to gather all dependencies from a Katana file
- `load_mapping_from_file()`: Loads path mappings from CSV file

### 2. analyze_katana.py
Client-side analysis script that:
- Takes input Katana file and output directory as arguments
- Logs analysis process to create_log.txt
- Collects all dependencies using utility functions
- Generates katana_file_list.txt (CSV: source_path,target_path)
- Generates web_ui_data.json (JSON with AOVs, assets, render settings)
- Exits with appropriate status codes

### 3. repath_katana.py
Server-side repath script that:
- Takes input Katana file, output Katana file, and optional mapping file as arguments
- Loads or generates path mappings
- Modifies the Katana file to replace client paths with server paths
- Saves the modified Katana file
- Exits with appropriate status codes

## Modular Design Benefits
- Shared utility functions reduce code duplication
- Easier maintenance and updates
- Consistent behavior between analysis and repath phases
- Clear separation of concerns
- Improved testability

## Usage

### Analysis Script
```bash
python analyze_katana.py input.katana /path/to/output/directory
```

### Repath Script
```bash
# With automatic mapping generation
python repath_katana.py input.katana output.katana

# With provided mapping file
python repath_katana.py input.katana output.katana mapping.csv
```

## Output Files
After running the analysis script, the output directory will contain:
- create_log.txt: Detailed log of the analysis process
- katana_file_list.txt: CSV listing of source files and their target hash paths
- web_ui_data.json: JSON containing AOVs, assets, and render settings

## Dependencies
- Foundry Katana Python API (NodegraphAPI, KatanaFile, AssetAPI)
- Python standard library (os, sys, json, hashlib, re, datetime)

## Error Handling
- Comprehensive error checking with informative messages
- Graceful degradation when optional data is not available
- Non-zero exit codes on failure
- Detailed logging for troubleshooting

## Testing
The scripts have been syntax-checked and are ready for deployment in a Katana environment.
Actual testing requires a Katana installation with sample files containing texture dependencies.

## Next Steps
1. Deploy to render farm environment
2. Test with actual Katana files containing texture dependencies
3. Verify output file formats match expectations
4. Integrate with render farm job submission system