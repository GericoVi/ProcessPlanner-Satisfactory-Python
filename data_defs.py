from dataclasses import dataclass


@dataclass
class Asset:
    '''
    For asset data
    '''
    name: str
    image: str
    type: str
    recipes: list = None


@dataclass
class Recipe:
    '''
    For recipe information
    '''
    name: str
    ingredients: tuple
    building_name: str
    products: tuple

    def __post_init__(self):
        # For searching through a list of recipes
        self.ingredients_names  = [ingredient.name for ingredient in self.ingredients]
        self.products_names     = [product.name for product in self.products]

    def __eq__(self, other):
        # It should be enough to compare the recipe names, these are unique?
        return self.name == other.name

        """ #First trivially check if they have the same number of components
        if (len(self.ingredients) != len(other.ingredients)) or (len(self.products) != len(other.products)):
            return False

        # Check if the string attributes are equal
        if (self.name != other.name) or (self.building_name != other.building_name):
            return False

        # Need to call the equate functions of the objects in the list of ingredients and products
        for m,n in zip(self.ingredients, other.ingredients):
            if m != n:
                return False

        for m,n in zip(self.products, other.products):
            if m != n:
                return False

        # If all checks are fine, then the two recipes are equal
        return True """

    def __hash__(self):
        return hash((self.name, self.ingredients, self.building_name, self.products))


@dataclass(unsafe_hash=True)
class Component:
    '''
    Stores data on each component of a recipe (ingredients or products)
    '''
    name        : str
    quantity    : float         # quantity needed/produced per recipe
    rate        : float         # rate consumed/produced by the recipe per minute at 100% clock speed
    energy_rate : float = None  # per item


@dataclass
class GraphNode():
    '''
    Generic node on the graph
    '''
    node_id : int
    name    : str


@dataclass
class ItemNode(GraphNode):
    '''
    For items - components or liquids or gases
    '''
    rate_requested  : float     # Amount per min needed downstream
    rate_filled     : float     # Amount per min provided upstream

    def rate_needed(self):
        '''
        Utility function to get the rate still needed to be fulfilled
        '''
        return self.rate_requested - self.rate_filled

@dataclass
class BuildingNode(GraphNode):
    '''
    For production buildings
    '''     
    recipe                  : Recipe
    primary_item            : str          
    production_rate_default : float     # Amount of primary item produced per min at 100% clock speed
    rate_produced           : float     # Amount of primary item actually produced
    
    def __post_init__(self):
        self.update_clockspeed()

    def update_clockspeed(self):
        '''
        Utility function for updating clock speed - decimal
        '''
        self.clock_speed = (self.rate_produced / self.production_rate_default)
    

@dataclass
class GraphEdge:
    '''
    For the edges of the production planner graph
    '''
    source_id   : int
    target_id   : int
    item_name   : str
    rate        : float     # rate of flow through this edge - i.e. flow of items or liquids or gases