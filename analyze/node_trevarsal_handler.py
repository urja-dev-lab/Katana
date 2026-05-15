

# Get upstream/input nodes
def get_input_nodes(node):

    nodes = []

    for port in node.getInputPorts():

        for connected_port in port.getConnectedPorts():

            nodes.append(connected_port.getNode())

    return nodes

# Get downstream/output nodes
def get_output_nodes(node):

    nodes = []

    for port in node.getOutputPorts():

        for connected_port in port.getConnectedPorts():

            nodes.append(connected_port.getNode())

    return nodes