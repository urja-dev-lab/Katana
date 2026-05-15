from Katana import NodegraphAPI
import json


def get_detailed_attributes(node):
    """
    Get detailed attributes for a given node.
    """
    visited = set()
    return node_to_dict(visited, node)


def node_to_dict(visited, node):
    """
    Convert a Katana node and all referenced nodes into dictionaries.
    """

    if not node:
        return None

    node_name = node.getName()

    # Prevent infinite recursion
    if node_name in visited:
        return {"_ref": node_name}

    visited.add(node_name)

    data = {}

    def recurse(param):
        children = param.getChildren()

        # ----------------------------------------
        # GROUP PARAM
        # ----------------------------------------
        if children:
            group_data = {}

            for child in children:
                group_data[child.getName()] = recurse(child)

            return group_data

        # ----------------------------------------
        # LEAF PARAM
        # ----------------------------------------
        try:
            value = param.getValue(0)
        except:
            value = None

        # ----------------------------------------
        # If value references another node
        # ----------------------------------------
        if isinstance(value, str):

            ref_node = NodegraphAPI.GetNode(value)

            if ref_node:
                return {
                    "_node_ref": value,
                    "_node_data": node_to_dict(visited, ref_node)
                }

        return value

    data[node_name] = recurse(node.getParameters())

    return data


# ----------------------------------------
# START NODE
# ----------------------------------------

# node = NodegraphAPI.GetNode("Assets_Double_Decker_Bus")

# result = get_detailed_attributes(node)

# # Pretty print
# print(json.dumps(result, indent=4))