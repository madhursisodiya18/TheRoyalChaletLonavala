import sqlite3
import os
import json

def main():
    # Get the database file path
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'villa_booking.db')
    
    print(f"Attempting to connect to database at: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns exist in the booking table
    cursor.execute("PRAGMA table_info(booking)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    # Add all required columns if they don't exist
    columns_to_add = {
        'adults': ('INTEGER', 1),
        'children': ('INTEGER', 0),
        'villa_type': ('VARCHAR(50)', "'Standard Villa'"),
        'meal_plan': ('VARCHAR(50)', 'NULL'),
        'amenities': ('TEXT', 'NULL'),
        'base_price': ('INTEGER', 'NULL'),
        'meal_cost': ('INTEGER', 0),
        'amenities_cost': ('INTEGER', 0),
        'subtotal': ('INTEGER', 'NULL'),
        'gst': ('INTEGER', 0),
        'booking_date': ('DATETIME', 'NULL')
        # payment_status is already in the database
    }
    
    for column_name, (column_type, default_value) in columns_to_add.items():
        if column_name not in column_names:
            print(f"Adding '{column_name}' column to booking table...")
            if default_value == 'NULL':
                cursor.execute(f"ALTER TABLE booking ADD COLUMN {column_name} {column_type}")
            else:
                cursor.execute(f"ALTER TABLE booking ADD COLUMN {column_name} {column_type} DEFAULT {default_value}")
            print(f"'{column_name}' column added successfully.")
        else:
            print(f"'{column_name}' column already exists.")
    
    # Update existing bookings with default values for required fields
    print("Updating existing bookings with default values...")
    cursor.execute("""
        UPDATE booking 
        SET villa_type = 'Standard Villa',
            adults = COALESCE(adults, 1),
            children = COALESCE(children, 0),
            meal_cost = COALESCE(meal_cost, 0),
            amenities_cost = COALESCE(amenities_cost, 0),
            payment_status = COALESCE(payment_status, 'pending')
        WHERE villa_type IS NULL OR adults IS NULL OR children IS NULL OR meal_cost IS NULL OR amenities_cost IS NULL OR payment_status IS NULL
    """)
    
    # Set empty JSON array for amenities if NULL
    cursor.execute("UPDATE booking SET amenities = '[]' WHERE amenities IS NULL")
    
    # Calculate and update base_price, subtotal without GST; set gst to 0
    cursor.execute("""
        UPDATE booking
        SET base_price = COALESCE(base_price, COALESCE(base_price, 0)),
            subtotal = COALESCE(subtotal, COALESCE(base_price, 0) + COALESCE(meal_cost, 0) + COALESCE(amenities_cost, 0)),
            gst = COALESCE(gst, 0)
        WHERE 1 = 1
    """)
    # Align total_price with subtotal to remove any legacy GST amounts
    cursor.execute("""
        UPDATE booking
        SET total_price = COALESCE(subtotal, COALESCE(base_price, 0) + COALESCE(meal_cost, 0) + COALESCE(amenities_cost, 0))
        WHERE total_price IS NULL OR total_price != COALESCE(subtotal, COALESCE(base_price, 0) + COALESCE(meal_cost, 0) + COALESCE(amenities_cost, 0))
    """)
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    
    print("Database update completed successfully.")

if __name__ == "__main__":
    main()
    from flask import Flask
from extensions import db
from models import Booking

# Create Flask app
app = Flask(__name__)

# Configure database
import os
db_path = os.path.join(os.path.abspath('instance'), 'villa_booking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

from sqlalchemy import text

with app.app_context():
    try:
        # Try to add the payment_status column if it doesn't exist
        db.session.execute(text("ALTER TABLE booking ADD COLUMN payment_status VARCHAR(20) DEFAULT 'pending'"))
        db.session.commit()
        print('✅ Added payment_status column to booking table')
    except Exception as e:
        print(f'❌ Error: {str(e)}')
        # If the column already exists or there's another issue, try a different approach
        try:
            # Recreate the table with the correct schema
            print('Attempting to update database schema...')
            db.create_all()
            print('✅ Database schema updated')
        except Exception as e2:
            print(f'❌ Error updating schema: {str(e2)}')
            
    # Add is_veg column to food_menu table if it doesn't exist
    try:
        # Check if column exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('food_menu')]
        
        if 'is_veg' not in columns:
            print("Adding is_veg column to food_menu table...")
            # Use SQLAlchemy to add the column with current syntax
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE food_menu ADD COLUMN is_veg BOOLEAN DEFAULT 1"))
                
                # Set default values - assume all items are vegetarian by default
                conn.execute(text("UPDATE food_menu SET is_veg = 1"))
                conn.commit()
            
            print("is_veg column added successfully!")
        else:
            print("is_veg column already exists in food_menu table")
    except Exception as e:
        print(f"Error updating food_menu table: {e}")

    try:
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('booking')]
        with db.engine.connect() as conn:
            if 'booking_id' not in columns:
                conn.execute(text("ALTER TABLE booking ADD COLUMN booking_id VARCHAR(50)"))
            if 'user_name' not in columns:
                conn.execute(text("ALTER TABLE booking ADD COLUMN user_name VARCHAR(100)"))
            if 'email' not in columns:
                conn.execute(text("ALTER TABLE booking ADD COLUMN email VARCHAR(120)"))
            if 'phone' not in columns:
                conn.execute(text("ALTER TABLE booking ADD COLUMN phone VARCHAR(20)"))
            if 'address' not in columns:
                conn.execute(text("ALTER TABLE booking ADD COLUMN address TEXT"))
            conn.commit()
        print("Booking table updated with new columns if they were missing")
    except Exception as e:
        print(f"Error updating booking table: {e}")
