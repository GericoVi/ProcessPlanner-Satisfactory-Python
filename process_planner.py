from data_defs import Recipe, ItemNode, BuildingNode, GraphEdge

class ProcessGraph:
    '''
    Computes a network graph of the balanced production layout to produce the requested items at a given rate
    '''

    def __init__(self, asset_data: dict):
        self.assets = asset_data

        self.graph_nodes        = {}    
        self.graph_edges        = []
        self.root_nodes         = []    # Keep track of root nodes for laying out graph later


    def reset_graph(self):
        '''
        Remove all nodes and edges from graph, and reset the other variables
        Utility function - if we need to remove a requested item, just recalculate the graph, doesn't take long anyway
        Not currently used, most of the time the class instance is just recreated
        '''
        self.graph_nodes        = {}   
        self.graph_edges        = []
        self.root_nodes         = []   
        

    def add_request(self, requested_item: str, requested_amount: int):
        '''
        Starts the process of adding a network to the graph to represent the production process of the requested item
        Propagating back from the item to basic items (i.e. ores, etc.)
        '''
        node_name = f"{requested_item}_OUT"

        # Add to graph
        self.graph_nodes[node_name] = ItemNode(name= requested_item, rate_requested= requested_amount)

        # Fill request by propagating the node
        self.fill_item_request(node_name)


    def fill_item_request(self, item_node_name: str):
        '''
        Edits the graph to fulfil the requested amount of the given item
        '''
        # Get item recipe
        recipes = self.assets[ self.graph_nodes[item_node_name].name ].recipes

        # Just use the standard recipe for now
        if len(recipes) > 0:
            recipe = recipes[0]
        else:
            raise Exception(f'No recipe for {self.graph_nodes[item_node_name].name}')

        # First check if there are unused resources (byproducts or buildings) in the graph we can use
        self.use_resources(item_node_name)

        if self.graph_nodes[item_node_name].rate_needed() > 0:
            # Update the graph to add the ingredients and byproducts of this recipe
            self.build_recipe(recipe, item_node_name)


    def use_resources(self, requesting_node: str):
        '''
        Checks if nodes currently on the graph can be used to fill the request
        '''
        def use_node(node_name: str):
            # If this item is being made 'on-purpose', we can safely increase its production to meet the request
            if self.graph_nodes[node_name].primary:
                rate_increment = self.graph_nodes[requesting_node].rate_needed()
            
            # If it's only a byproduct, only use the unused amount so not to disturb the upstream process
            else:
                rate_increment = self.graph_nodes[node_name].rate_unused()

            if rate_increment > 0:
                # Update nodes
                self.graph_nodes[requesting_node].rate_filled += rate_increment
                self.graph_nodes[node_name].rate_requested += rate_increment
                self.propagate_node_update(node_name)

                # Add edge
                self.graph_edges.append(GraphEdge(
                    source_id= node_name,
                    target_id= requesting_node,
                    item_name= node_name,
                    rate=      rate_increment
                ))

        # Are we filling an item node - i.e. a user request
        if isinstance(self.graph_nodes[requesting_node], ItemNode):
            item_name = requesting_node.replace('_OUT', '')

            # Is this item already on the graph?
            if item_name in self.graph_nodes:
                use_node(item_name)

        # Are we filling a building node = attempy to fill the recipe's ingredient requirements with existing nodes
        elif isinstance(self.graph_nodes[requesting_node], BuildingNode):
            for ingredient in self.graph_nodes[requesting_node].recipe.ingredients:
                if ingredient.name in self.graph_nodes:
                    use_node(ingredient.name)


    def propagate_node_update(self, node_name: str):
        '''
        Propagates the new resource usage of a node to upstream nodes
        Uses the graph edges to find the immediate upstream nodes from this one and updates their requirements
        Function is called recursively until no more upstream nodes are found
        '''

        if isinstance(self.graph_nodes[node_name], ItemNode):
            # Find this node's upstream builder, if it has one
            '''
            TO DO: Store connection information in the nodes? So that we don't need to loop the list of edges
            But then will need some post processing after network calculation to be able to visualise
            Since Dash cytoscape needs edges as input
            '''
            for i,edge in enumerate(self.graph_edges):
                if edge.target_id == self.graph_nodes[node_name]:
                    builder_node = edge.source_id

                    # Only propagate the update upstream if the item node is a 'primary' product - so existing upstream processes don't mess up
                    if self.graph_nodes[i].primary_item == node_name:

                        # Update rate filled of node - since we'll increase upstream production
                        rate_increment = self.graph_nodes[node_name].rate_requested - self.graph_nodes[node_name].rate_filled
                        self.graph_nodes[node_name].rate_filled += rate_increment

                        # Update upstream builder
                        self.graph_nodes[builder_node].rate_produced += rate_increment

                        # Update edge
                        self.graph_edges[i].rate += rate_increment

                        self.propagate_node_update(builder_node)

                        break

        elif isinstance(self.graph_nodes[node_name], BuildingNode):
            recipe = self.graph_nodes[node_name].recipe

            # Get clock speed increment
            old_speed = self.graph_nodes[node_name].clock_speed
            self.graph_nodes[node_name].update_clockspeed()
            clock_increment = self.graph_nodes[node_name].clock_speed - old_speed

            # Find upstream nodes by travelling along edges
            for i,edge in enumerate(self.graph_edges):
                # Update ingredient nodess
                if edge.target_id == self.graph_nodes[node_name].node_id:
                    ingredient_node = edge.source_id

                    # Get recipe requirements for this item
                    idx_in_recipe = recipe.ingredients_names.index( self.graph_nodes[ingredient_node].name )

                    # Required increment - can be negative in case of decrement (unlikely)
                    rate_increment = recipe.ingredients[idx_in_recipe].rate * clock_increment
                    
                    self.graph_nodes[ingredient_node].rate_requested += rate_increment

                    # Update edge
                    self.graph_edges[i].rate += rate_increment

                    # Update upstream node - call function recursively
                    self.propagate_node_update(ingredient_node)

                    pass

                # Update byproduct nodes
                elif edge.source_id == self.graph_nodes[node_name].node_id:
                    byproduct_node = edge.target_id

                    if self.graph_nodes[byproduct_node].name != self.graph_nodes[node_name].primary_item:
                        idx_in_recipe = recipe.products_names.index( self.graph_nodes[byproduct_node].name )
                        rate_increment = recipe.products[idx_in_recipe].rate * clock_increment
                        self.graph_nodes[byproduct_node].rate_filled += rate_increment

                        # Update edge
                        self.graph_edges[i].rate += rate_increment

                        ''' 
                        TO DO: Needs a trickier update for this, in case this byproduct node is being used in another process
                        Let's say item A is produced as a byproduct by building A at 1 item/min but building B needs item A at 3 items/min
                        Then another building, building C, needs to produce item A as a 'primary' item at 2 items/min
                        If building A is subsequently updated such that it is now making 2 of item A per min, building C then needs to be updated to produce less of item A (1 item/min)

                        Leave it for now - may result in excess production for complex processes
                        '''


    def build_recipe(self, recipe: Recipe, item_node_name: str):
        '''
        Adds a building node using a given recipe to fill an item node, 
        and adds byproducts and ingredients to the graph
        '''
        # Get production rate of 'primary' item with 100% clock speed
        idx = recipe.products_names.index( self.graph_nodes[item_node_name].name )
        default_rate = recipe.products[idx].rate

        # Add a building node to fill the requested rate
        building_node_name = f"{recipe.building_name}:{item_node_name}"
        self.graph_nodes[building_node_name] = BuildingNode(
            name=                       recipe.building_name,
            recipe=                     recipe,
            primary_item=               self.graph_nodes[item_node_name].name,
            production_rate_default=    default_rate,
            rate_produced=              self.graph_nodes[item_node_name].rate_needed()
        )

        # Update item node
        self.graph_nodes[item_node_name].rate_filled += self.graph_nodes[building_node_name].rate_produced

        # Add edge between new building and requested item
        self.graph_edges.append(GraphEdge(
            source_id   = building_node_name,
            target_id   = item_node_name,
            item_name   = self.graph_nodes[item_node_name].name,
            rate        = self.graph_nodes[building_node_name].rate_produced
        ))

        # Add byproducts of recipe to the graph if there are any
        for product in recipe.products:
            if product.name != self.graph_nodes[item_node_name].name:
                rate_produced = product.rate * self.graph_nodes[building_node_name].clock_speed

                # Check if this item is already on the graph and add to this node instead
                if product.name in self.graph_nodes:
                    self.graph_nodes[product.name].rate_filled += rate_produced
                    '''
                    TO DO: Propagate a graph update?
                    Similar to the planned update for the byproduct nodes discussed before
                    '''

                else:
                    self.graph_nodes[product.name] = ItemNode(name= product.name, rate_filled= rate_produced)

                # Add edge between building and byproduct node
                self.graph_edges.append(GraphEdge(
                    source_id   = building_node_name,
                    target_id   = product.name,
                    item_name   = product.name,
                    rate        = rate_produced
                ))

        # Add recipe ingredients to the graph if there are any
        for ingredient in recipe.ingredients:
            rate_required = ingredient.rate * self.graph_nodes[building_node_name].clock_speed

            # Check if this item is already on the graph, if so add to it and propagate update upstream
            if ingredient.name in self.graph_nodes:
                self.graph_nodes[ingredient.name].rate_requested += rate_required

                # Propagate update upstream
                self.propagate_node_update(ingredient.name)
            else:
                self.graph_nodes[ingredient.name] = ItemNode(name= ingredient.name, rate_requested= rate_required)
                
                # Fill item node request
                self.fill_item_request(ingredient.name)

            # Add edge between ingredient and building
            self.graph_edges.append(GraphEdge(
                source_id   = ingredient.name,
                target_id   = building_node_name,
                item_name   = ingredient.name,
                rate        = rate_required
            ))

        if len(recipe.ingredients) == 0:
            # If there's no ingredients, this is an extractor/miner building
            self.root_nodes.append(building_node_name)

    
if __name__ == '__main__':
    import time
    import pickle

    # Read in recipes in pickle file
    with open('asset_data.pickle', 'rb') as outfile:
        asset_data = pickle.load(outfile)

    # Test process
    start = time.time()
    planner = ProcessGraph(asset_data)
    print(f"Setup time: {time.time()-start}")

    start = time.time()
    planner.add_request('turbo_motor', 1)
    print(f"Process planning time: {time.time()-start}")

    # For confirming that it worked
    print('\nTurbo motor needs:')
    for root in planner.root_nodes:
        root_node = planner.graph_nodes[root]
        print(f"{round(root_node.rate_produced,1)} {root_node.primary_item} per min")