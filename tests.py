import pickle
from process_planner import ProcessGraph
from data_defs import ItemNode

def singlerequests(verbose):
    '''
    Tests the base network calculation with single item requests with quantity 1
    Checks if all node requests have been filled
    And checks the correctness of the production process by checking the raw material requirements against known amounts
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

    if verbose:
        print("TEST: single item request")

    # Load item data
    with open('asset_data.pickle', 'rb') as infile:
        asset_data = pickle.load(infile)

    # Initialise graph
    planner = ProcessGraph(asset_data)

    all_pass = True

    for item in test_items:
        item_name = item['name']

        if verbose:
            print(f"Item: {item_name}")

        
        planner.add_request(item_name,1)

        # Check if all is filled
        fill_test = True
        for node_key in planner.graph_nodes:
            node = planner.graph_nodes[node_key]
            if isinstance(node, ItemNode):
                if node.rate_requested > node.rate_filled:
                    if verbose:
                        print(f"{node.name} unfilled")
                    fill_test = False

        if verbose:
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
                if verbose:
                    print(f"Incorrect amount of {raw_material}")
                raw_check = False

        if verbose:
            if raw_check:
                print('Raw materials test PASSED: all raw material requirements correct')
            else:
                print('Raw materials test FAILED')

        all_pass = all_pass and raw_check

        planner.reset_graph()

    if all_pass:
        if verbose:
            print('ALL TESTS PASSED')
            print()
        else:
            print('[singlerequests] test PASSED')
        return True
    else:
        print('[singlerequests] test FAILED')
        return False


def matsutilisation(verbose):
    '''
    Tests the raw material utilisation capability against a known ratio
    Known ratio not fully validated
    - is mathematically sound
    - seems to results in a balanced production ingame but not completely confirmed
    '''
    available_materials = {
        'iron_ore': 720,
        'copper_ore': 240,
        'coal': 480,
        'limestone': 240
    }
    request_ratios = {
        'motor': 1,
        'encased_industrial_beam': 2,
        'steel_pipe': 10,
        'copper_sheet': 10
    }
    actual_production = {
        'motor': 8,
        'encased_industrial_beam': 16,
        'steel_pipe': 80,
        'copper_sheet': 80
    }
    required_materials = {
        'iron_ore': 628,
        'copper_ore': 224,
        'coal': 448,
        'limestone': 240
    }

    if verbose:
        print("TEST: available materials utilisation")

    # Load item data
    with open('asset_data.pickle', 'rb') as infile:
        asset_data = pickle.load(infile)

    # Initialise graph
    planner = ProcessGraph(asset_data)

    test_pass = True

    planner.mats_utilisation(available_materials, request_ratios)

    for item, amount in actual_production.items():
        if not round(planner.graph_nodes[f"{item}_OUT"].rate_filled,1) == amount or not round(planner.graph_nodes[f"{item}_OUT"].rate_requested,1) == amount:
            if verbose:
                print(f"Incorrect amount produced of {item}")
            test_pass = False

    if verbose and test_pass:
        print("Requested items production amounts correct")

    for item, amount in required_materials.items():
        if not round(planner.graph_nodes[item].rate_filled,1) == amount or not round(planner.graph_nodes[item].rate_requested,1) == amount:
            if verbose:
                print(f"Incorrect amount of {item} requred")
                print(planner.graph_nodes[item])
            test_pass = False

    if verbose and test_pass:
        print("Calculated raw material requirements correct")

    if test_pass:
        if verbose:
            print('ALL TESTS PASSED')
            print()
        # else:
        #     print('[matutilisation] test PASSED')
        return True
    else:
        print('[matutilisation] test FAILED')
        return False


def doall(verbose):
    singlerequests(verbose)
    matsutilisation(verbose)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', action='store_true', help='Show detailed info of test progres')

    args = parser.parse_args()
    
    doall(args.v)
