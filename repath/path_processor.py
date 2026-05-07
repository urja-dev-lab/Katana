import sys
import os

# Add common directory to path for katana_utils import
current_dir = os.path.dirname(os.path.abspath(__file__))
common_dir = os.path.join(current_dir, '..', 'common')
if common_dir not in sys.path:
    sys.path.append(common_dir)

from katana_utils import is_file_parameter

try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None


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
