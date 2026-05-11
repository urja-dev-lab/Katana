import sys
import os

from common.katana_utils import is_file_parameter
from common.logger import KatanaLogger

try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None


def process_nodes_for_path_replacement(mapping, logger):
    """Traverse all nodes and replace file paths"""
    logger.log("[INFO] Traversing nodes for path replacement...")
    all_nodes = NodegraphAPI.GetAllNodes()
    logger.log(f"[INFO] Found {len(all_nodes)} nodes to process")

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

                                    # Log the path change
                                    logger.repath(val, new_path)

                                    # Set the new value
                                    child.setValue(new_path, 0)

                                    replaced_count += 1
                                    if replaced_count % 10 == 0:
                                        logger.log(f"[INFO] Replaced {replaced_count} file paths...")
                        except Exception as e:
                            # Skip parameters that cause errors
                            pass
                    elif param_type == 'group':
                        replace_paths_in_group(child)

            replace_paths_in_group(root_param)
        except Exception as e:
            # Skip nodes that cause errors
            continue

    logger.log(f"[INFO] Finished processing nodes. Replaced {replaced_count} file paths.")
    return replaced_count