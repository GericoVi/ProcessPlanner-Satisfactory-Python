import dash
from dash.dependencies import Output, Input, State, ALL
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
    # For storing this session's data in the browser - don't store as globals so multiple instances can run
    dcc.Store(id='memory', data={'requested_items':{}}),

    html.H1("Production Planner"),
    
    # Item inputs 
    html.Div(["Item request: ",
        dcc.Input(id='item_input', type='text', style= {'width': '20%'}),
        html.Button(id='submit', type='submit', children='submit')
    ]),

    # Results
    html.Div(children= [
        # Raw materials needed for requested items and production rates
        html.Div(
            style= {'display': 'inline-block', 'verticalAlign': 'top'}, 
            children= [
                html.H3("Raw materials required per min (steady state)"),
                html.Div(
                    id= 'raw_materials'
                )
            ],
        ),

        # Graph of production process
        cyto.Cytoscape(
            id='process_network',
            elements=[],
            layout={'name': 'dagre'},
            style={'width': '70%', 'height': '2000px', 'display': 'inline-block'},
            stylesheet=[
                {
                    'selector': 'edge',
                    'style': {
                        'label': 'data(weight)',
                        'line-color': '#ccc',
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
        )
    ]
    )
])

@app.callback(
    Output(component_id='process_network', component_property='elements'),                  # For updating the graph
    Output(component_id='raw_materials', component_property='children'),                    # For updating the list of raw materials needed
    Output(component_id='memory', component_property='data'),                               # For updating the session's data storage
    Output(component_id='item_input', component_property='value'),                          # For clearing the input form after it's submitted
    Input(component_id='submit', component_property='n_clicks'),                            # Triggers this callback when button is pressed
    Input(component_id={'type': 'item_amount', 'index': ALL}, component_property='id'),     # Input form id, for matching with value
    Input(component_id={'type': 'item_amount', 'index': ALL}, component_property='value'),  # Amount of requested item
    State(component_id='item_input', component_property='value'),                           # Get what the user typed and potentially add it to data storage
    State(component_id='memory', component_property='data'),                                # Current state of the data storage
)
def add_item(n_clicks, input_ids, item_amounts, item_name, memory):
    elements = []
    mats = []

    # Check if the amounts were changed
    for i, amount in enumerate(item_amounts):
        if memory['requested_items'][input_ids[i]['index']] != amount:
            memory['requested_items'][input_ids[i]['index']] = amount

        # If it's been changed to 0, remove
        if amount == 0:
            del memory['requested_items'][input_ids[i]['index']]


    with open('asset_data.pickle', 'rb') as infile:
        asset_data = pickle.load(infile)

    # If valid item, add to storage
    if item_name is not None:
        item_name = item_name.replace(' ','_').lower()
        if item_name in asset_data:
            try:
                memory['requested_items'][item_name] += 1
            except KeyError:
                memory['requested_items'][item_name] = 1


    if len(memory['requested_items']) > 0:
        for item, amount in memory['requested_items'].items():

            planner = ProcessGraph(asset_data)

            planner.add_request(item, amount)

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
            mats.append(html.P(children= [
                dcc.Input(
                    id={
                        'type': 'item_amount',
                        'index': item
                    }, 
                    type= 'number',
                    value= amount, 
                    style= {'width': '50px'}
                    ), 
                html.Strong(f"   {' '.join(item.split('_'))} needs:")
                ] 
                ))
            for root in planner.root_nodes:
                root_node = planner.graph_nodes[root]
                mats.append(html.P(f"{round(root_node.rate_produced,1)} {' '.join(root_node.primary_item.split('_'))} per min"))
            mats.append(html.Br())

    return elements, mats, memory, ''


if __name__ == '__main__':
    app.run_server(debug=True)