from flask import Flask
from extensions import db
from models import Booking, Coupon

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
        # Try to add the coupon_id column if it doesn't exist
        db.session.execute(text("ALTER TABLE booking ADD COLUMN coupon_id INTEGER"))
        db.session.commit()
        print('✅ Added coupon_id column to booking table')
    except Exception as e:
        print(f'❌ Error adding coupon_id column: {str(e)}')
        
    try:
        # Make sure the coupon table exists
        db.create_all()
        print('✅ Database schema updated')
    except Exception as e2:
        print(f'❌ Error updating schema: {str(e2)}')