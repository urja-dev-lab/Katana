# Katana Python API Commands Reference

## Overview

This document provides a comprehensive reference for Foundry Katana Python API commands used in integration projects. The commands are organized by module and functionality.

## Core API Modules

### NodegraphAPI
The primary module for working with nodes in Katana.

#### Key Commands:
- `NodegraphAPI.GetAllNodes()` - Returns a list of all nodes in the current node graph
- `NodegraphAPI.GetNode(name)` - Gets a node by name
- `node.getType()` - Returns the type of a node
- `node.getName()` - Returns the name of a node
- `node.getParameters()` - Returns the root parameter group for a node
- `node.addInputPort(name)` - Adds an input port to a node
- `node.removeInputPort(name)` - Removes an input port from a node

### Katana Module
Module for file operations and scene management.

#### Key Commands:
- `KatanaFile.Load(filename)` - Loads a Katana file
- `KatanaFile.Save(filename)` - Saves the current scene to a file
- `KatanaFile.WriteDelta(filename, node)` - Writes scene delta to file

### AssetAPI
Module for asset management and path resolution.

#### Key Commands:
- `AssetAPI.GetDefaultAssetPlugin().resolveAsset(path)` - Resolves an asset path using the default asset plugin
- `AssetAPI.SetDefaultAssetPlugin(plugin)` - Sets the default asset plugin

## Node Operations

### Getting Node Information
```python
# Get all nodes in the scene
all_nodes = NodegraphAPI.GetAllNodes()

# Get a specific node by name
node = NodegraphAPI.GetNode("MyNodeName")

# Get node type
node_type = node.getType()

# Get node name
node_name = node.getName()
```

### Working with Render Nodes
```python
# Find all render nodes
render_nodes = []
for node in NodegraphAPI.GetAllNodes():
    if node.getType() == 'Render':
        render_nodes.append(node)

# Get render node name for submission
for node in render_nodes:
    render_node_name = node.getName()
    print(f"Found render node: {render_node_name}")
```

### Parameter Operations
```python
# Get root parameter group
root_params = node.getParameters()

# Get child parameter by name
child_param = root_params.getChildByName("parameter_name")

# Get parameter value
param_value = param.getValue(0)  # 0 is the frame number

# Set parameter value
param.setValue("new_value", 0)  # 0 is the frame number
```

### Working with Node Parameters
```python
# Get all parameters for a node
params = node.getParameters()

# Get a specific parameter
param = params.getChildByName("param_name")

# Get parameter value
value = param.getValue(0)

# Set parameter value
param.setValue("new_value", 0)
```

## File I/O Operations

### Loading and Saving Katana Files
```python
# Load a Katana file
KatanaFile.Load("filename.katana")

# Save a Katana file
KatanaFile.Save("output_filename.katana")
```

## Scene Analysis Operations

### Extracting Scene Information
```python
# Get all nodes for analysis
nodes = NodegraphAPI.GetAllNodes()

# Process each node for dependencies
for node in nodes:
    node_type = node.getType()
    if node_type == "Render":
        # Process render node dependencies
        pass
```

### Extracting Render Node Information
```python
# Extract render node names for submission
render_node_names = []
for node in NodegraphAPI.GetAllNodes():
    if node.getType() == 'Render':
        render_node_names.append(node.getName())
```

## Render Node Processing
```python
# Extract render node information for submission
render_nodes = []
for node in NodegraphAPI.GetAllNodes():
    if node.getType() == 'Render':
        render_nodes.append(node.getName())
        print(f"Found render node: {node.getName()}")
```

## Render Farm Submission Requirements

### Required Information for Submission
1. **Render Node Name** - The specific render node to use for rendering
2. **AOVs** - Available render passes from the render node
3. **Render Settings** - Resolution, frame range, renderer type
4. **Asset Dependencies** - All file paths required for rendering

### Example web_ui_data.json Structure
```json
{
  "aovs": [
    {"name": "RGBA", "type": 6},
    {"name": "Z", "type": 4}
  ],
  "assets": [
    {
      "metadata": {"node_type": "file"},
      "node": "TextureNode",
      "source": "/path/to/texture.tx",
      "target": "assets/file/hash/texture.tx"
    }
  ],
  "render_settings": {
    "renderer": "arnold",
    "resolution_width": 1920,
    "resolution_height": 1080,
    "frame_start": 1,
    "frame_end": 100,
    "frame_step": 1
  },
  "render_nodes": ["RenderNode1", "RenderNode2"]
}
```

## Additional Resources
- [Katana Documentation](https://learn.foundry.com/katana/Content/)