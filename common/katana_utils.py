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


def load_mapping_from_file(mapping_file):
    """Load path mappings from CSV file"""
    mapping = {}
    try:
        with open(mapping_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    source_path = parts[0].strip()
                    target_path = parts[1].strip()
                    # Normalize source path for lookup (convert backslashes to forward slashes)
                    normalized_source = source_path.replace('\\', '/')
                    mapping[normalized_source] = target_path
                else:
                    print(f"[WARNING] Skipping malformed line {line_num} in mapping file: {line}")
    except Exception as e:
        print(f"[ERROR] Failed to load mapping file {mapping_file}: {e}")
    return mapping



