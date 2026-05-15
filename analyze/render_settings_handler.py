from common.logger import KatanaLogger

try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None

from analyze.node_trevarsal_handler import get_input_nodes
from analyze.node_attr_fetcher import param_to_dict


def get_render_settings(logger=None):
    """Extract render settings from render nodes by checking their upstream settings nodes"""
    # Create logger if not provided
    if logger is None:
        logger = KatanaLogger()

    render_nodes_data = {}
    # try:
    if not NodegraphAPI:
        logger.warning("Katana modules not available, using empty render nodes data")
        return {}

    all_nodes = NodegraphAPI.GetAllNodes()
    
    # Find all render nodes and collect their settings from upstream nodes
    for node in all_nodes:
        if node.getType() == 'Render':
            render_node_name = node.getName()
            logger.info(f"Found render node: {render_node_name}")
            
            # Get the settings node connected to this render node
            settings_node = get_input_nodes(node)[0] if get_input_nodes(node) else None
            if settings_node:
                settings_node_name = settings_node.getName()
                logger.info(f"Found settings node: {settings_node_name} for render node: {render_node_name}")
            else:
                settings_node_name = None

            # Extract settings from the settings node if it exists
            if settings_node:
                settings = param_to_dict(settings_node.getParameters()) if settings_node else {}
            
                
                # If we didn't find a specific renderer parameter, check for Arnold renderer as fallback
                # if 'renderer' not in settings:
                #     settings['renderer'] = 'dl'  # Default to 3Delight

            
            # Build the data structure for this render node
            render_nodes_data[render_node_name] = {
                "settings_node": settings_node_name,
                "render_settings": settings
            }
            
            logger.info(f"Extracted settings for render node '{render_node_name}': {settings}")

    # except Exception as e:
    #     logger.warning(f"Could not extract render settings: {e}")
    #     # Return empty dict on error rather than crashing
    #     return {}

    return render_nodes_data