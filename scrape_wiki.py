### 
# For scraping the satisfactory wiki and getting item and recipe data
# Non-general, uses the structure, tag labels and attributes present on the website as of 15-06-21
###

import requests
from bs4 import BeautifulSoup as bs
from data_defs import Recipe, Component, Asset


def find_navigation_table(full_soup: bs, subsection):
    '''
    Find requested table in navigation box
    '''

    anchor = full_soup.find_all('a', attrs={'title':f"Template:{subsection}Nav"})

    if len(anchor) == 0:
        raise Exception(f"{subsection} navigation box not found")

    if len(anchor) > 1:
        print(f"WARNING: Multiple potential {subsection.lower} navigation boxes found, using first one")

    anchor = anchor[0]

    return anchor.find_parent('table')


def get_production_buildings(buildings_table: bs, base_link='https://satisfactory.fandom.com/wiki/', overwrite_existing_image = False):
    '''
    Get the data for all production buildings
    '''
    buildings = {}

    names = None
    for row in buildings_table.find_all('tr'):
        first_col = row.find('td')
        if first_col is not None and first_col.text.lower() == 'production':

            # Get the names from the images, so the categories get left out
            names = [element.find_parent('a')['href'].split('/')[-1] for element in row.find_all('img')]

    if len(names) > 0:
        for name in names:
            # Get name from link
            building_name = name.lower()

            full_link = f"{base_link}{name}"
            # Get image
            try:
                page = requests.get(full_link)
                soup = bs(page.content, 'html.parser')
                img_url = soup.find(attrs={'class':'infobox-table'}).find(attrs={'class':'image'}).find('img')['src']
                
                img_url = img_url.split('/')
                for i,ele in enumerate(img_url):
                    if '.png' in ele:
                        idx = i
                        break
                img_url = '/'.join(img_url[:idx+1])

                img_data = requests.get(img_url).content
                image_path = f"images/{building_name}.jpg"

                with open(image_path, 'wb') as handler:
                    handler.write(img_data)
            except:
                print( f"Image not found or download failed for {full_link}" )
                image_path = None

            # Construct the data class and add to dict
            buildings[building_name] = Asset(name=building_name, image_local=image_path, image_url=img_url, type='building')

            print(f"{building_name}...Done")

    return buildings


def get_section(full_soup: bs, section_name: str) -> list:
    '''
    Gets a list of elements of a section on the wiki page - list of navigable strings
    '''

    start = False
    output = []
    for element in full_soup.find(attrs={'class':'mw-parser-output'}).findChildren(recursive=False):
            if element.name == 'h2':
                if section_name.lower() in element.text.lower():
                    start = True
                elif start == True:
                    break
            elif start == True:
                output.append(element)
    
    return output


def parse_crafting(recipe_table: bs) -> list[Recipe]:
    '''
    Gets all recipes for a given recipe table soup
    '''

    recipes = []

    if recipe_table is None:
        return recipes

    # Loop through all rows
    new_recipe = True
    recipe_name = None
    building_name = None
    ingredients = []
    products = []
    for row in recipe_table.find_all('tr')[1:]:
        cols = row.find_all('td')
        cols = [ele.text for ele in cols]
        cols = [ele for ele in cols if (ele and ele != u'\xa0')]  # Remove empty entries and non-breaking space characters
        
        # Data extraction relies on parsing known string formats - see output of:
        # print(cols)

        # Extract data from columns
        if new_recipe:
            recipe_name = '_'.join(cols[0].lower().replace('alternate','').split(' '))

            ingredients_done = False

            manual_crafting = 'craft bench' in row.text.lower() or 'equipment workshop' in row.text.lower()

            for element in cols[1:-1]:
                if 'sec' in element or (manual_crafting and not element.split(' ')[0].isdigit()):
                    # If we find the production building (has 'sec' data), set flag
                    ingredients_done = True

                    digit_idx = [x.isdigit() for x in element].index(True)
                    building_name = '_'.join(element[:digit_idx].lower().split(' '))

                else:
                    # List of ingredients
                    if not ingredients_done:
                        ele = element.replace(' / min', '').replace('× ','').split(' ')
                        
                        quantity = float(ele[0])
                        name = '_'.join(ele[1:])

                        if manual_crafting:
                            item_name = name.lower()
                            rate = None
                        else:
                            digit_idx = [x.isdigit() for x in name].index(True)

                            item_name = name[:digit_idx].lower()
                            rate = float(name[digit_idx:])

                        # print(item_name)
                        ingredients.append(Component(item_name, quantity, rate))

                    # List of products
                    else:
                        ele = element.replace('/ min', '').replace('× ','').replace(' MJ / item','').split(' ')
                        
                        quantity = float(ele[0])

                        try:
                            energy_rate = float(ele[-1])    
                        except:
                            energy_rate = None

                        name = '_'.join(ele[1:-1])

                        if manual_crafting:
                            item_name = name.lower()
                            rate = None
                        else:
                            digit_idx = [x.isdigit() for x in name].index(True)

                            item_name = name[:digit_idx].lower()
                            rate = float(name[digit_idx:])

                        products.append(Component(item_name, quantity, rate, energy_rate))

            # Manufacturer recipes have multiple rows of input in the wiki (and manual crafting stations)
            if building_name == 'manufacturer' or building_name == 'blender' or building_name == 'craft_bench' or building_name == 'equipment_workshop':
                new_recipe = False
            else:
                recipes.append(Recipe(recipe_name, ingredients, building_name, products))
                ingredients = []
                products = []

        # Multiple row recipes
        else:
            for element in cols:
                ele = element.replace(' / min', '').replace('× ','').split(' ')

                quantity = float(ele[0])

                name = '_'.join(ele[1:])
                digit_idx = [x.isdigit() for x in name].index(True)

                item_name = name[:digit_idx].lower()
                rate = float(name[digit_idx:])

                ingredients.append(Component(item_name, quantity, rate))

            recipes.append(Recipe(recipe_name, ingredients, building_name, products))
            ingredients = []
            products = []
            new_recipe = True

    return recipes


def read_wiki_page(full_soup: bs) -> dict:
    '''
    Reads the wiki page of a satisfactory object (item, building, etc) and outputs a dataclass containing relevant data
    '''
    output = {'item': None, 'msg': [], 'error': []}

    # Item name
    item_name = '_'.join(full_soup.find(attrs={"itemprop":"name"}).text.lower().split(' '))

    # Read table of contents to decide what to do with this page
    try:
        table_of_contents = full_soup.find('div', attrs={'id':'toc'}).find('ul')
    except:
        table_of_contents = None

    if table_of_contents is None:
        output['msg'].append( 'Table of contents not found' )
        output['error'].append(1)
        return output

    # Save image
    image_path = f"images/{item_name}.jpg"
    try:
        img_url = full_soup.find(attrs={'class':'infobox-table'}).find(attrs={'class':'image'}).find('img')['src']
        
        img_url = img_url.split('/')
        for i,ele in enumerate(img_url):
            if '.png' in ele:
                idx = i
                break
        img_url = '/'.join(img_url[:idx+1])
        
        img_data = requests.get(img_url).content

        with open(image_path, 'wb') as handler:
            handler.write(img_data)

    except:
        image_path = None
        output['msg'].append( 'Image not found or download failed' )
        output['error'].append(2)

    # Parse section titles
    headings = [element.text.lower() for element in table_of_contents.find_all('span', attrs={'class':'toctext'})]
    numbers  = [element.text.split('.') for element in table_of_contents.find_all('span', attrs={'class':'tocnumber'})]

    # Check if it's an item that can be crafted or extracted
    recipes = []
    if 'obtaining' in headings:
        # Get the headings and soup
        section = numbers[headings.index('obtaining')]

        subsection_titles = []
        for i,num in enumerate(numbers):
            if len(num) > 1 and num[0] == section[0]:
                subsection_titles.append(headings[i])

        subsections = get_section(full_soup, 'obtaining')

        # Extract data
        resource_acquisition_flag = 0
        extraction_energy_flag = 0
        crafting_recipes_flag = 0
        recipe_list = []
        for element in subsections:

            if element.name == 'h3':
                if resource_acquisition_flag == 0 and 'resource acquisition' in element.text.lower():
                    resource_acquisition_flag = 1
                    continue

                elif extraction_energy_flag == 0 and 'extraction energy' in element.text.lower():
                    extraction_energy_flag = 1
                    continue

                elif crafting_recipes_flag == 0 and 'crafting' in element.text.lower():
                    crafting_recipes_flag = 1
                    continue
            
            # Relevant data is in the next tag after the heading
            if resource_acquisition_flag == 1 and element.name == 'p':
                if 'miners' in element.text.lower():
                    extractor = 'miner'

                elif 'extractor' in element.text.lower():
                    # ignoring resource well extractors
                    extractor = [link for link in element.find_all('a') if 'extractor' in link['title'].lower()][0]['href'].split('/')[-1].lower()   
                
                else:
                    extractor = None

                if extractor is None:
                    resource_acquisition_flag = -1
                else:
                    resource_acquisition_flag = 2

                continue

            if resource_acquisition_flag == 2 and element.name == 'table':
                # Get mk 1 miner or extractor output for a normal node
                production_rate = float(element.find_all('tr')[2].find_all('td')[1].text)

                resource_acquisition_flag = -1
                continue

            if extraction_energy_flag == 1 and element.name == 'p':
                try:
                    extraction_energy = float(element.find('span')['title'])
                except:
                    words = element.text.split(' ')
                    extraction_energy = words[words.index('MJ')-1]

                extraction_energy_flag = -1
                continue

            if crafting_recipes_flag == 1 and element.name == 'div':
                recipe_table = element.find(attrs={'class':'wikitable'})
                recipe_list = parse_crafting(recipe_table)

        # Make psuedo recipe for extraction
        if resource_acquisition_flag == -1 and extraction_energy_flag == -1:
            recipes.append(Recipe(
                name=item_name, 
                ingredients=[], 
                building_name=extractor, 
                products=[Component(name=item_name, quantity=1, rate=production_rate, energy_rate=extraction_energy)]
                ))

        # Add recipes in the table if not already in it - sometimes the extraction recipe is in the wiki table, sometimes not
        for recipe in recipe_list:
            if recipe not in recipes:
                recipes.append(recipe)

    # Construct Item data class and put into output dict
    output['item'] = Asset(name=item_name, image_local=image_path, image_url=img_url, type='item', recipes=recipes)

    return output


def get_items_and_recipes(items_table: bs, base_link='https://satisfactory.fandom.com/wiki/'):
    '''
    Get the data for all satisfactory inventory items also outputs a list of all unique recipes
    '''
    items = {}
    recipes = []

    # Get the names from the images, so the labels get left out (i.e. the tier links) - also, remove single quote characters that were read as %27
    names = [element.find_parent('a')['href'].split('/')[-1] for element in items_table.find_all('img')]

    if len(names) > 0:
        for name in names:
            full_link = f"{base_link}{name}"

            page = requests.get(full_link)
            soup = bs(page.content, 'html.parser')

            output = read_wiki_page(soup)

            if output['item'] is not None:
                # Use a dict so we can get individual items quickly by name
                items[output['item'].name] = output['item']

                for recipe in output['item'].recipes:
                    # Don't add duplicates - recipes with multiple products will show up in the list of different items
                    if recipe not in recipes:
                        recipes.append(recipe)
                
                print(f"{output['item'].name}...Done")
            else:
                print(f"Failed to read {full_link} -> {output['msg']}")

    return items, recipes


def get_all_asset_data(wiki_url: str = 'https://satisfactory.fandom.com/wiki/Satisfactory_Wiki'):
    '''
    Get buildings and item data from the satisfactory wiki and return a list of Asset classes
    '''

    # Get content of satisfactory wiki home page
    page = requests.get(wiki_url)
    soup = bs(page.content, 'html.parser')

    # Get data and images for all production buildings
    build_table = find_navigation_table(soup, 'Building')
    buildings = get_production_buildings(build_table)

    print()
    # Get data and images for all items
    items_table = find_navigation_table(soup, 'Item')
    items, _ = get_items_and_recipes(items_table)

    return buildings | items


def assets_to_pickle(asset_data: dict, output_file: str = 'asset_data.pickle'):
    '''
    Save asset data to a pickle file
    '''
    import pickle

    with open(output_file, 'wb') as outfile:
        pickle.dump(asset_data, outfile)

    print(f"Asset data saved in {output_file}")


def assets_to_json(asset_data: dict, output_file: str = 'asset_data.json'):
    '''
    Save asset data to a json file - for interoperability
    '''
    import json
    
    flat_data = []

    # Loop through all assets in list and flatten the classes within classes into dictionaries
    for key in asset_data:
        asset = asset_data[key]

        recipes = []
        if asset.recipes is not None:
            for recipe in asset.recipes:
                recipe.products = [vars(product) for product in recipe.products]
                recipe.ingredients = [vars(ingredient) for ingredient in recipe.ingredients]

                recipes.append(vars(recipe))

        
        dictionary = vars(asset)
        dictionary['recipes'] = recipes

        flat_data.append(dictionary)

    with open(output_file, 'w') as outfile:
        json.dump(flat_data, outfile, indent=2)


if __name__ == '__main__':
    
    asset_data = get_all_asset_data()
    assets_to_pickle(asset_data)

    # import pickle
    # with open('asset_data.pickle', 'rb') as infile:
    #     asset_data = pickle.load(infile)

    # assets_to_json(asset_data)
