from app import app, db
from models import MenuSection, FoodMenu
from flask import flash

def create_menu_section(name, display_name, icon="fas fa-utensils", description="", display_order=0):
    """Create a menu section if it doesn't exist"""
    existing = MenuSection.query.filter_by(name=name).first()
    if existing:
        # Update existing section
        existing.display_name = display_name
        existing.icon = icon
        existing.description = description
        existing.display_order = display_order
        existing.is_active = True
        return existing
    else:
        # Create new section
        section = MenuSection(
            name=name,
            display_name=display_name,
            icon=icon,
            description=description,
            display_order=display_order,
            is_active=True
        )
        db.session.add(section)
        return section

def create_menu_item(name, price, section_id, section_name, subcategory=None, description="", preparation_time=15):
    """Create a menu item if it doesn't exist, otherwise update it"""
    existing = FoodMenu.query.filter_by(name=name, section_id=section_id).first()
    if existing:
        # Update existing item
        existing.price = price
        existing.description = description
        existing.subcategory = subcategory
        existing.preparation_time = preparation_time
        existing.is_available = True
        return existing
    else:
        # Create new item
        item = FoodMenu(
            name=name,
            price=price,
            section_id=section_id,
            section=section_name,
            subcategory=subcategory,
            description=description,
            preparation_time=preparation_time,
            is_available=True
        )
        db.session.add(item)
        return item

def update_menu():
    """Update the menu with predefined categories and items"""
    with app.app_context():
        # Create sections
        veg_main = create_menu_section(
            "vegetarian_main", 
            "🥗 VEGETARIAN MAIN COURSE", 
            "fas fa-leaf", 
            "Vegetarian main course dishes", 
            display_order=1
        )
        
        non_veg_main = create_menu_section(
            "non_vegetarian_main", 
            "🍗 NON-VEGETARIAN MAIN COURSE", 
            "fas fa-drumstick-bite", 
            "Non-vegetarian main course dishes", 
            display_order=2
        )
        
        rice_roti = create_menu_section(
            "rice_roti", 
            "🍚 RICE & ROTI", 
            "fas fa-bread-slice", 
            "Rice and bread options", 
            display_order=3
        )
        
        starters = create_menu_section(
            "starters", 
            "🍟 STARTERS / SNACKS", 
            "fas fa-cookie", 
            "Starters and snacks", 
            display_order=4
        )
        
        beverages = create_menu_section(
            "beverages", 
            "🥤 BEVERAGES", 
            "fas fa-glass-whiskey", 
            "Refreshing drinks", 
            display_order=5
        )
        
        bar_menu = create_menu_section(
            "bar_menu", 
            "🍹 BAR MENU", 
            "fas fa-cocktail", 
            "Alcoholic beverages", 
            display_order=6
        )
        
        tobacco = create_menu_section(
            "tobacco", 
            "🚬 CIGARETTES & TOBACCO", 
            "fas fa-smoking", 
            "Cigarettes and tobacco products", 
            display_order=7
        )
        
        # Commit sections to get IDs
        db.session.commit()
        
        # Add vegetarian main course items
        create_menu_item("Paneer Butter Masala", 140, veg_main.id, veg_main.name)
        create_menu_item("Veg Biryani", 120, veg_main.id, veg_main.name)
        create_menu_item("Mix Veg Curry", 110, veg_main.id, veg_main.name)
        create_menu_item("Aloo Gobi", 100, veg_main.id, veg_main.name)
        create_menu_item("Bhindi Masala", 100, veg_main.id, veg_main.name)
        create_menu_item("Dal Tadka", 90, veg_main.id, veg_main.name)
        create_menu_item("Dal Fry", 80, veg_main.id, veg_main.name)
        
        # Add non-vegetarian main course items
        create_menu_item("Chicken Curry", 160, non_veg_main.id, non_veg_main.name)
        create_menu_item("Chicken Masala", 170, non_veg_main.id, non_veg_main.name)
        create_menu_item("Egg Curry", 100, non_veg_main.id, non_veg_main.name)
        create_menu_item("Chicken Biryani", 150, non_veg_main.id, non_veg_main.name)
        create_menu_item("Mutton Curry (on request)", 240, non_veg_main.id, non_veg_main.name)
        
        # Add rice & roti items
        create_menu_item("Steamed Rice (1 plate)", 60, rice_roti.id, rice_roti.name)
        create_menu_item("Jeera Rice", 70, rice_roti.id, rice_roti.name)
        create_menu_item("Veg Pulao", 90, rice_roti.id, rice_roti.name)
        create_menu_item("Chapati (per piece)", 10, rice_roti.id, rice_roti.name)
        create_menu_item("Butter Naan (per piece)", 25, rice_roti.id, rice_roti.name)
        create_menu_item("Tandoori Roti (per piece)", 15, rice_roti.id, rice_roti.name)
        
        # Add starters/snacks items
        create_menu_item("Veg Pakora", 80, starters.id, starters.name)
        create_menu_item("French Fries", 90, starters.id, starters.name)
        create_menu_item("Chicken Lollipop (4 pcs)", 130, starters.id, starters.name)
        create_menu_item("Paneer Tikka (4 pcs)", 120, starters.id, starters.name)
        create_menu_item("Chicken Tikka (4 pcs)", 150, starters.id, starters.name)
        create_menu_item("Boiled Egg (2 pcs)", 40, starters.id, starters.name)
        
        # Add beverages items
        create_menu_item("Cold Drink (Glass/Bottle)", 40, beverages.id, beverages.name, description="30–50")
        create_menu_item("Mineral Water (1L)", 20, beverages.id, beverages.name)
        create_menu_item("Tea / Coffee", 20, beverages.id, beverages.name)
        create_menu_item("Buttermilk / Lassi", 30, beverages.id, beverages.name)
        
        # Add bar menu items with subcategories
        create_menu_item("Royal Stag", 150, bar_menu.id, bar_menu.name, subcategory="🥃 WHISKEY", description="Per peg")
        create_menu_item("Blenders Pride", 180, bar_menu.id, bar_menu.name, subcategory="🥃 WHISKEY", description="Per peg")
        create_menu_item("Black Label", 350, bar_menu.id, bar_menu.name, subcategory="🥃 WHISKEY", description="Per peg")
        
        create_menu_item("Kingfisher (Pint/Can)", 130, bar_menu.id, bar_menu.name, subcategory="🍺 BEER")
        create_menu_item("Budweiser", 160, bar_menu.id, bar_menu.name, subcategory="🍺 BEER")
        create_menu_item("Bira", 170, bar_menu.id, bar_menu.name, subcategory="🍺 BEER")
        
        create_menu_item("Mojito", 220, bar_menu.id, bar_menu.name, subcategory="🍸 COCKTAILS")
        create_menu_item("Screwdriver", 250, bar_menu.id, bar_menu.name, subcategory="🍸 COCKTAILS")
        create_menu_item("Cosmopolitan", 300, bar_menu.id, bar_menu.name, subcategory="🍸 COCKTAILS")
        create_menu_item("Tequila Shot", 200, bar_menu.id, bar_menu.name, subcategory="🍸 COCKTAILS")
        
        create_menu_item("Red / White Wine (Glass)", 250, bar_menu.id, bar_menu.name, subcategory="🥂 WINE")
        create_menu_item("Bottle (Domestic/Imported)", 1500, bar_menu.id, bar_menu.name, subcategory="🥂 WINE", description="₹1000–₹2000")
        
        # Add tobacco items
        create_menu_item("Classic Milds", 20, tobacco.id, tobacco.name, description="Per stick")
        create_menu_item("Gold Flake", 15, tobacco.id, tobacco.name, description="Per stick")
        create_menu_item("Marlboro", 25, tobacco.id, tobacco.name, description="Per stick")
        create_menu_item("Rolling Paper", 30, tobacco.id, tobacco.name)
        create_menu_item("Hookah (Mint, Apple, Paan Flavors)", 500, tobacco.id, tobacco.name)
        
        # Commit all changes
        db.session.commit()
        print("Menu updated successfully!")

if __name__ == "__main__":
    update_menu()