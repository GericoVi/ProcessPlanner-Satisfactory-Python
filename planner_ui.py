import dash
from dash.dependencies import Output, Input
import dash_core_components as dcc
import dash_html_components as html
import dash_cytoscape as cyto
import pickle
from process_planner import ProcessGraph
from data_defs import ItemNode, BuildingNode


# Initialise dash app and extra layouts for graphs
app = dash.Dash(__name__)
cyto.load_extra_layouts()

# Initialise layout of web app
app.layout = html.Div([
    html.H1("Process Network"),
    html.Div(["Item: ",
        dcc.Input(id='item_input', value='smart_plating', type='text')
    ]),
    cyto.Cytoscape(
        id='process_network',
        elements=[],
        layout={'name': 'breadthfirst'},
        style={'width': '1500px', 'height': '1000px'},
        stylesheet=[
            {
                'selector': 'edge',
                'style': {
                    'label': 'data(weight)'
                }
            },
            {
                'selector': 'node',
                'style': {
                    'label': 'data(label)'
                }
            }
        ]
    )
])

@app.callback(
    Output(component_id='process_network', component_property='elements'),
    Output(component_id='process_network', component_property='layout'),
    Input(component_id='item_input', component_property='value')
)
def update_graph(item_name):
    elements = []
    layout = {
        'name': 'breadthfirst',
        'roots': []
    }

    if len(item_name) > 0:
        # Load data and initialise planner
        with open('asset_data.pickle', 'rb') as infile:
            asset_data = pickle.load(infile)

        # Check if valid item
        if item_name in asset_data:

            planner = ProcessGraph(asset_data)

            planner.add_request(item_name, 1)

            layout['roots'] = [node for node in planner.root_nodes]

            # Get nodes in graph
            for node_name in planner.graph_nodes:
                node = planner.graph_nodes[node_name]
                if isinstance(node,ItemNode):
                    label = f"{round(node.rate_filled,1)}/{round(node.rate_requested,1)} {node.name} per min"
                elif isinstance(node,BuildingNode):
                    label = f"{node.name} ({round(node.clock_speed*100,1)}%)"

                elements.append({'data' : {
                    'id'    : node_name,
                    'label' : label
                }})

            # Get connecting edges
            for edge in planner.graph_edges:
                elements.append({'data' : {
                    'source'    : edge.source_id,
                    'target'    : edge.target_id,
                    'weight'    : round(edge.rate,1)
                }})

    return elements, layout


if __name__ == '__main__':
    app.run_server(debug=True)