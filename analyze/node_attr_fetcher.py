from Katana import NodegraphAPI

def node_attr_fetch(node_name):
    node = NodegraphAPI.GetNode(node_name)
    return param_to_dict(node.getParameters())


def param_to_dict(param):
    """
    Recursively convert Katana parameters into a dictionary.
    """

    children = param.getChildren()

    # ----------------------------------------
    # GROUP PARAM
    # ----------------------------------------
    if children:
        data = {}

        for child in children:
            data[child.getName()] = param_to_dict(child)

        return data

    # ----------------------------------------
    # LEAF PARAM
    # ----------------------------------------
    try:
        return param.getValue(0)
    except:
        return None


# # Get node
# node = NodegraphAPI.GetNode("Assets_Double_Decker_Bus")

# # Convert parameters to dictionary
# params_dict = param_to_dict(node.getParameters())

# Print result
# print(params_dict)