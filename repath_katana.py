#!/usr/bin/env python3
"""
Katana Repath Script
Modifies a Katana file to adjust paths from client-side to server-side references.
"""

import os
import sys
import json
import traceback
from datetime import datetime

# Import from common utilities
script_path = sys.argv[0]
script_dir = os.path.dirname(os.path.abspath(script_path))
# Add the script's directory to Python path for imports
if script_dir not in sys.path:
    sys.path.append(script_dir)
    print(f"sys.path updated to include script directory {script_dir}")
from common.katana_utils import load_mapping_from_file
from repath.path_processor import process_nodes_for_path_replacement

# Import Katana APIs
try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None


def setup_script_logging(log_file=None):
    """Setup logging to console and optionally to file"""
    def log_message(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}"
        print(log_entry)
        if log_file:
            with open(log_file, 'a') as f:
                f.write(log_entry + '\n')
    return log_message


def validate_input_file(input_katana):
    """Validate that input file exists"""
    if not os.path.exists(input_katana):
        raise FileNotFoundError(f"Input file does not exist: {input_katana}")


def ensure_output_directory(output_path):
    """Ensure output directory exists"""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)


def load_mapping_from_webui_data(mapping_file, log_message):
    """Load mapping from web_ui_data.json file"""
    mapping = {}
    try:
        with open(mapping_file, 'r') as f:
            web_ui_data = json.load(f)
        
        # Extract assets from web_ui_data.json
        assets = web_ui_data.get('assets', [])
        for asset in assets:
            source_path = asset.get('source', '')
            target_path = asset.get('target', '')
            if source_path and target_path:
                # Normalize source path for lookup (convert backslashes to forward slashes)
                normalized_source = source_path.replace('\\', '/')
                mapping[normalized_source] = target_path
        
        log_message(f"[INFO] Loaded {len(mapping)} path mappings from {mapping_file}")
    except Exception as e:
        log_message(f"[ERROR] Failed to load mapping from {mapping_file}: {e}")
        raise
    
    return mapping


def load_katana_file(input_katana, log_message):
    """Load the Katana file"""
    try:
        log_message("[INFO] Loading Katana file...")
        KatanaFile.Load(input_katana)
        log_message("[SUCCESS] Scene file loaded successfully")
        return True
    except Exception as e:
        log_message(f"[ERROR] Failed to load Katana file: {e}")
        return False




def save_katana_file(output_katana, log_message):
    """Save the modified Katana file"""
    try:
        log_message("[INFO] Saving modified Katana file...")
        # Ensure output directory exists
        ensure_output_directory(output_katana)
        KatanaFile.Save(output_katana)
        log_message(f"[SUCCESS] Modified Katana file saved to: {output_katana}")
        return True
    except Exception as e:
        log_message(f"[ERROR] Failed to save modified Katana file: {e}")
        return False


def log_script_header(log_message, input_katana, output_katana, mapping_file=None):
    """Log script header information"""
    log_message("================================================================================")
    log_message("Katana Repath Script")
    log_message("================================================================================")
    log_message(f"Input file: {input_katana}")
    log_message(f"Output file: {output_katana}")
    if mapping_file:
        log_message(f"Mapping file: {mapping_file}")
    log_message("================================================================================")


def log_script_footer(log_message):
    """Log script footer information"""
    log_message("================================================================================")
    log_message("[SUCCESS] Katana repath completed successfully")
    log_message("================================================================================")


def main():
    """Main entry point"""
    try:
        # Validate arguments (account for -- separator from katana --script)
        if len(sys.argv) < 4:
            print("Usage: repath_katana.py <input.katana> <output.katana> <mapping_file>")
            print("Mapping file is compulsory and should be the web_ui_data.json from analysis")
            sys.exit(1)
        
        # Skip the -- separator that katana --script adds
        input_katana = sys.argv[2]
        output_katana = sys.argv[3]
        mapping_file = sys.argv[4]  # Mapping file is now compulsory
        
        # Validate input file
        validate_input_file(input_katana)
        
        # Validate mapping file exists
        if not os.path.exists(mapping_file):
            print(f"[ERROR] Mapping file does not exist: {mapping_file}")
            sys.exit(1)
        
        # Setup logging (we'll log to console for now, but could create a log file)
        log_message = setup_script_logging()
        
        # Log header
        log_script_header(log_message, input_katana, output_katana, mapping_file)
        
        # Load mapping from the provided file (web_ui_data.json)
        mapping = load_mapping_from_webui_data(mapping_file, log_message)
        
        # Load the Katana file
        if not load_katana_file(input_katana, log_message):
            sys.exit(1)
        
        # Process nodes for path replacement
        replaced_count = process_nodes_for_path_replacement(mapping, log_message)
        
        # Save the modified Katana file
        if not save_katana_file(output_katana, log_message):
            sys.exit(1)
        
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