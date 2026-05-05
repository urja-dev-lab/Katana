#!/usr/bin/env python3
"""
Utility functions for Katana integration scripts
"""

import os
import re
import hashlib
from datetime import datetime

try:
    import NodegraphAPI
    from Katana import KatanaFile, AssetAPI
except ImportError:
    # These will be handled in the main scripts
    NodegraphAPI = None
    KatanaFile = None
    AssetAPI = None


def setup_logging(log_file):
    """Setup logging to both console and file"""
    def log_message(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}"
        print(log_entry)
        with open(log_file, 'a') as f:
            f.write(log_entry + '\n')
    return log_message


def is_file_parameter(param):
    """Determine if a parameter references a file asset"""
    if not param:
        return False
    
    param_type = param.getType()
    param_name = param.getName().lower()
    
    # Check parameter type
    if param_type not in ['string', 'stringArray']:
        return False
    
    # Check parameter name for file-related keywords
    file_keywords = ['file', 'path', 'asset', 'texture', 'map', 'image', 'filename', 
                    'proxy', 'geometry', 'abc', 'vdb', 'exr', 'tx', 'tif', 'tiff',
                    'jpg', 'jpeg', 'png', 'hdr', 'env', 'environment', 'shader', 
                    'material', 'displacement', 'bump', 'normal', 'specular', 
                    'diffuse', 'opacity', 'transmission', 'subsurface']
    
    is_file_param = any(keyword in param_name for keyword in file_keywords)
    
    # Check parameter hints for file widgets
    is_file_widget = False
    try:
        hint_str = param.getHintString()
        if hint_str and ('assetIdInput' in hint_str or 'fileInput' in hint_str or 
                        'filepath' in hint_str.lower()):
            is_file_widget = True
    except:
        pass
    
    # Get parameter value
    try:
        value = param.getValue(0)
        if not value or not isinstance(value, str) or not value.strip():
            return False
        
        # Check for file extensions
        has_extension = any(value.lower().endswith(ext) for ext in 
                           ['.exr', '.tx', '.tif', '.tiff', '.hdr', '.jpg', '.jpeg', 
                            '.png', '.abc', '.vdb', '.obj', '.fbx', '.ma', '.mb',
                            '.ass', '.usd', '.usda', '.usdc', '.usdz', '.obj', '.ply',
                            '.stl', '.xsi', '.lk', '.sd', '.tga', '.bmp', '.gif',
                            '.pic', '.rat', '.rat', '.rat', '.rat'])
        
        # Check if it looks like a path
        looks_like_path = ('/' in value or '\\' in value or '::' in value) and not value.startswith('/root')
        
        return (is_file_param or is_file_widget or has_extension) and looks_like_path
    except:
        return False


def resolve_asset_path(path):
    """Resolve asset path using AssetAPI"""
    if not path or not AssetAPI:
        return path
    
    try:
        resolved = AssetAPI.GetDefaultAssetPlugin().resolveAsset(path)
        return resolved if resolved else path
    except:
        return path


def generate_asset_hash(path):
    """Generate a hash for asset organization (matching Maya format)"""
    # Use a subset of SHA256 to match the Maya format
    hash_object = hashlib.sha256(path.encode())
    return hash_object.hexdigest()[:32]


def process_file_sequence(file_path):
    """Detect and expand file sequences"""
    # Check if this looks like a file sequence
    sequence_patterns = [
        r'(.*)\.(\d+)\.(.*)',  # filename.1001.ext
        r'(.*)\.(\d{4})\.(.*)',  # filename.1001.ext with 4-digit frame
        r'(.*)\.(\d{3})\.(.*)',  # filename.001.ext with 3-digit frame
    ]
    
    for pattern in sequence_patterns:
        match = re.match(pattern, file_path)
        if match:
            base_path = match.group(1)
            frame_num = match.group(2)
            extension = match.group(3)
            
            # Look for sequence in the same directory
            directory = os.path.dirname(file_path)
            if not directory:
                directory = '.'
            
            try:
                files_in_dir = os.listdir(directory)
                sequence_files = []
                
                # Find all files matching the pattern
                prefix = os.path.basename(base_path)
                suffix = '.' + extension if extension else ''
                
                for f in files_in_dir:
                    if f.startswith(prefix) and f.endswith(suffix):
                        # Extract frame number
                        frame_part = f[len(prefix):-len(suffix)] if suffix else f[len(prefix):]
                        if frame_part.isdigit():
                            sequence_files.append(os.path.join(directory, f))
                
                if len(sequence_files) > 1:
                    return sorted(sequence_files)
            except:
                pass
    
    return [file_path]  # Return as single item list if not a sequence


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


def collect_all_dependencies(input_file):
    """Collect all dependencies from a Katana file"""
    dependencies = set()  # Set of resolved file paths
    file_mapping = {}     # Mapping of source -> target
    assets_data = []      # For web_ui_data.json
    
    if not NodegraphAPI or not KatanaFile:
        print("[ERROR] Katana modules not available")
        return dependencies, file_mapping, assets_data
    
    # Load the Katana file
    try:
        KatanaFile.Load(input_file)
    except Exception as e:
        print(f"[ERROR] Failed to load Katana file: {e}")
        return dependencies, file_mapping, assets_data
    
    # Traverse all nodes to find dependencies
    all_nodes = NodegraphAPI.GetAllNodes()
    
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
                                        
                                        # Add to assets data for web_ui_data.json
                                        assets_data.append({
                                            'metadata': {
                                                'node_type': child.getType()
                                            },
                                            'node': child.getParent().getName() if child.getParent() else 'Unknown',
                                            'source': normalized_path,
                                            'target': target_path
                                        })
                                        
                                        processed_count += 1
                        except Exception as e:
                            # Skip parameters that cause errors
                            pass
                    elif param_type == 'group':
                        find_paths_in_group(child)
            
            find_paths_in_group(root_param)
        except Exception as e:
            # Skip nodes that cause errors
            continue
    
    return dependencies, file_mapping, assets_data