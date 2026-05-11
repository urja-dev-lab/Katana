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

from common.logger import KatanaLogger
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


class KatanaRepath:
    """Main class for Katana file repathing"""
    
    def __init__(self, input_katana, output_katana, mapping_file, log_file=None):
        self.input_katana = input_katana
        self.output_katana = output_katana
        self.mapping_file = mapping_file
        self.log_file = log_file
        self.logger = None
        self.mapping = {}
        
    def setup_logging(self):
        """Setup logging to file and console"""
        # Use the directory of the mapping file (web_ui_data.json) for the repath log
        log_dir = os.path.dirname(self.mapping_file)
        if log_dir:
            log_file_path = os.path.join(log_dir, 'repath_log.txt')
            self.logger = KatanaLogger(log_file_path)
        else:
            self.logger = KatanaLogger() # Console only logging
        return self.logger.log
    
    def validate_input_file(self, log_message):
        """Validate that input file exists"""
        if not os.path.exists(self.input_katana):
            raise FileNotFoundError(f"Input file does not exist: {self.input_katana}")
        log_message(f"[INFO] Input file validated: {self.input_katana}")
    
    def validate_mapping_file(self, log_message):
        """Validate that mapping file exists"""
        if not os.path.exists(self.mapping_file):
            raise FileNotFoundError(f"Mapping file does not exist: {self.mapping_file}")
        log_message(f"[INFO] Mapping file validated: {self.mapping_file}")
    
    def ensure_output_directory(self, log_message):
        """Ensure output directory exists"""
        output_dir = os.path.dirname(self.output_katana)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        log_message(f"[INFO] Output directory ensured: {output_dir}")
    
    def load_mapping_from_webui_data(self, log_message):
        """Load mapping from web_ui_data.json file"""
        log_message("[INFO] Loading mapping from web_ui_data.json...")
        mapping = {}
        try:
            with open(self.mapping_file, 'r') as f:
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
            
            log_message(f"[INFO] Loaded {len(mapping)} path mappings from {self.mapping_file}")
            self.mapping = mapping
            return mapping
        except Exception as e:
            log_message(f"[ERROR] Failed to load mapping from {self.mapping_file}: {e}")
            raise
    
    def load_katana_file(self, log_message):
        """Load the Katana file"""
        log_message("[INFO] Loading Katana file...")
        try:
            KatanaFile.Load(self.input_katana)
            log_message("[SUCCESS] Scene file loaded successfully")
            return True
        except Exception as e:
            log_message(f"[ERROR] Failed to load Katana file: {e}")
            return False
    
    def save_katana_file(self, log_message):
        """Save the modified Katana file"""
        log_message("[INFO] Saving modified Katana file...")
        try:
            # Ensure output directory exists
            self.ensure_output_directory(log_message)
            KatanaFile.Save(self.output_katana)
            log_message(f"[SUCCESS] Modified Katana file saved to: {self.output_katana}")
            return True
        except Exception as e:
            log_message(f"[ERROR] Failed to save modified Katana file: {e}")
            return False
    
    def log_script_header(self, log_message):
        """Log script header information"""
        log_message("================================================================================")
        log_message("Katana Repath Script")
        log_message("================================================================================")
        log_message(f"Input file: {self.input_katana}")
        log_message(f"Output file: {self.output_katana}")
        log_message(f"Mapping file: {self.mapping_file}")
        log_message("================================================================================")
    
    def log_script_footer(self, log_message):
        """Log script footer information"""
        log_message("================================================================================")
        log_message("[SUCCESS] Katana repath completed successfully")
        log_message("================================================================================")
    
    def run(self):
        """Main execution method"""
        try:
            # Setup logging
            log_message = self.setup_logging()
            
            # Log header
            self.log_script_header(log_message)
            
            # Validate inputs
            self.validate_input_file(log_message)
            self.validate_mapping_file(log_message)
            
            # Load mapping from the provided file (web_ui_data.json)
            self.load_mapping_from_webui_data(log_message)
            
            # Load the Katana file
            if not self.load_katana_file(log_message):
                sys.exit(1)
            
            # Process nodes for path replacement
            replaced_count = process_nodes_for_path_replacement(self.mapping, self.logger)
            log_message(f"[INFO] Path replacement completed. Replaced {replaced_count} file paths.")
            
            # Save the modified Katana file
            if not self.save_katana_file(log_message):
                sys.exit(1)
            
            # Log footer
            self.log_script_footer(log_message)
            
        except FileNotFoundError as e:
            self.logger.error(f"[ERROR] {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"[ERROR] Unexpected error: {e}")
            self.logger.error(traceback.format_exc())
            sys.exit(1)


def main():
    """Main entry point"""
    try:
        # Validate arguments (account for -- separator from katana --script)
        if len(sys.argv) < 4:
            print("Usage: repath_katana.py <input.katana> <output.katana> <mapping_file>")
            print("Usage: katana --script repath_katana.py <input.katana> <output.katana> <mapping_file>")
            print("Mapping file is compulsory and should be the web_ui_data.json from analysis")

        
        # Skip the -- separator that katana --script adds
        input_katana = sys.argv[2]
        output_katana = sys.argv[3]
        mapping_file = sys.argv[4]  # Mapping file is now compulsory
        
        # Create repath instance and run
        repath_script = KatanaRepath(input_katana, output_katana, mapping_file)
        repath_script.run()
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize repath script: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()