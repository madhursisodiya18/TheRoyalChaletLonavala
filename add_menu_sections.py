from app import app, db, MenuSection, FoodMenu

with app.app_context():
    # Add new menu sections
    bar_section = MenuSection(
        name='bar',
        display_name='Bar',
        description='Alcoholic beverages and cocktails',
        icon='fas fa-wine-glass-alt',
        display_order=6
    )
    
    bar_snacks_section = MenuSection(
        name='bar-snacks',
        display_name='Bar Snacks',
        description='Snacks to enjoy with your drinks',
        icon='fas fa-cookie-bite',
        display_order=7
    )
    
    hookah_section = MenuSection(
        name='hookah',
        display_name='Hookah',
        description='Premium hookah flavors',
        icon='fas fa-smoking',
        display_order=8
    )
    
    cigarettes_section = MenuSection(
        name='cigarettes',
        display_name='Cigarettes',
        description='Premium cigarette brands',
        icon='fas fa-smoking',
        display_order=9
    )
    
    # Add sections to database
    db.session.add(bar_section)
    db.session.add(bar_snacks_section)
    db.session.add(hookah_section)
    db.session.add(cigarettes_section)
    
    try:
        db.session.commit()
        print("New menu sections added successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error adding menu sections: {e}")
        
    # Add sample menu items for Bar section
    if bar_section.id:
        bar_items = [
            {
                'name': 'Classic Mojito',
                'price': 350,
                'description': 'Refreshing cocktail with white rum, mint, lime, sugar, and soda water',
                'section_id': bar_section.id,
                'section': 'Bar',
                'subcategory': 'Cocktails',
                'is_available': True,
                'preparation_time': 5
            },
            {
                'name': 'Old Fashioned',
                'price': 450,
                'description': 'Classic cocktail with bourbon, sugar, bitters, and orange twist',
                'section_id': bar_section.id,
                'section': 'Bar',
                'subcategory': 'Cocktails',
                'is_available': True,
                'preparation_time': 5
            },
            {
                'name': 'Blended Scotch',
                'price': 550,
                'description': 'Premium blended scotch whisky, served neat or on the rocks',
                'section_id': bar_section.id,
                'section': 'Bar',
                'subcategory': 'Whisky',
                'is_available': True,
                'preparation_time': 2
            },
            {
                'name': 'Red Wine',
                'price': 400,
                'description': 'Glass of premium red wine',
                'section_id': bar_section.id,
                'section': 'Bar',
                'subcategory': 'Wine',
                'is_available': True,
                'preparation_time': 2
            }
        ]
        
        for item_data in bar_items:
            menu_item = FoodMenu(**item_data)
            db.session.add(menu_item)
    
    # Add sample menu items for Bar Snacks section
    if bar_snacks_section.id:
        bar_snacks_items = [
            {
                'name': 'Spicy Peanuts',
                'price': 150,
                'description': 'Roasted peanuts tossed with spices and herbs',
                'section_id': bar_snacks_section.id,
                'section': 'Bar Snacks',
                'subcategory': 'Nuts',
                'is_available': True,
                'preparation_time': 5
            },
            {
                'name': 'Cheese Platter',
                'price': 450,
                'description': 'Assortment of premium cheeses with crackers and fruits',
                'section_id': bar_snacks_section.id,
                'section': 'Bar Snacks',
                'subcategory': 'Platters',
                'is_available': True,
                'preparation_time': 10
            },
            {
                'name': 'Chicken Wings',
                'price': 350,
                'description': 'Crispy fried chicken wings tossed in spicy sauce',
                'section_id': bar_snacks_section.id,
                'section': 'Bar Snacks',
                'subcategory': 'Appetizers',
                'is_available': True,
                'preparation_time': 15
            }
        ]
        
        for item_data in bar_snacks_items:
            menu_item = FoodMenu(**item_data)
            db.session.add(menu_item)
    
    # Add sample menu items for Hookah section
    if hookah_section.id:
        hookah_items = [
            {
                'name': 'Mint Hookah',
                'price': 800,
                'description': 'Refreshing mint flavored hookah',
                'section_id': hookah_section.id,
                'section': 'Hookah',
                'subcategory': 'Flavors',
                'is_available': True,
                'preparation_time': 10
            },
            {
                'name': 'Double Apple Hookah',
                'price': 800,
                'description': 'Classic double apple flavored hookah',
                'section_id': hookah_section.id,
                'section': 'Hookah',
                'subcategory': 'Flavors',
                'is_available': True,
                'preparation_time': 10
            },
            {
                'name': 'Blueberry Hookah',
                'price': 850,
                'description': 'Sweet blueberry flavored hookah',
                'section_id': hookah_section.id,
                'section': 'Hookah',
                'subcategory': 'Flavors',
                'is_available': True,
                'preparation_time': 10
            }
        ]
        
        for item_data in hookah_items:
            menu_item = FoodMenu(**item_data)
            db.session.add(menu_item)
    
    # Add sample menu items for Cigarettes section
    if cigarettes_section.id:
        cigarettes_items = [
            {
                'name': 'Marlboro',
                'price': 350,
                'description': 'Pack of Marlboro cigarettes',
                'section_id': cigarettes_section.id,
                'section': 'Cigarettes',
                'subcategory': 'Premium',
                'is_available': True,
                'preparation_time': 1
            },
            {
                'name': 'Dunhill',
                'price': 400,
                'description': 'Pack of Dunhill cigarettes',
                'section_id': cigarettes_section.id,
                'section': 'Cigarettes',
                'subcategory': 'Premium',
                'is_available': True,
                'preparation_time': 1
            },
            {
                'name': 'Classic Mild',
                'price': 300,
                'description': 'Pack of Classic Mild cigarettes',
                'section_id': cigarettes_section.id,
                'section': 'Cigarettes',
                'subcategory': 'Regular',
                'is_available': True,
                'preparation_time': 1
            }
        ]
        
        for item_data in cigarettes_items:
            menu_item = FoodMenu(**item_data)
            db.session.add(menu_item)
    
    try:
        db.session.commit()
        print("New menu items added successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error adding menu items: {e}")