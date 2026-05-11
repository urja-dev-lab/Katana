#!/usr/bin/env python3
"""
Katana Analysis Script
Extracts dependencies from a Katana file and generates required output files for render farm integration.
"""

import os
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Get script directory using sys.argv[0] as fallback when __file__ is not available
try:
    script_path = sys.argv[0] if sys.argv and len(sys.argv) > 0 and not any('script' in arg for arg in sys.argv) else __file__
    if script_path and os.path.exists(script_path):
        script_dir = os.path.dirname(os.path.abspath(script_path))
    else:
        # Try to get directory from the first argument that looks like a file path
        script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.path.dirname(os.path.abspath(sys.argv[0]))
except (NameError, IndexError):
    script_dir = os.getcwd()

# Add the script's directory to Python path for imports
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
    print(f"sys.path updated to include script directory {script_dir}")

# Import logger from common
common_path = os.path.join(script_dir, 'common')
if common_path not in sys.path:
    sys.path.insert(0, common_path)
    print(f"sys.path updated to include common directory {common_path}")

# Import from analyze directory
analyze_path = os.path.join(script_dir, 'analyze')
if analyze_path not in sys.path:
    sys.path.insert(0, analyze_path)
    print(f"sys.path updated to include analyze directory {analyze_path}")

from common.logger import KatanaLogger
from analyze.dependency_handler import collect_all_dependencies
from analyze.aov_handler import get_aovs_from_render_nodes
from analyze.render_settings_handler import get_render_settings


class KatanaAnalyzer:
    """Main class for Katana file analysis"""
    
    def __init__(self, input_katana, output_directory):
        self.input_katana = input_katana
        self.output_directory = output_directory
        self.logger = KatanaLogger()
        self.dependencies = set()
        self.file_mapping = {}
        self.assets_data = []
        self.aovs = []
        self.render_settings = {}
        
    def setup_logging(self):
        """Setup logging to both console and file"""
        log_file = os.path.join(self.output_directory, 'create_log.txt')
        self.logger = KatanaLogger(log_file)
        return self.logger.log
    
    def validate_input_file(self):
        """Validate that input file exists"""
        if not os.path.exists(self.input_katana):
            raise FileNotFoundError(f"Input file does not exist: {self.input_katana}")
    
    def ensure_output_directory(self):
        """Ensure output directory exists"""
        os.makedirs(self.output_directory, exist_ok=True)
    
    def collect_dependencies_and_mapping(self, logger):
        """Collect dependencies and generate file mapping"""
        logger.info("[INFO] Collecting dependencies from Katana file...")
        self.dependencies, self.file_mapping, self.assets_data = collect_all_dependencies(self.input_katana, logger)
        logger.info(f"[INFO] Found {len(self.dependencies)} unique dependencies.")
        return self.dependencies, self.file_mapping, self.assets_data
    
    def extract_aovs(self, logger):
        """Extract AOVs from render nodes"""
        logger.info("[INFO] Extracting AOVs...")
        try:
            self.aovs = get_aovs_from_render_nodes()
            logger.info(f"[INFO] Found {len(self.aovs)} AOVs")
            return self.aovs
        except Exception as e:
            logger.warning(f"[WARNING] Could not extract AOVs: {e}")
            logger.info("[INFO] Using default AOVs: RGBA, Z")
            self.aovs = [{'name': 'RGBA', 'type': 6}, {'name': 'Z', 'type': 4}]
            return self.aovs
    
    def extract_render_settings(self, logger):
            """Extract render settings from render nodes"""
            logger.info("[INFO] Extracting render settings...")
            try:
                self.render_settings = get_render_settings()
                logger.info("[INFO] Render settings extracted")
                return self.render_settings
            except Exception as e:
                logger.warning(f"[WARNING] Could not extract render settings: {e}")
                logger.info("[INFO] Using default render settings: Arnold 1920x1080 1-100x1")
                self.render_settings = {
                    'renderer': 'arnold',
                    'resolution_width': 1920,
                    'resolution_height': 1080,
                    'frame_start': 1,
                    'frame_end': 100,
                    'frame_step': 1
                }
                return self.render_settings
            except Exception as e:
                logger.warning(f"[WARNING] Could not extract render settings: {e}")
                logger.info("[INFO] Using default render settings: Arnold 1920x1080 1-100x1")
                self.render_settings = {
                    'renderer': 'arnold',
                    'resolution_width': 1920,
                    'resolution_height': 1080,
                    'frame_start': 1,
                    'frame_end': 100,
                    'frame_step': 1
                }
                return self.render_settings
            except Exception as e:
                self.logger.warning(f"[WARNING] Could not extract render settings: {e}")
                self.logger.info("[INFO] Using default render settings: Arnold 1920x1080 1-100x1")
                self.render_settings = {
                    'renderer': 'arnold',
                    'resolution_width': 1920,
                    'resolution_height': 1080,
                    'frame_start': 1,
                    'frame_end': 100,
                    'frame_step': 1
                }
                return self.render_settings

    def is_sequence_source_valid(self, source_path):
        """Check if a sequence source path has any existing files"""
        from analyze.file_sequence_validator import is_sequence_source_valid
        return is_sequence_source_valid(source_path)

    def save_dependency_list(self, log_message):
        """Save dependencies to katana_file_list.txt - only if source path exists"""
        file_list_path = os.path.join(self.output_directory, 'katana_file_list.txt')
        missing_assets = []
        try:
            with open(file_list_path, 'w') as f:
                for source_path in sorted(self.dependencies):
                    # Only add paths where source actually exists
                    if os.path.exists(source_path):
                        target_path = self.file_mapping[source_path]
                        f.write(f"{source_path},{target_path}\n")
                    else:
                        missing_assets.append({
                            'source': source_path,
                            'reason': 'Source file does not exist',
                            'target': self.file_mapping.get(source_path, 'Unknown')
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
    
    def save_web_ui_data(self, log_message):
        """Save web UI data to web_ui_data.json - only include assets where source path exists"""
        web_ui_path = os.path.join(self.output_directory, 'web_ui_data.json')
        missing_assets = []
        try:
            # Filter assets to only include those where source path exists
            # For sequences, check if any file in the sequence exists
            valid_assets = []
            for asset in self.assets_data:
                source_path = asset.get('source', '')
                if source_path:
                    # Check if this is a sequence pattern
                    if '<UDIM>' in source_path or any(pattern in source_path for pattern in ['.[0-9][0-9][0-9][0-9].', '.[0-9][0-9][0-9].', '.[0-9].']):
                        # For sequences, check if any file in the sequence exists
                        if self.is_sequence_source_valid(source_path):
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
                "aovs": self.aovs,
                "assets": valid_assets,
                "render_settings": self.render_settings
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
    
    def log_script_header(self, logger):
            """Log script header information"""
            logger.info("================================================================================")
            logger.info("Katana Analyzer Script")
            logger.info("================================================================================")
            logger.info(f"Scene path: {self.input_katana}")
            logger.info(f"Output directory: {self.output_directory}")
            logger.info("================================================================================")
            logger.info("================================================================================")
        
    def log_script_footer(self, logger):
        """Log script footer information"""
        logger.info("================================================================================")
        logger.info("[SUCCESS] Katana analysis completed successfully")
        logger.info("================================================================================")
    
    def log_script_footer(self, logger):
        """Log script footer information"""
        logger.info("================================================================================")
        logger.info("[SUCCESS] Katana analysis completed successfully")
        logger.info("================================================================================")
    
    def run(self):
        """Main execution method"""
        try:
            # Validate input file
            self.validate_input_file()
            
            # Ensure output directory exists
            self.ensure_output_directory()
            
            # Setup logging
            log_message = self.setup_logging()
            
            # Log header
            self.log_script_header(self.logger)
            
            # Collect dependencies
            self.collect_dependencies_and_mapping(self.logger)
            
            # Extract AOVs
            self.extract_aovs(self.logger)
            
            # Extract render settings
            self.extract_render_settings(self.logger)
            
            # Save outputs and get missing assets
            missing_from_list = self.save_dependency_list(log_message)
            missing_from_webui = self.save_web_ui_data(log_message)
            
            # Log footer
            self.log_script_footer(self.logger)
            
        except FileNotFoundError as e:
            self.logger.error(f"[ERROR] {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"[ERROR] Unexpected error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            traceback.print_exc()
            sys.exit(1)


def main():
    """Main entry point"""
    try:
        # Validate arguments (account for -- separator from katana --script)
        if len(sys.argv) < 4:
            print("Usage: analyze_katana.py <input.katana> <output_directory>")
            print("Usage: katana --script analyze_katana.py <input.katana> <output_directory>")
            sys.exit(1)
        
        # Skip the -- separator that katana --script adds
        input_katana = sys.argv[2]
        output_directory = sys.argv[3]
        
        # Create analyzer instance and run
        analyzer = KatanaAnalyzer(input_katana, output_directory)
        analyzer.run()
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize analyzer: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()