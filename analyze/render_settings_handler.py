try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None

    
def get_render_settings():
    """Extract render settings from render nodes"""
    settings = {}
    try:
        if not NodegraphAPI:
            # Provide defaults
            return {
                'renderer': 'arnold',
                'resolution_width': 1920,
                'resolution_height': 1080,
                'frame_start': 1,
                'frame_end': 100,
                'frame_step': 1
            }
            
        all_nodes = NodegraphAPI.GetAllNodes()
        for node in all_nodes:
            if node.getType() == 'Render':
                render_params = node.getParameters()
                if render_params:
                    # Extract common render settings
                    settings['renderer'] = render_params.getChildByName('renderer').getValue(0) if render_params.getChildByName('renderer') else 'arnold'
                    settings['resolution_width'] = render_params.getChildByName('resolutionWidth').getValue(0) if render_params.getChildByName('resolutionWidth') else 1920
                    settings['resolution_height'] = render_params.getChildByName('resolutionHeight').getValue(0) if render_params.getChildByName('resolutionHeight') else 1080
                    settings['frame_start'] = render_params.getChildByName('frameStart').getValue(0) if render_params.getChildByName('frameStart') else 1
                    settings['frame_end'] = render_params.getChildByName('frameEnd').getValue(0) if render_params.getChildByName('frameEnd') else 100
                    settings['frame_step'] = render_params.getChildByName('frameStep').getValue(0) if render_params.getChildByName('frameStep') else 1
                    break
    except Exception as e:
        print(f"[WARNING] Could not extract render settings: {e}")
        # Provide defaults
        settings = {
            'renderer': 'arnold',
            'resolution_width': 1920,
            'resolution_height': 1080,
            'frame_start': 1,
            'frame_end': 100,
            'frame_step': 1
        }
    
    return settings
