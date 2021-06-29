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
        dcc.Input(id='item_inputs', value='smart plating, versatile framework, automated wiring', type='text')
    ]),
    cyto.Cytoscape(
        id='process_network',
        elements=[],
        layout={'name': 'dagre'},
        style={'width': '1500px', 'height': '2000px'},
        stylesheet=[
            {
                'selector': 'edge',
                'style': {
                    'label': 'data(weight)',
                    'line-color': '#ccc',
                    'mid-target-arrow-color': 'red',
                    'mid-target-arrow-shape': 'triangle',
                    'arrow-scale': 0.8,
                    'font-size': '8px'
                }
            },
            {
                'selector': 'node',
                'style': {
                    'label': 'data(label)',
                    'width': 30,
                    'height': 30,
                    'background-fit': 'cover',
                    'background-image': 'data(image)',
                    'font-size': '8px'
                }
            }
        ]
    ),
    html.H2("Raw materials required per min (at steady state)"),
    html.Div(id='raw_materials')
])

@app.callback(
    Output(component_id='process_network', component_property='elements'),
    Output(component_id='process_network', component_property='layout'),
    Output(component_id='raw_materials', component_property='children'),
    Input(component_id='item_inputs', component_property='value')
)
def update_graph(item_names):
    elements = []
    layout = {
        'name': 'dagre'
    }
    mats = []

    if len(item_names) > 0:
        # Load item data
        with open('asset_data.pickle', 'rb') as infile:
            asset_data = pickle.load(infile)

        planner = ProcessGraph(asset_data)

        # Split up item requests
        names = []
        for item in item_names.split(', '):
            names += item.split(',')

        for item_name in names:
            item_name = item_name.replace(' ','_').lower()
            
            # Check if valid item
            if item_name in asset_data:

                planner.add_request(item_name, 1)

                # Get nodes in graph
                for node_name in planner.graph_nodes:
                    node = planner.graph_nodes[node_name]
                    if isinstance(node,ItemNode):
                        label = f"{round(node.rate_filled,1)} {' '.join(node.name.split('_'))} per min"
                    elif isinstance(node,BuildingNode):
                        label = f"{node.name} ({round(node.clock_speed*100,1)}%)"

                    asset_name = node_name.replace('_OUT', '').split(':')[0]
                    if asset_name == 'resource_well_extractor':
                        asset_name = 'resource_well_pressurizer'

                    elements.append({'data' : {
                        'id'    : node_name,
                        'label' : label,
                        'image' : asset_data[asset_name].image_url
                    }})

                # Get connecting edges
                for edge in planner.graph_edges:
                    elements.append({'data' : {
                        'source'    : edge.source_id,
                        'target'    : edge.target_id,
                        'weight'    : round(edge.rate,1)
                    }})

                # Get raw materials
                mats.append(html.P(f'\n{item_name} needs:'))
                for root in planner.root_nodes:
                    root_node = planner.graph_nodes[root]
                    mats.append(html.P(f"{round(root_node.rate_produced,1)} {root_node.primary_item} per min"))

    return elements, layout, mats


if __name__ == '__main__':
    app.run_server(debug=True)