import pickle
from data_defs import Recipe, ItemNode, BuildingNode, GraphEdge

class ProcessGraph:
    '''
    Computes a network graph of the balanced production layout to produce the requested items at a given rate
    '''

    def __init__(self, asset_data: dict):
        self.assets = asset_data

        self.node_id_iterator   = 0
        self.graph_nodes        = []
        self.graph_edges        = []
        self.ids_list           = []    # List of just the node ids so that we can easily get a specific node's index within the graph_nodes list
        self.root_idxs          = []    # Keep track of root nodes for laying out graph later


    def reset_graph(self):
        '''
        Remove all nodes and edges from graph, and reset the other variables
        Utility function - if we need to remove a requested item, just recalculate the graph, doesn't take long anyway
        Not currently used, most of the time the class instance is just recreated
        '''
        self.node_id_iterator = 0
        self.graph_nodes        = []
        self.graph_edges        = []
        self.ids_list           = []   
        self.root_idxs          = []   
        

    def add_request(self, requested_item: str, requested_amount: int):
        '''
        Starts the process of adding a network to the graph to represent the production process of the requested item
        Propagating back from the item to basic items (i.e. ores, etc.)
        '''

        # Add to graph
        idx = self.add_item_node(
            item_name       = requested_item, 
            rate_requested  = requested_amount
            )

        # Fill request by propagating the node
        self.fill_node(idx)


    def fill_node(self, current_node_idx: int):
        '''
        Edits the graph to fulfil the requested amount of the given item
        '''
        # Get item recipe
        recipes = self.assets[self.graph_nodes[current_node_idx].name].recipes

        # Just use the standard recipe for now
        if len(recipes) > 0:
            current_recipe = recipes[0]
        else:
            current_recipe = None

        # First check if there are unused resources (byproducts or buildings) in the graph we can use
        self.use_resources(current_node_idx, current_recipe)

        if self.graph_nodes[current_node_idx].rate_needed() > 0:
            if current_recipe is not None:
                # If there is a recipe, add a building node to fill the requested rate
                while self.graph_nodes[current_node_idx].rate_needed() > 0:
                    building_idx = self.add_building_node(
                        recipe          = current_recipe, 
                        item            = self.graph_nodes[current_node_idx].name, 
                        rate_requested  = self.graph_nodes[current_node_idx].rate_needed()
                        )

                    self.graph_nodes[current_node_idx].rate_filled += self.graph_nodes[building_idx].rate_produced

                    # Update the graph to add the ingredients and byproducts of this recipe
                    ingredients_idxs = self.build_recipe(building_idx, current_node_idx)

                    # Call this function recursively to propagate the ingredient nodes
                    for idx in ingredients_idxs:
                        self.fill_node(idx)

            else:
                print(f'No recipe for {self.graph_nodes[current_node_idx].name}')


    def build_recipe(self, building_node_idx: int, item_node_idx: int):
        '''
        Connects the item node and its production building, and adds byproducts and ingredients to the graph
        '''
        recipe = self.graph_nodes[building_node_idx].recipe

        # Make sure the clock speed has been updated
        self.graph_nodes[building_node_idx].update_clockspeed()

        # Add edge between new building and requested item
        self.graph_edges.append(GraphEdge(
            source_id   = self.graph_nodes[building_node_idx].node_id,
            target_id   = self.graph_nodes[item_node_idx].node_id,
            item_name   = self.graph_nodes[item_node_idx].name,
            rate        = self.graph_nodes[building_node_idx].rate_produced
        ))

        # Add byproducts of recipe to the graph if there are any
        for product in recipe.products:
            if product.name != self.graph_nodes[item_node_idx].name:
                rate_produced = product.rate * self.graph_nodes[building_node_idx].clock_speed

                # Check if this item is already on the graph and add to this node
                product_idx = None
                for i,node in enumerate(self.graph_nodes):
                    if isinstance(node, ItemNode) and node.name == product.name:
                        self.graph_nodes[i].rate_filled += rate_produced

                        product_idx = i
                        break

                if product_idx is None:
                    # If not, add new node
                    product_idx = self.add_item_node(
                        item_name   = product.name,
                        rate_filled = rate_produced
                    )

                # Add edge between building and byproduct node
                self.graph_edges.append(GraphEdge(
                    source_id   = self.graph_nodes[building_node_idx].node_id,
                    target_id   = self.graph_nodes[product_idx].node_id,
                    item_name   = self.graph_nodes[product_idx].name,
                    rate        = rate_produced
                ))

        # Add recipe ingredients to the graph as new nodes
        new_ingredients_idxs = []
        for ingredient in recipe.ingredients:
            rate_required = ingredient.rate * self.graph_nodes[building_node_idx].clock_speed

            # Check if this item is already on the graph, if so add to it and propagate update upstream
            ingredient_idx = None
            for i,node in enumerate(self.graph_nodes):
                if isinstance(node, ItemNode) and node.name == ingredient.name:
                    self.graph_nodes[i].rate_requested += rate_required

                    ingredient_idx = i
                    self.propagate_node_update(ingredient_idx)
                    break

            if ingredient_idx is None:
                ingredient_idx = self.add_item_node(
                    item_name       = ingredient.name,
                    rate_requested  = rate_required
                )

                new_ingredients_idxs.append(ingredient_idx)

            # Add edge between ingredient and building
            self.graph_edges.append(GraphEdge(
                source_id   = self.graph_nodes[ingredient_idx].node_id,
                target_id   = self.graph_nodes[building_node_idx].node_id,
                item_name   = self.graph_nodes[ingredient_idx].name,
                rate        = rate_required
            ))

        if len(recipe.ingredients) == 0:
            # If there's noi ingredients, this is an extractor/miner building
            self.root_idxs.append(building_node_idx)

        # Return indexes of new ingredient nodes so we can propagate them
        return new_ingredients_idxs


    def use_resources(self, current_node_idx: int, recipe: Recipe = None):
        '''
        Checks if there are unused resources in the graph which can be used to fill a request
        '''
        debug=False
        if self.graph_nodes[current_node_idx].name == 'iron_rod':
            debug=True
        for i,node in enumerate(self.graph_nodes):
            used = False
            # Any unused by products
            if isinstance(node, ItemNode) and node.name == self.graph_nodes[current_node_idx].name and node.rate_filled > node.rate_requested:
                unused_rate = node.rate_filled - node.rate_requested

                to_use = min(unused_rate, self.graph_nodes[current_node_idx].rate_needed())

                # Update unused byproduct
                self.graph_nodes[i].rate_requested += to_use

                used = True

            # Is there a building that's already producing this item - increase it's clock speed to meet request
            if recipe is not None:
                if isinstance(node, BuildingNode) and node.recipe == recipe:
                    # if debug:
                        # print(self.graph_nodes[current_node_idx].rate_needed())
                    to_use = self.graph_nodes[current_node_idx].rate_needed()

                    # Update building
                    self.graph_nodes[i].rate_produced += to_use
                    self.propagate_node_update(i)

                    used = True

            if used:
                # Update requesting node
                self.graph_nodes[current_node_idx].rate_filled += to_use

                # Add new edge between resource and the node being filled
                self.graph_edges.append(GraphEdge(
                    source_id   = node.node_id,
                    target_id   = self.graph_nodes[current_node_idx].node_id,
                    item_name   = self.graph_nodes[current_node_idx].name,
                    rate        = to_use
                ))
            
            # Stop if we've filled the full request already
            if self.graph_nodes[current_node_idx].rate_needed() <= 0:
                    break


    def propagate_node_update(self, node_idx: int):
        '''
        Propagates the new resource usage of a node to upstream nodes
        Uses the graph edges to find the immediate upstream nodes from this one and updates their requirements
        Function is called recursively until no more upstream nodes are found
        '''

        if isinstance(self.graph_nodes[node_idx], BuildingNode):
            recipe = self.graph_nodes[node_idx].recipe

            # Get clock speed increment
            old_speed = self.graph_nodes[node_idx].clock_speed
            self.graph_nodes[node_idx].update_clockspeed()
            clock_increment = self.graph_nodes[node_idx].clock_speed - old_speed

            # Iterate upstream - edges were added from downstream first
            for i,edge in enumerate(self.graph_edges):

                # Update connected item nodes
                if edge.target_id == self.graph_nodes[node_idx].node_id:
                    upstream_id = edge.source_id
                        
                    # Get index of node in list
                    upstream_node_idx = self.ids_list.index(upstream_id)

                    # Get recipe requirements for this item
                    idx_in_recipe = recipe.ingredients_names.index( self.graph_nodes[upstream_node_idx].name )

                    # Required increment - can be negative in case of decrement (unlikely)
                    rate_increment = recipe.ingredients[idx_in_recipe].rate * clock_increment
                    
                    self.graph_nodes[upstream_node_idx].rate_requested += rate_increment

                    # Update edge
                    self.graph_edges[i].rate += rate_increment

                    # Update upstream node - call function recursively
                    self.propagate_node_update(upstream_node_idx)

                    pass

                # Update byproduct nodes - should not need further propagation
                if edge.source_id == self.graph_nodes[node_idx].node_id:
                    downstream_id = edge.target_id
                    downstram_node_idx = self.ids_list.index(downstream_id)

                    if self.graph_nodes[downstram_node_idx].name != self.graph_nodes[node_idx].primary_item:
                        idx_in_recipe = recipe.products_names.index( self.graph_nodes[downstram_node_idx].name )
                        rate_increment = recipe.products[idx_in_recipe].rate * clock_increment
                        self.graph_nodes[downstram_node_idx].rate_requested += rate_increment

                        # Update edge
                        self.graph_edges[i].rate += rate_increment

        else:
            # Item nodes only need their edges updated
            # Upstream nodes should already be completed, since depth first creation - so rate increment is just the now unfilled amount
            rate_increment = self.graph_nodes[node_idx].rate_requested - self.graph_nodes[node_idx].rate_filled

            self.graph_nodes[node_idx].rate_filled += rate_increment

            # Update upstream builder
            for i,edge in enumerate(self.graph_edges):
                if edge.target_id == self.graph_nodes[node_idx].node_id:
                    upstream_id = edge.source_id
                    upstream_node_idx = self.ids_list.index(upstream_id)

                    self.graph_nodes[upstream_node_idx].rate_produced += rate_increment

                    # Update edge
                    self.graph_edges[i].rate += rate_increment

                    self.propagate_node_update( upstream_node_idx )

                    # Item nodes only have one upstream connection at this stage
                    break


    def pool_products(self, item_name: str, rate_produced: float, source_idx: int):
        '''
        Checks if the given item is already on the graph, and add to that node instead of making a new one
        '''
        for i,node in enumerate(self.graph_nodes):
            if isinstance(node, ItemNode) and node.name == item_name:
                self.graph_nodes[i].rate_filled += rate_produced

                # Add edge
                self.graph_edges.append(GraphEdge(
                    source_id   = self.graph_nodes[source_idx].node_id,
                    target_id   = node.node_id,
                    item_name   = item_name,
                    rate        = rate_produced
                ))

                return i

        return None

    
    def add_item_node(self, item_name: str, rate_requested: float = 0, rate_filled: float = 0):
        '''
        Utility function for adding item nodes to the graph
        '''
        if not (rate_requested == 0 and rate_filled == 0):
            self.graph_nodes.append(ItemNode(
                node_id         = self.node_id_iterator,
                name            = item_name,
                rate_requested  = rate_requested,
                rate_filled     = rate_filled
            ))
            self.ids_list.append(self.node_id_iterator)

            self.node_id_iterator += 1

        # Return the index of the node we just added
        return len(self.graph_nodes) - 1


    def add_building_node(self, recipe: Recipe, item: str, rate_requested: float):
        '''
        Utility function for adding a building node to the graph, given a recipe and the requested output item and rate
        '''
        # Get production rate of item of interest with this building running on 100% clock speed
        idx = recipe.products_names.index(item)

        """ # Can the requested rate be fulfilled without overclocking?
        output_rate = min(recipe.products[idx].rate, rate_requested) """

        # Just create one building node, regardless if it needs overclocked or not (even past 250%) - do splitting later
        output_rate = rate_requested

        self.graph_nodes.append(BuildingNode(
            node_id                 = self.node_id_iterator,
            name                    = recipe.building_name,
            recipe                  = recipe,
            primary_item            = item,   
            production_rate_default = recipe.products[idx].rate,
            rate_produced           = output_rate
        ))
        self.ids_list.append(self.node_id_iterator)

        self.node_id_iterator += 1

        # Return the index of the node we just added
        return len(self.graph_nodes) - 1


if __name__ == '__main__':
    # Read in recipes in pickle file
    with open('asset_data.pickle', 'rb') as outfile:
        asset_data = pickle.load(outfile)

    planner = ProcessGraph(asset_data)

    for key,value in asset_data.items():
        print(key)