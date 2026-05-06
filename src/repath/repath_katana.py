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
sys.path.append(os.path.join(os.path.dirname(script_path), '..', 'common'))
from katana_utils import *


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


def load_mapping_if_provided(mapping_file, log_message):
    """Load mapping from file if provided"""
    mapping = {}
    if mapping_file:
        if os.path.exists(mapping_file):
            mapping = load_mapping_from_file(mapping_file)
            log_message(f"[INFO] Loaded {len(mapping)} path mappings from {mapping_file}")
        else:
            log_message(f"[WARNING] Mapping file does not exist: {mapping_file}")
            log_message("[INFO] Will generate mapping from Katana file instead")
    return mapping


def generate_mapping_if_needed(input_katana, mapping, log_message):
    """Generate mapping from Katana file if not provided"""
    if not mapping:
        log_message("[INFO] Generating path mapping from Katana file...")
        _, mapping, _ = collect_all_dependencies(input_katana)
        log_message(f"[INFO] Generated {len(mapping)} path mappings")
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


def process_nodes_for_path_replacement(mapping, log_message):
    """Traverse all nodes and replace file paths"""
    log_message("[INFO] Traversing nodes for path replacement...")
    all_nodes = NodegraphAPI.GetAllNodes()
    log_message(f"[INFO] Found {len(all_nodes)} nodes to process")
    
    replaced_count = 0
    for node in all_nodes:
        try:
            # Get the root parameter group for the node
            root_param = node.getParameters()
            if not root_param:
                continue
                
            # Recursive search for parameters containing asset/file info
            def replace_paths_in_group(group_param):
                nonlocal replaced_count
                for child in group_param.getChildren():
                    param_type = child.getType()
                    
                    if param_type == 'group':
                        replace_paths_in_group(child)
                        continue
                    
                    # Check if this is a file parameter
                    if is_file_parameter(child):
                        try:
                            val = child.getValue(0)
                            if val and isinstance(val, str) and val.strip():
                                # Clean the path
                                val = val.strip()
                                
                                # Skip if it's a scene graph location
                                if val.startswith('/root'):
                                    continue
                                
                                # Normalize path separators for lookup
                                normalized_path = val.replace('\\', '/')
                                
                                # Check if we have a mapping for this path
                                if normalized_path in mapping:
                                    # Get the new path
                                    new_path = mapping[normalized_path]
                                    
                                    # Set the new value
                                    child.setValue(new_path, 0)
                                    
                                    replaced_count += 1
                                    if replaced_count % 10 == 0:
                                        log_message(f"[INFO] Replaced {replaced_count} file paths...")
                        except Exception as e:
                            # Skip parameters that cause errors
                            pass
                    elif param_type == 'group':
                        replace_paths_in_group(child)
            
            replace_paths_in_group(root_param)
        except Exception as e:
            # Skip nodes that cause errors
            continue
    
    log_message(f"[INFO] Finished processing nodes. Replaced {replaced_count} file paths.")
    return replaced_count


def save_katana_file(output_katana, log_message):
    """Save the modified Katana file"""
    try:
        log_message("[INFO] Saving modified Katana file...")
        # Ensure output directory exists
        ensure_output_directory(output_katana)
        KatanaFile.SaveAs(output_katana)
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
            print("Usage: repath_katana.py <input.katana> <output.katana> [mapping_file]")
            sys.exit(1)
        
        # Skip the -- separator that katana --script adds
        input_katana = sys.argv[2]
        output_katana = sys.argv[3]
        mapping_file = sys.argv[4] if len(sys.argv) > 4 else None
        
        # Validate input file
        validate_input_file(input_katana)
        
        # Setup logging (we'll log to console for now, but could create a log file)
        log_message = setup_script_logging()
        
        # Log header
        log_script_header(log_message, input_katana, output_katana, mapping_file)
        
        # Load mapping if provided
        mapping = load_mapping_if_provided(mapping_file, log_message)
        
        # Generate mapping if needed
        mapping = generate_mapping_if_needed(input_katana, mapping, log_message)
        
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