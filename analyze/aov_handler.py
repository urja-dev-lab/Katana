def get_aovs_from_render_nodes(logger=None):
    """Extract AOV information from render nodes"""
    # Create logger if not provided
    if logger is None:
        from common.logger import KatanaLogger
        logger = KatanaLogger()

    aovs = []
    render_node_names = []
    try:
        if not NodegraphAPI:
            logger.warning("Katana modules not available, using default AOVs")
            return [{'name': 'RGBA', 'type': 6}, {'name': 'Z', 'type': 4}], render_node_names

        # Get all nodes in the scene
        all_nodes = NodegraphAPI.GetAllNodes()
        
        # Find all render nodes
        for node in all_nodes:
            if node.getType() == 'Render':
                # Add render node name to list
                render_node_names.append(node.getName())

                # Extract AOV information from render node
                render_params = node.getParameters()
                if render_params:
                    # Look for AOV parameters
                    aovs_param = render_params.getChildByName('aovs')
                    if aovs_param:
                        # Process AOV parameters
                        for i in range(aovs_param.getNumChildren()):
                            aov_child = aovs_param.getChildByIndex(i)
                            if aov_child.getType() == 'group':
                                aov_name = aov_child.getChildByName('name')
                                aov_type = aov_child.getChildByName('type')
                                if aov_name and aov_type:
                                    aovs.append({
                                        'name': aov_name.getValue(0),
                                        'type': int(aov_type.getValue(0))
                                    })
                    else:
                        # Fallback: look for individual AOV parameters
                        # Common AOV names in Katana/Arnold
                        common_aovs = ['RGBA', 'Z', 'diffuse', 'specular', 'sss',
                        'indirect_diffuse', 'indirect_specular',
                        'transmission', 'subsurface', 'emission',
                        'shadow_matte', 'opacity']
                        for aov_name in common_aovs:
                            aov_param = render_params.getChildByName(aov_name)
                            if aov_param:
                                aovs.append({
                                    'name': aov_name,
                                    'type': 6 # Default type for color AOVs
                                })
        logger.info(f"Found {len(render_node_names)} render node(s): {', '.join(render_node_names) if render_node_names else 'None'}")
    except Exception as e:
        logger.warning(f"Could not extract AOVs: {e}")
        # Return default AOVs if there's an error
        if not aovs:
            aovs = [
                {'name': 'RGBA', 'type': 6},
                {'name': 'Z', 'type': 4},
                {'name': 'diffuse', 'type': 5},
                {'name': 'specular', 'type': 5}
            ]

    return aovs, render_node_names