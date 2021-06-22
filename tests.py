import pickle
from process_planner import ProcessGraph
from data_defs import ItemNode

'''
Items to test
'''
test_items = [{
    'name': 'smart_plating',
    'raw_mats': {
        'iron_ore': 23.25
    }
},
{
    'name': 'cooling_system',
    'raw_mats': {
        'water': 15.00,
        'nitrogen_gas': 25.00,
        'coal': 5.00,
        'bauxite': 10.00,
        'raw_quartz': 5.00,
        'copper_ore': 15.33,
        'crude_oil': 3.00
    }
},
{
    'name': 'turbo_motor',
    'raw_mats': {
        'water': 108.00,
        'nitrogen_gas': 100.00,
        'coal': 80.00,
        'bauxite': 88.00,
        'raw_quartz': 74.00,
        'copper_ore': 156.33,
        'crude_oil': 135.00,
        'iron_ore': 169.00
    }
}]

# Load item data
with open('asset_data.pickle', 'rb') as infile:
    asset_data = pickle.load(infile)

# Initialise graph
planner = ProcessGraph(asset_data)

all_pass = True

for item in test_items:
    item_name = item['name']
    print(f"TEST: {item_name}")

    
    planner.add_request(item_name,1)

    # Check if all is filled
    fill_test = True
    for node_key in planner.graph_nodes:
        node = planner.graph_nodes[node_key]
        if isinstance(node, ItemNode):
            if node.rate_requested > node.rate_filled:
                print(f"{node.name} unfilled")
                fill_test = False
    if fill_test:
        print('Fill test PASSED: all nodes requests met')
    else:
        print('Fill test FAILED')

    all_pass = all_pass and fill_test

    # Check if raw material requirements are correct
    raw_check = True
    for root in planner.root_nodes:
        root_node = planner.graph_nodes[root]
        raw_material = root_node.primary_item
        if not item['raw_mats'][raw_material] == round(root_node.rate_produced,2):
            print(f"Incorrect amount of {raw_material}")
            raw_check = False
    if raw_check:
        print('Raw materials test PASSED: all raw material requirements correct')
    else:
        print('Raw materials test FAILED')

    all_pass = all_pass and raw_check

    planner.reset_graph()
    print()

if all_pass:
    print('ALL TESTS PASSED')
