import dash
from dash.dependencies import Output, Input, State, ALL
import dash_core_components as dcc
import dash_html_components as html
import dash_cytoscape as cyto
import pickle
from process_planner import ProcessGraph
from data_defs import ItemNode, BuildingNode
import numpy as np

# Initialise dash app and extra layouts for graphs
app = dash.Dash(__name__)
cyto.load_extra_layouts()

app.layout = html.Div([
    # For storing this session's data in the browser - don't store as globals so multiple instances can run
    dcc.Store(id='memory', data={'raw_materials':{}, 'requested_items':{}}),

    html.H1("Materials Utilisation Planner"),

    # Inputs
    html.Table([
        # Raw material inputs
        html.Tr([
            html.Td('Raw material:', style= {'width': '150px'}),
            html.Td([
                dcc.Input(id='raw_input', type='text'),
                html.Button(id='raw_add', type='submit', children='add')
            ], style= {'width': '450px'})
        ]),

        html.Tr('', style={'height':'10px'}),

        # Requested item ratios
        html.Tr([
            html.Td('Item request:', style= {'width': '150px'}),
            html.Td([
                dcc.Input(id='request_input', type='text'),
                html.Button(id='request_add', type='submit', children='add')
            ], style= {'width': '450px'})
        ]),

    ], style= {'width': '600px'}),

    # Results
    html.Div(children= [
        # Changeable inputs
        html.Div(
            style= {'display': 'inline-block', 'verticalAlign': 'top'}, 
            children= [
                html.Div('', style={'height':'20px'}),
                html.Button(id='submit', type='submit', children='submit', style={'width':'100px', 'height':'30px'}),
                html.Div(
                    id= 'raw_materials'
                ),
                html.Div('', style={'height':'10px'}),
                html.Div(
                    id= 'requested_items'
                ),
                html.Div('', style={'height':'10px'}),
                html.H3(id='calc-msg', style={'color':'red'})
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
    ])
])

@app.callback(
    Output('memory', 'data'),                                   # For updating the session's memory
    Output('raw_materials', 'children'),                        # For updating the list of raw materials on screen
    Output('requested_items', 'children'),                      # For updating the list of item requests on screen
    Output('raw_input', 'value'),                               # For clearing the input form
    Output('request_input', 'value'),                           # For clearing the input form
    Input('raw_add', 'n_clicks'),                               # Raw materials add button trigger
    Input('request_add', 'n_clicks'),                           # Item request add button trigger
    Input({'type': 'raw_materials', 'index': ALL}, 'id'),       # Input for id for matching with value
    Input({'type': 'raw_materials', 'index': ALL}, 'value'),    # Amount of raw material in added form
    Input({'type': 'requested_items', 'index': ALL}, 'id'),     # Input for id for matching with value
    Input({'type': 'requested_items', 'index': ALL}, 'value'),  # Amount of raw material in added form
    State('raw_input', 'value'),                                # Text within the form
    State('request_input', 'value'),                            # Text within the form
    State('memory', 'data')                                     # Session memory
)
def manage_inputs(raw_clicks, request_clicks, raw_ids, raw_amounts, request_ids, request_amounts, raw_name, request_name, memory):
    # Check if the amounts were changed
    ids = [raw_ids, request_ids]
    keys = ['raw_materials', 'requested_items']
    for i,amounts in enumerate([raw_amounts, request_amounts]):
        for j, amount in enumerate(amounts):
            if amount is None:
                amount = 0
            
            if memory[keys[i]][ids[i][j]['index']] != amount:
                memory[keys[i]][ids[i][j]['index']] = amount

            # If it's been changed to 0, remove
            if amount == 0:
                del memory[keys[i]][ids[i][j]['index']]

    with open('asset_data.pickle', 'rb') as infile:
        asset_data = pickle.load(infile)

    # If valid item, add to storage
    for i,name in enumerate([raw_name, request_name]):
        if name is not None:
            item_name = name.replace(' ','_').lower()
            if item_name in asset_data:
                try:
                    memory[keys[i]][item_name] += 1
                except KeyError:
                    memory[keys[i]][item_name] = 1

    # Show the inputs so far on the screen, with forms so it can be edited
    data = [[html.P(html.Strong('Available raw material amounts:'))],[html.P(html.Strong('Desired item output ratio:'))]]
    for i,key in enumerate(keys):
        for k, val in memory[key].items():
            data[i].append(html.P([
                dcc.Input(
                    id= {'type': f"{key}", 'index': k},
                    type= 'number',
                    value= val,
                    style= {'width': '50px'}
                ),
                f"     {' '.join(k.split('_'))}"
            ]))

    return memory, data[0], data[1], '', ''


@app.callback(
    Output('process_network', 'elements'),      # For showing the caluclated production process network
    Output('calc-msg', 'children'),             # To show messages after calculation - ie missing materials error
    Input('submit', 'n_clicks'),                # Button which triggers the callback and starts the calculation
    State('memory', 'data')                     # Session memory
)
def calculate_production(n_clicks, memory):
    elements = []

    if len(memory['requested_items']) == 0:
        return elements, ''

    # Load data into planner
    with open('asset_data.pickle', 'rb') as infile:
        asset_data = pickle.load(infile)
    planner = ProcessGraph(asset_data)

    request_items = []
    request_ratio = np.array([])
    for key, val in memory['requested_items'].items():
        # Do a preliminary calculation of raw material requirements
        planner.add_request(key, val)

        # Extract into lists for easier manipulation later
        request_items.append(key)
        request_ratio = np.append(request_ratio, val)

    # Extract raw material requirements into lists/numpy arrays
    raw_mats = []
    raw_required = np.array([])
    raw_actual = np.array([])
    for root in planner.root_nodes:
        root_node = planner.graph_nodes[root]
        raw_mats.append(root_node.primary_item)
        raw_required = np.append(raw_required, root_node.rate_produced)

        # And check if all raw materials are present at all
        if root_node.primary_item in memory['raw_materials']:
            raw_actual = np.append(raw_actual, memory['raw_materials'][root_node.primary_item] )
        else:
            return elements, f"Missing raw material: {' '.join(root_node.primary_item.split('_'))}"

    # Get constraining material and get actual amounts we can produce
    raw_availability = raw_actual / raw_required
    constraint = np.argmin( raw_availability )
    
    actual_production = (request_ratio/raw_required[constraint]) * raw_actual[constraint]

    # Calculate network again with new ratio
    planner.reset_graph()
    for i,item in enumerate(request_items):
        planner.add_request(item, actual_production[i])

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

    return elements, ''

if __name__ == '__main__':
    app.run_server(debug=True, port=8050)