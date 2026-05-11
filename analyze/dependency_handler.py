import os
import re
from common.katana_utils import is_file_parameter, resolve_asset_path
from analyze.file_sequence_handler import process_file_sequence
from common.katana_utils import generate_asset_hash
from common.logger import KatanaLogger

try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None


def collect_all_dependencies(input_file, logger=None):
    """Collect all dependencies from a Katana file"""
    # Create logger if not provided
    if logger is None:
        logger = KatanaLogger()
    
    dependencies = set()  # Set of resolved file paths
    file_mapping = {}     # Mapping of source -> target
    assets_data = []      # For web_ui_data.json
    added_sources = set()  # Track sources we've already added to assets_data to avoid duplicates
    
    if not NodegraphAPI or not KatanaFile:
        logger.error("Katana modules not available")
        return dependencies, file_mapping, assets_data
    
    # Load the Katana file
    try:
        KatanaFile.Load(input_file)
        logger.info("Katana file loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Katana file: {e}")
        return dependencies, file_mapping, assets_data
    
    # Traverse all nodes to find dependencies
    all_nodes = NodegraphAPI.GetAllNodes()
    logger.info(f"Found {len(all_nodes)} nodes to process")
    
    processed_count = 0
    for node in all_nodes:
        try:
            # Get the root parameter group for the node
            root_param = node.getParameters()
            if not root_param:
                continue
            
            # Recursive search for parameters containing asset/file info
            def find_paths_in_group(group_param):
                nonlocal processed_count
                for child in group_param.getChildren():
                    param_type = child.getType()
                    
                    if param_type == 'group':
                        find_paths_in_group(child)
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
                                
                                # Resolve the asset path
                                resolved_path = resolve_asset_path(val)
                                
                                # Process file sequences
                                file_sequence = process_file_sequence(resolved_path)
                                
                                # For web_ui_data.json, we want to add the original sequence pattern
                                # For dependencies and mapping, we want all expanded files
                                original_source_path = val  # Store the original path
                                
                                for file_path in file_sequence:
                                    if file_path and ('/' in file_path or '\\' in file_path):
                                        # Normalize path separators
                                        normalized_path = file_path.replace('\\', '/')
                                        
                                        # Add to dependencies
                                        dependencies.add(normalized_path)
                                        
                                        # Generate target path using hash
                                        asset_hash = generate_asset_hash(normalized_path)
                                        # Determine file extension for target
                                        _, ext = os.path.splitext(normalized_path)
                                        target_path = f"assets\\file\\{asset_hash}\\{os.path.basename(normalized_path)}"
                                        
                                        # Store mapping
                                        file_mapping[normalized_path] = target_path
                                        
                                        processed_count += 1
                                
                                # Add to web_ui_data.json - only add the original sequence pattern once
                                # This ensures we have the sequence pattern in assets, not all expanded files
                                if original_source_path and ('/' in original_source_path or '\\' in original_source_path):
                                    normalized_original = original_source_path.replace('\\', '/')
                                    # Only add if we haven't already added this source (to avoid duplicates)
                                    if normalized_original not in added_sources:
                                        # Generate target hash for the original sequence pattern
                                        asset_hash = generate_asset_hash(normalized_original)
                                        _, ext = os.path.splitext(normalized_original)
                                        target_path = f"assets\\file\\{asset_hash}\\{os.path.basename(normalized_original)}"
                                        
                                        assets_data.append({
                                            'metadata': {
                                                'node_type': child.getType()
                                            },
                                            'node': child.getParent().getName() if child.getParent() else 'Unknown',
                                            'source': normalized_original,
                                            'target': target_path
                                        })
                                        
                                        # Mark this source as added
                                        added_sources.add(normalized_original)
                        except Exception as e:
                            # Skip parameters that cause errors
                            pass
                    elif param_type == 'group':
                        find_paths_in_group(child)
            
            find_paths_in_group(root_param)
        except Exception as e:
            # Skip nodes that cause errors
            continue
    
    logger.info(f"Dependency collection completed. Processed {processed_count} file parameters.")
    return dependencies, file_mapping, assets_data