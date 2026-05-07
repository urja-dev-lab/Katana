try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None

def get_aovs_from_render_nodes():
    """Extract AOV information from render nodes"""
    aovs = []
    try:
        if not NodegraphAPI:
            return [{'name': 'RGBA', 'type': 6}, {'name': 'Z', 'type': 4}]
            
        # Get all render nodes (typically Render node type)
        all_nodes = NodegraphAPI.GetAllNodes()
        for node in all_nodes:
            if node.getType() == 'Render':
                # Extract AOV information from render node
                render_settings = node.getParameters()
                if render_settings:
                    # Look for AOV parameters
                    aovs_param = render_settings.getChildByName('aovs')
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
                            aov_param = render_settings.getChildByName(aov_name)
                            if aov_param:
                                aovs.append({
                                    'name': aov_name,
                                    'type': 6  # Default type for color AOVs
                                })
    except Exception as e:
        print(f"[WARNING] Could not extract AOVs: {e}")
    
    # If no AOVs found, provide some defaults based on common Katana setups
    if not aovs:
        aovs = [
            {'name': 'RGBA', 'type': 6},
            {'name': 'Z', 'type': 4},
            {'name': 'diffuse', 'type': 5},
            {'name': 'specular', 'type': 5}
        ]
    
    return aovs
