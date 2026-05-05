#!/usr/bin/env python3
"""
Katana Analysis Script
Extracts dependencies from a Katana file and generates required output files for render farm integration.
"""

import os
import sys
import json

# Import from common utilities
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
from katana_utils import *


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: analyze_katana.py <input.katana> <output_directory>")
        sys.exit(1)
    
    input_katana = sys.argv[1]
    output_directory = sys.argv[2]
    
    # Validate input file
    if not os.path.exists(input_katana):
        print(f"[ERROR] Input file does not exist: {input_katana}")
        sys.exit(1)
    
    # Setup logging
    log_file = os.path.join(output_directory, 'create_log.txt')
    log_message = setup_logging(log_file)
    
    log_message("================================================================================")
    log_message("Katana Analyzer Script")
    log_message("================================================================================")
    log_message(f"Scene path: {input_katana}")
    log_message(f"Output directory: {output_directory}")
    log_message("================================================================================")
    
    # Ensure output directory exists
    os.makedirs(output_directory, exist_ok=True)
    
    # Collect dependencies
    dependencies, file_mapping, assets_data = collect_all_dependencies(input_katana)
    log_message(f"[INFO] Found {len(dependencies)} unique dependencies.")
    
    # Extract AOVs
    try:
        log_message("[INFO] Extracting AOVs...")
        aovs = get_aovs_from_render_nodes()
        log_message(f"[INFO] Found {len(aovs)} AOVs")
    except Exception as e:
        log_message(f"[WARNING] Could not extract AOVs: {e}")
        aovs = [{'name': 'RGBA', 'type': 6}, {'name': 'Z', 'type': 4}]
    
    # Extract render settings
    try:
        log_message("[INFO] Extracting render settings...")
        render_settings = get_render_settings()
        log_message("[INFO] Render settings extracted")
    except Exception as e:
        log_message(f"[WARNING] Could not extract render settings: {e}")
        render_settings = {
            'renderer': 'arnold',
            'resolution_width': 1920,
            'resolution_height': 1080,
            'frame_start': 1,
            'frame_end': 100,
            'frame_step': 1
        }
    
    # Save dependencies to file (katana_file_list.txt equivalent)
    file_list_path = os.path.join(output_directory, 'katana_file_list.txt')
    try:
        with open(file_list_path, 'w') as f:
            for source_path in sorted(dependencies):
                target_path = file_mapping[source_path]
                f.write(f"{source_path},{target_path}\n")
        log_message(f"[SUCCESS] Dependency list saved to: {file_list_path}")
    except Exception as e:
        log_message(f"[ERROR] Failed to save dependency list: {e}")
        sys.exit(1)
    
    # Generate web_ui_data.json
    web_ui_path = os.path.join(output_directory, 'web_ui_data.json')
    try:
        web_ui_data = {
            "aovs": aovs,
            "assets": assets_data,
            "render_settings": render_settings
        }
        
        with open(web_ui_path, 'w') as f:
            json.dump(web_ui_data, f, indent=2)
        log_message(f"[SUCCESS] Web UI data saved to: {web_ui_path}")
    except Exception as e:
        log_message(f"[ERROR] Failed to save web UI data: {e}")
        sys.exit(1)
    
    log_message("================================================================================")
    log_message("[SUCCESS] Katana analysis completed successfully")
    log_message("================================================================================")


if __name__ == "__main__":
    main()