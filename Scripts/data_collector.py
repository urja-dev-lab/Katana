import os
import sys
import NodegraphAPI
from Katana import KatanaFile, AssetAPI

def get_asset_dependencies(katana_file):
    # Load the scene in headless mode
    print(f"[INFO] Loading Katana file: {katana_file}")
    KatanaFile.Load(katana_file)
    
    dependencies = set()
    all_nodes = NodegraphAPI.GetAllNodes()

    for node in all_nodes:
        # Get the root parameter group for the node
        root_param = node.getParameters()
        if not root_param:
            continue
            
        # Recursive search for parameters containing asset/file info
        find_paths_in_group(root_param, dependencies)

    return sorted(list(dependencies))

def find_paths_in_group(group_param, dependencies):
    for child in group_param.getChildren():
        param_type = child.getType()
        
        if param_type == 'group':
            find_paths_in_group(child, dependencies)
            continue
        
        if param_type not in ['string', 'stringArray']:
            continue

        try:
            val = child.getValue(0)
            if not val or not isinstance(val, str) or not val.strip():
                continue
            
            # --- 1. CLEANING: Remove Scene Graph locations ---
            # If it starts with /root, it's a Katana scene path, not a disk asset
            if val.startswith('/root'):
                continue

            # --- 2. IDENTIFICATION: Is this a file? ---
            name_lower = child.getName().lower()
            
            # Keywords common in Arnold/3Delight texture & proxy nodes
            file_keywords = ['asset', 'file', 'path', 'filename', 'map', 'tex', 'image', 'color_item']
            is_file_param = any(k in name_lower for k in file_keywords)

            # Check for file extension patterns (e.g., .exr, .tx, .tif, .hdr, .abc, .vdb)
            has_extension = any(val.lower().endswith(ext) for ext in 
                               ['.exr', '.tx', '.tif', '.tiff', '.hdr', '.jpg', '.png', '.abc', '.vdb', '.ass'])

            # --- 3. VALIDATION ---
            # We want it if it's a file widget OR it has a file extension
            if is_file_param or has_extension:
                # Basic check to ensure it actually looks like a disk path
                if '/' in val or '\\' in val or '::' in val:
                    
                    # Resolve via AssetAPI
                    try:
                        resolved = AssetAPI.GetDefaultAssetPlugin().resolveAsset(val)
                        final_path = resolved if resolved else val
                        
                        # Only add if it's not a relative internal name
                        if '/' in final_path or '\\' in final_path:
                            dependencies.add(final_path.replace('\\', '/'))
                    except:
                        dependencies.add(val.replace('\\', '/'))
        except:
            continue
            
# def find_paths_in_group(group_param, dependencies):
#     for child in group_param.getChildren():
#         param_type = child.getType()
        
#         # 1. If it's a group, recurse
#         if param_type == 'group':
#             find_paths_in_group(child, dependencies)
#             continue
        
#         # 2. Only attempt getValue on string or number-based parameters
#         # This avoids the TypeError on buttons/pointers/etc.
#         if param_type not in ['string', 'number', 'stringArray', 'numberArray']:
#             continue

#         try:
#             val = child.getValue(0)
#             if not val or not isinstance(val, (str, list)):
#                 continue
            
#             # If it's a list (stringArray), just take the first index or join them
#             if isinstance(val, list):
#                 val = val[0] if len(val) > 0 else ""
                
#             if not isinstance(val, str) or not val.strip():
#                 continue

#             # 3. Check for Hints (Widget type)
#             is_file_widget = False
#             try:
#                 hint_str = child.getHintString()
#                 if hint_str and ('assetIdInput' in hint_str or 'fileInput' in hint_str):
#                     is_file_widget = True
#             except:
#                 pass

#             # 4. Keyword Check
#             name_lower = child.getName().lower()
#             is_likely_path = any(k in name_lower for k in ['asset', 'file', 'path', 'filename'])
            
#             # 5. Validation & Resolution
#             # We look for path markers: slashes, backslashes, or asset colons
#             if is_file_widget or (is_likely_path and ('/' in val or '\\' in val or '::' in val)):
#                 # Clean up the path (convert backslashes for consistency)
#                 clean_val = val.replace('\\', '/')
                
#                 try:
#                     resolved = AssetAPI.GetDefaultAssetPlugin().resolveAsset(clean_val)
#                     final_path = resolved if resolved else clean_val
#                     dependencies.add(final_path)
#                     print(f"[FOUND] {child.getFullName()} -> {final_path}")
#                 except:
#                     dependencies.add(clean_val)
#         except Exception as e:
#             # Silently skip parameters that don't support value access
#             continue

def save_to_file(data, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        for path in data:
            f.write(f"{path}\n")
    print(f"[SUCCESS] Dependencies saved to: {output_path}")

if __name__ == "__main__":
    # Filter out the script name and the optional '--' separator
    args = [a for a in sys.argv[1:] if a != '--']

    if len(args) < 2:
        print("Usage: katana --script analyze_katana.py <input.katana> <output.txt>")
        sys.exit(1)

    input_katana = args[0]
    output_txt = args[1]

    deps = get_asset_dependencies(input_katana)
    save_to_file(deps, output_txt)