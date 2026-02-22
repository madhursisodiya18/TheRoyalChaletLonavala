from flask import Flask
from extensions import db
from models import GalleryImage

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
        # Try to add the tags column if it doesn't exist
        db.session.execute(text("ALTER TABLE gallery_image ADD COLUMN tags VARCHAR(200) DEFAULT ''"))
        db.session.commit()
        print('✅ Added tags column to gallery_image table')
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