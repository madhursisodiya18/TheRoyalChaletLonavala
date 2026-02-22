import os
from flask import Flask
from extensions import db
from models import User, Booking, FoodMenu, FoodOrder, GalleryImage, Review, Contact, VillaSettings, Notification
from werkzeug.security import generate_password_hash
from datetime import datetime, date

# Create Flask app
app = Flask(__name__)

# Ensure instance directory exists
if not os.path.exists('instance'):
    os.makedirs('instance')

# Configure database
db_path = os.path.join(os.path.abspath('instance'), 'villa_booking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

def create_database():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create admin user
        admin_user = User(
            username='admin',
            email='admin@royalchalet.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True,
            phone='+919673340163',
            address='Admin Address',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(admin_user)
        
        # Create default villa settings
        default_settings = [
            ('villa_name', 'The Royal Chalet', 'Name of the villa'),
            ('villa_description', 'Luxury Villa Retreat in Lonavala, Pune', 'Description of the villa'),
            ('weekday_price', '10000', 'Price per night on weekdays'),
            ('weekend_price', '15000', 'Price per night on weekends'),
            ('check_in_time', '12:00', 'Check-in time'),
            ('check_out_time', '11:00', 'Check-out time'),
            ('contact_phone', '+919503589999', 'Contact phone number'),
            ('contact_email', 'info@royalchalet.com', 'Contact email'),
            ('contact_address', 'Lonavala, Pune, Maharashtra', 'Contact address'),
            ('mail_server', 'smtp.gmail.com', 'SMTP server for emails'),
            ('mail_port', '587', 'SMTP port'),
            ('mail_username', 'your-email@gmail.com', 'Email username'),
            ('mail_password', 'your-app-password', 'Email password')
        ]
        
        for key, value, description in default_settings:
            setting = VillaSettings(
                setting_key=key,
                setting_value=value,
                description=description
            )
            db.session.add(setting)
       
        
        # Create some sample gallery images
        gallery_images = [
            {
                'section': 'exterior',
                'image_path': 'Villa From Outside1.jpg',
                'caption': 'Villa Facade',
                'alt_text': 'Beautiful villa exterior view',
                'is_featured': True,
                'display_order': 1
            },
            {
                'section': 'exterior',
                'image_path': 'Villa From Outside2.jpg',
                'caption': 'Villa Side View',
                'alt_text': 'Elegant villa side view',
                'is_featured': True,
                'display_order': 2
            },
            {
                'section': 'bedrooms',
                'image_path': 'masterbedroom.jpg',
                'caption': 'Master Bedroom',
                'alt_text': 'Luxurious master bedroom',
                'is_featured': True,
                'display_order': 3
            },
            {
                'section': 'bedrooms',
                'image_path': 'bedroom1.jpg',
                'caption': 'Guest Bedroom 1',
                'alt_text': 'Comfortable guest bedroom',
                'is_featured': False,
                'display_order': 4
            },
            {
                'section': 'living',
                'image_path': 'hall1.jpg',
                'caption': 'Living Room',
                'alt_text': 'Spacious living area',
                'is_featured': True,
                'display_order': 5
            },
            {
                'section': 'pool',
                'image_path': 'Swiming pool 1.jpg',
                'caption': 'Private Pool',
                'alt_text': 'Stunning private pool',
                'is_featured': True,
                'display_order': 6
            }
        ]
        
        for image_data in gallery_images:
            gallery_image = GalleryImage(**image_data)
            db.session.add(gallery_image)
        
        # Commit all changes
        db.session.commit()
        
        print("✅ Database created successfully!")
        print("📊 Tables created:")
        print("   - User (with phone, address, timestamps)")
        print("   - Booking (with check_in/check_out, total_price)")
        print("   - FoodMenu (with availability, preparation_time)")
        print("   - FoodOrder (with JSON items, status)")
        print("   - GalleryImage (with alt_text, is_featured)")
        print("   - Review (with rating, approval)")
        print("   - Contact (with status tracking)")
        print("   - VillaSettings (with dynamic configuration)")
        print("   - Notification (with read status)")
        print("\n👤 Default admin user created:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   Email: admin@royalchalet.com")
        print("\n⚙️ Default villa settings configured")
        print("🍽️ Sample menu items added")
        print("🖼️ Sample gallery images added")

if __name__ == '__main__':
    create_database()