#!/usr/bin/env python3
"""
Katana Analysis Script
Extracts dependencies from a Katana file and generates required output files for render farm integration.
"""

import os
import sys
import json
import traceback
from datetime import datetime

# Import from common utilities
script_path = sys.argv[0]
sys.path.append(os.path.join(os.path.dirname(script_path), '..', 'common'))
from katana_utils import *


def setup_script_logging(log_file):
    """Setup logging to both console and file"""
    def log_message(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}"
        print(log_entry)
        with open(log_file, 'a') as f:
            f.write(log_entry + '\n')
    return log_message


def validate_input_file(input_katana):
    """Validate that input file exists"""
    if not os.path.exists(input_katana):
        raise FileNotFoundError(f"Input file does not exist: {input_katana}")


def ensure_output_directory(output_directory):
    """Ensure output directory exists"""
    os.makedirs(output_directory, exist_ok=True)


def collect_dependencies_and_mapping(input_katana, log_message):
    """Collect dependencies and generate file mapping"""
    log_message("[INFO] Collecting dependencies from Katana file...")
    dependencies, file_mapping, assets_data = collect_all_dependencies(input_katana)
    log_message(f"[INFO] Found {len(dependencies)} unique dependencies.")
    return dependencies, file_mapping, assets_data


def extract_aovs(log_message):
    """Extract AOVs from render nodes"""
    log_message("[INFO] Extracting AOVs...")
    try:
        aovs = get_aovs_from_render_nodes()
        log_message(f"[INFO] Found {len(aovs)} AOVs")
        return aovs
    except Exception as e:
        log_message(f"[WARNING] Could not extract AOVs: {e}")
        log_message("[INFO] Using default AOVs: RGBA, Z")
        return [{'name': 'RGBA', 'type': 6}, {'name': 'Z', 'type': 4}]


def extract_render_settings(log_message):
    """Extract render settings from render nodes"""
    log_message("[INFO] Extracting render settings...")
    try:
        render_settings = get_render_settings()
        log_message("[INFO] Render settings extracted")
        return render_settings
    except Exception as e:
        log_message(f"[WARNING] Could not extract render settings: {e}")
        log_message("[INFO] Using default render settings: Arnold 1920x1080 1-100x1")
        return {
            'renderer': 'arnold',
            'resolution_width': 1920,
            'resolution_height': 1080,
            'frame_start': 1,
            'frame_end': 100,
            'frame_step': 1
        }


def save_dependency_list(dependencies, file_mapping, output_directory, log_message):
    """Save dependencies to katana_file_list.txt"""
    file_list_path = os.path.join(output_directory, 'katana_file_list.txt')
    try:
        with open(file_list_path, 'w') as f:
            for source_path in sorted(dependencies):
                target_path = file_mapping[source_path]
                f.write(f"{source_path},{target_path}\n")
        log_message(f"[SUCCESS] Dependency list saved to: {file_list_path}")
    except Exception as e:
        log_message(f"[ERROR] Failed to save dependency list: {e}")
        raise


def save_web_ui_data(aovs, assets_data, render_settings, output_directory, log_message):
    """Save web UI data to web_ui_data.json"""
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
        raise


def log_script_header(log_message, input_katana, output_directory):
    """Log script header information"""
    log_message("================================================================================")
    log_message("Katana Analyzer Script")
    log_message("================================================================================")
    log_message(f"Scene path: {input_katana}")
    log_message(f"Output directory: {output_directory}")
    log_message("================================================================================")


def log_script_footer(log_message):
    """Log script footer information"""
    log_message("================================================================================")
    log_message("[SUCCESS] Katana analysis completed successfully")
    log_message("================================================================================")


def main():
    """Main entry point"""
    try:
        # Validate arguments (account for -- separator from katana --script)
        if len(sys.argv) < 4:
            print("Usage: analyze_katana.py <input.katana> <output_directory>")
            sys.exit(1)
        
        # Skip the -- separator that katana --script adds
        input_katana = sys.argv[2]
        output_directory = sys.argv[3]
        
        # Validate input file
        validate_input_file(input_katana)
        
        # Ensure output directory exists
        ensure_output_directory(output_directory)
        
        # Setup logging
        log_file = os.path.join(output_directory, 'create_log.txt')
        log_message = setup_script_logging(log_file)
        
        # Log header
        log_script_header(log_message, input_katana, output_directory)
        
        # Collect dependencies
        dependencies, file_mapping, assets_data = collect_dependencies_and_mapping(input_katana, log_message)
        
        # Extract AOVs
        aovs = extract_aovs(log_message)
        
        # Extract render settings
        render_settings = extract_render_settings(log_message)
        
        # Save outputs
        save_dependency_list(dependencies, file_mapping, output_directory, log_message)
        save_web_ui_data(aovs, assets_data, render_settings, output_directory, log_message)
        
        # Log footer
        log_script_footer(log_message)
        
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()