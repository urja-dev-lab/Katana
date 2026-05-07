#!/usr/bin/env python3
"""
Katana Analysis Script
Extracts dependencies from a Katana file and generates required output files for render farm integration.
"""

import os
import json
import sys
import re
import glob
import traceback
from datetime import datetime
from pathlib import Path

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.getcwd()

print(f"Script directory: {script_dir}")
if script_dir not in sys.path:
    sys.path.append(script_dir)
    print(f"sys.path updated to include script directory {script_dir}")
print(f"sys.path: {sys.path}")

# Import from analyze directory
sys.path.append(os.path.join(script_dir, 'analyze'))
from dependency_handler import collect_all_dependencies
from aov_handler import get_aovs_from_render_nodes
from render_settings_handler import get_render_settings


def setup_script_logging(log_file):
    """Setup logging to both console and file"""
    def log_message(message):
        """Log a message with timestamp to both console and log file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}"
        print(log_entry)
        
        if log_file:
            with open(log_file, 'a') as f:
                f.write(log_entry + '\n')
    return log_message


def is_sequence_source_valid(source_path):
    """Check if a sequence source path has any existing files"""
    # Handle UDIM patterns
    if '<UDIM>' in source_path:
        # Replace <UDIM> with wildcards to find matching files
        udim_pattern = source_path.replace('<UDIM>', '[0-9][0-9][0-9][0-9]')
        try:
            matching_files = glob.glob(udim_pattern)
            # Also check for 3-digit frame numbers sometimes used with UDIM
            udim_pattern_3digit = source_path.replace('<UDIM>', '[0-9][0-9][0-9]')
            matching_files_3digit = glob.glob(udim_pattern_3digit)
            matching_files.extend(matching_files_3digit)
            
            # Remove duplicates and check if any exist
            matching_files = list(set(matching_files))
            return len(matching_files) > 0
        except:
            pass
    
    # Check for standard file sequences
    sequence_patterns = [
        r'(.*)\.(\d+)\.(.*)',  # filename.1001.ext
        r'(.*)\.(\d{4})\.(.*)',  # filename.1001.ext with 4-digit frame
        r'(.*)\.(\d{3})\.(.*)',  # filename.001.ext with 3-digit frame
        r'(.*)\.(\d{1,4})\.(.*)',  # filename.1.ext or filename.0001.ext
    ]
    
    for pattern in sequence_patterns:
        match = re.match(pattern, source_path)
        if match:
            base_path = match.group(1)
            frame_num = match.group(2)
            extension = match.group(3)
            
            # Look for sequence in the same directory
            directory = os.path.dirname(source_path)
            if not directory:
                directory = '.'
            
            try:
                files_in_dir = os.listdir(directory)
                sequence_files = []
                
                # Find all files matching the pattern
                prefix = os.path.basename(base_path)
                suffix = '.' + extension if extension else ''
                
                for f in files_in_dir:
                    if f.startswith(prefix) and f.endswith(suffix):
                        # Extract frame number
                        frame_part = f[len(prefix):-len(suffix)] if suffix else f[len(prefix):]
                        if frame_part.isdigit():
                            sequence_files.append(os.path.join(directory, f))
                
                if len(sequence_files) > 0:
                    return True
            except:
                pass
    
    # If not a sequence, fall back to regular file check
    return os.path.exists(source_path)


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
    """Save dependencies to katana_file_list.txt - only if source path exists"""
    file_list_path = os.path.join(output_directory, 'katana_file_list.txt')
    missing_assets = []
    try:
        with open(file_list_path, 'w') as f:
            for source_path in sorted(dependencies):
                # Only add paths where source actually exists
                if os.path.exists(source_path):
                    target_path = file_mapping[source_path]
                    f.write(f"{source_path},{target_path}\n")
                else:
                    missing_assets.append({
                        'source': source_path,
                        'reason': 'Source file does not exist',
                        'target': file_mapping.get(source_path, 'Unknown')
                    })
        
        log_message(f"[SUCCESS] Dependency list saved to: {file_list_path}")
        if missing_assets:
            log_message(f"[INFO] Skipped {len(missing_assets)} dependencies due to missing source files")
            for missing in missing_assets:  # Log all missing assets
                log_message(f"[WARNING] Missing asset: {missing['source']} - {missing['reason']}")
    except Exception as e:
        log_message(f"[ERROR] Failed to save dependency list: {e}")
        raise
    
    return missing_assets


def save_web_ui_data(aovs, assets_data, render_settings, output_directory, log_message):
    """Save web UI data to web_ui_data.json - only include assets where source path exists"""
    web_ui_path = os.path.join(output_directory, 'web_ui_data.json')
    missing_assets = []
    try:
        # Filter assets to only include those where source path exists
        # For sequences, check if any file in the sequence exists
        valid_assets = []
        for asset in assets_data:
            source_path = asset.get('source', '')
            if source_path:
                # Check if this is a sequence pattern
                if '<UDIM>' in source_path or any(pattern in source_path for pattern in ['.[0-9][0-9][0-9][0-9].', '.[0-9][0-9][0-9].', '.[0-9].']):
                    # For sequences, check if any file in the sequence exists
                    if is_sequence_source_valid(source_path):
                        valid_assets.append(asset)
                    else:
                        missing_assets.append({
                            'source': source_path,
                            'reason': 'No files in sequence exist',
                            'target': asset.get('target', 'Unknown')
                        })
                else:
                    # For regular files, check if the file exists
                    if os.path.exists(source_path):
                        valid_assets.append(asset)
                    else:
                        missing_assets.append({
                            'source': source_path,
                            'reason': 'Source file does not exist',
                            'target': asset.get('target', 'Unknown')
                        })
        
        web_ui_data = {
            "aovs": aovs,
            "assets": valid_assets,
            "render_settings": render_settings
        }
        
        with open(web_ui_path, 'w') as f:
            json.dump(web_ui_data, f, indent=2)
        log_message(f"[SUCCESS] Web UI data saved to: {web_ui_path}")
        if missing_assets:
            log_message(f"[INFO] Excluded {len(missing_assets)} assets from web_ui_data.json due to missing source files")
            for missing in missing_assets:  # Log all missing assets
                log_message(f"[WARNING] Missing asset: {missing['source']} - {missing['reason']}")
    except Exception as e:
        log_message(f"[ERROR] Failed to save web UI data: {e}")
        raise
    
    return missing_assets


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
        
        # Save outputs and get missing assets
        missing_from_list = save_dependency_list(dependencies, file_mapping, output_directory, log_message)
        missing_from_webui = save_web_ui_data(aovs, assets_data, render_settings, output_directory, log_message)
        
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