from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, make_response, send_from_directory, abort, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from extensions import db, csrf
import os
import json
import logging
import io
import csv
from datetime import datetime, timedelta, timezone
import locale
from functools import wraps

from models import User, Booking, FoodMenu, FoodOrder, GalleryImage, Review, Contact, VillaSettings, Notification, MenuSection, Coupon
from flask import abort
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('You need to be an admin to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['DEBUG'] = True

# Upload folder configuration
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# Add context processor for template variables
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')

# Set debug mode
app.config['DEBUG'] = True

# Ensure instance directory exists
if not os.path.exists('instance'):
    os.makedirs('instance')

# Use absolute path for database
db_path = os.path.join(os.path.abspath('instance'), 'villa_booking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
csrf.init_app(app)

# Ensure database tables exist
with app.app_context():
    # Create tables if they don't exist
    db.create_all()
    
    def initialize_default_settings():
        """Initialize default villa settings"""
        default_settings = {
            'villa_name': 'The Royal Chalet',
            'villa_description': 'Luxury villa with modern amenities',
            'weekday_price': '10000',
            'weekend_price': '15000',
            'max_guests': '8',
            'contact_email': 'info@royalchalet.com',
            'contact_phone': '+91 98765 43210',
            'check_in_time': '14:00',
            'check_out_time': '11:00',
            'mail_server': 'smtp.gmail.com',
            'mail_port': '587',
            'mail_username': os.environ.get('MAIL_USERNAME', 'your-email@gmail.com'),
            'mail_password': os.environ.get('MAIL_PASSWORD', 'your-app-password')
        }
        
        for key, value in default_settings.items():
            existing_setting = VillaSettings.query.filter_by(setting_key=key).first()
            if not existing_setting:
                setting = VillaSettings(setting_key=key, setting_value=value)
                db.session.add(setting)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error initializing default settings: {str(e)}")
            
    def update_email_config_from_db():
        """Update email configuration from database settings"""
        mail_server = VillaSettings.query.filter_by(setting_key='mail_server').first()
        mail_port = VillaSettings.query.filter_by(setting_key='mail_port').first()
        mail_username = VillaSettings.query.filter_by(setting_key='mail_username').first()
        mail_password = VillaSettings.query.filter_by(setting_key='mail_password').first()
        
        if mail_server and mail_server.setting_value:
            app.config['MAIL_SERVER'] = mail_server.setting_value
            app.logger.info(f"Updated MAIL_SERVER from database: {mail_server.setting_value}")
            
        if mail_port and mail_port.setting_value:
            app.config['MAIL_PORT'] = int(mail_port.setting_value)
            app.logger.info(f"Updated MAIL_PORT from database: {mail_port.setting_value}")
            
        if mail_username and mail_username.setting_value:
            app.config['MAIL_USERNAME'] = mail_username.setting_value
            app.logger.info(f"Updated MAIL_USERNAME from database: {mail_username.setting_value}")
            
        if mail_password and mail_password.setting_value:
            app.config['MAIL_PASSWORD'] = mail_password.setting_value
            app.logger.info("Updated MAIL_PASSWORD from database")
            
        app.logger.info("Email configuration updated from database settings")
    
    # Initialize default settings
    initialize_default_settings()
    
    # Update email configuration from database settings
    update_email_config_from_db()
    
    # Create default admin user if it doesn't exist
    if not User.query.filter_by(username='admin').first():
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
        db.session.commit()
    
    # Add sample menu items if they don't exist
    if not FoodMenu.query.first():
        # Get section IDs
        breakfast_section = MenuSection.query.filter_by(name='breakfast').first()
        main_course_section = MenuSection.query.filter_by(name='main-course').first()
        starters_section = MenuSection.query.filter_by(name='starters').first()
        desserts_section = MenuSection.query.filter_by(name='desserts').first()
        beverages_section = MenuSection.query.filter_by(name='beverages').first()
        
        sample_menu_items = [
            {
                'name': 'Masala Dosa',
                'price': 150,
                'description': 'Crispy dosa with potato filling and coconut chutney',
                'section_id': breakfast_section.id if breakfast_section else None,
                'section': 'Breakfast',
                'subcategory': 'South Indian',
                'is_available': True,
                'preparation_time': 10
            },
            {
                'name': 'Idli Sambar',
                'price': 120,
                'description': 'Soft idli with sambar and chutney',
                'section_id': breakfast_section.id if breakfast_section else None,
                'section': 'Breakfast',
                'subcategory': 'South Indian',
                'is_available': True,
                'preparation_time': 8
            },
            {
                'name': 'Butter Chicken',
                'price': 350,
                'description': 'Creamy butter chicken with naan bread',
                'section_id': main_course_section.id if main_course_section else None,
                'section': 'Main Course',
                'subcategory': 'North Indian',
                'is_available': True,
                'preparation_time': 20
            },
            {
                'name': 'Dal Khichdi',
                'price': 200,
                'description': 'Comforting dal khichdi with ghee',
                'section_id': main_course_section.id if main_course_section else None,
                'section': 'Main Course',
                'subcategory': 'Gujarati',
                'is_available': True,
                'preparation_time': 15
            },
            {
                'name': 'Aloo Paratha',
                'price': 80,
                'description': 'Stuffed potato paratha with curd',
                'section_id': breakfast_section.id if breakfast_section else None,
                'section': 'Breakfast',
                'subcategory': 'North Indian',
                'is_available': True,
                'preparation_time': 12
            },
            {
                'name': 'Bread Omelette',
                'price': 100,
                'description': 'Fresh bread with fluffy omelette',
                'section_id': breakfast_section.id if breakfast_section else None,
                'section': 'Breakfast',
                'subcategory': 'Continental',
                'is_available': True,
                'preparation_time': 8
            },
            {
                'name': 'Poha',
                'price': 90,
                'description': 'Flattened rice with vegetables and peanuts',
                'section_id': breakfast_section.id if breakfast_section else None,
                'section': 'Breakfast',
                'subcategory': 'Maharashtrian',
                'is_available': True,
                'preparation_time': 10
            },
            {
                'name': 'Upma',
                'price': 85,
                'description': 'Semolina upma with vegetables',
                'section_id': breakfast_section.id if breakfast_section else None,
                'section': 'Breakfast',
                'subcategory': 'South Indian',
                'is_available': True,
                'preparation_time': 12
            },
            {
                'name': 'Chicken Biryani',
                'price': 400,
                'description': 'Aromatic chicken biryani with raita',
                'section_id': main_course_section.id if main_course_section else None,
                'section': 'Main Course',
                'subcategory': 'Mughlai',
                'is_available': True,
                'preparation_time': 25
            },
            {
                'name': 'Paneer Tikka',
                'price': 280,
                'description': 'Grilled paneer tikka with mint chutney',
                'section_id': starters_section.id if starters_section else None,
                'section': 'Starters',
                'subcategory': 'Vegetarian',
                'is_available': True,
                'preparation_time': 15
            },
            {
                'name': 'Gulab Jamun',
                'price': 120,
                'description': 'Sweet gulab jamun in sugar syrup',
                'section_id': desserts_section.id if desserts_section else None,
                'section': 'Desserts',
                'subcategory': 'Indian Sweets',
                'is_available': True,
                'preparation_time': 5
            },
            {
                'name': 'Masala Chai',
                'price': 50,
                'description': 'Spiced Indian tea with milk',
                'section_id': beverages_section.id if beverages_section else None,
                'section': 'Beverages',
                'subcategory': 'Hot Drinks',
                'is_available': True,
                'preparation_time': 5
            }
        ]
        
        for item_data in sample_menu_items:
            menu_item = FoodMenu(**item_data)
            db.session.add(menu_item)
        
        try:
            db.session.commit()
            print("Sample menu items added successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding sample menu items: {e}")
    
    # Add sample gallery images if they don't exist
    if not GalleryImage.query.first():
        sample_gallery_images = [
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
                'section': 'kitchen',
                'image_path': 'kitchen.jpg',
                'caption': 'Modern Kitchen',
                'alt_text': 'Fully equipped modern kitchen',
                'is_featured': False,
                'display_order': 4
            }
        ]
        
        for image_data in sample_gallery_images:
            gallery_image = GalleryImage(**image_data)
            db.session.add(gallery_image)
        
        try:
            db.session.commit()
            print("Sample gallery images added successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding sample gallery images: {e}")

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Password reset serializer
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Helper functions
def allowed_file(filename, allowed_extensions):
    """
    Check if the file has an allowed extension
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Register Jinja filters
@app.template_filter('format_number')
def format_number(value):
    """Format a number with thousands separator"""
    try:
        # Set locale to Indian format (for comma separators)
        locale.setlocale(locale.LC_ALL, 'en_IN')
        return locale.format_string("%d", int(value), grouping=True)
    except (ValueError, locale.Error):
        # Fallback to simple formatting if locale fails
        return "{:,}".format(int(value))
    finally:
        # Reset locale
        locale.setlocale(locale.LC_ALL, '')
        
@app.template_filter('format_time')
def format_time(value):
    """Format a time string (e.g., '14:00' to '2:00 PM')"""
    try:
        # Parse the time string
        if ':' in value:
            hours, minutes = map(int, value.split(':'))
            # Convert to 12-hour format
            period = 'AM' if hours < 12 else 'PM'
            hours = hours % 12
            if hours == 0:
                hours = 12
            return f"{hours}:{minutes:02d} {period}"
        return value
    except (ValueError, AttributeError):
        # Return the original value if parsing fails
        return value


def get_setting(key, default=None):
    """Get villa setting value"""
    setting = VillaSettings.query.filter_by(setting_key=key).first()
    return setting.setting_value if setting else default

@app.context_processor
def inject_settings():
    """Make settings available to all templates"""
    settings = {}
    try:
        for setting in VillaSettings.query.all():
            settings[setting.setting_key] = setting.setting_value
    except:
        # Handle case when database is not yet created
        pass
    return {'villa_settings': settings}

def create_notification(user_id, title, message, type='info'):
    """Create a notification for user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type
    )
    db.session.add(notification)
    db.session.commit()

def send_email(to_email, subject, body):
    """Send email notification"""
    try:
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        text = msg.as_string()
        server.sendmail(app.config['MAIL_USERNAME'], to_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        
        # Enhanced validation
        if len(password) < 6:
            flash('Password must be at least 6 characters long!')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match!')
            return render_template('register.html')
        
        existing_user = User.query.filter((User.username==username)|(User.email==email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists! Please choose a different username.')
            else:
                flash('Email already registered! Please use a different email or try logging in.')
            return render_template('register.html')
        
        hashed_pw = generate_password_hash(password)
        user = User(
            username=username, 
            email=email, 
            password_hash=hashed_pw,
            phone=phone,
            address=address,
            created_at=datetime.now(timezone.utc)
        )  
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email
        welcome_body = f"""
        <h2>Welcome to {get_setting('villa_name')}!</h2>
        <p>Thank you for registering with us. We're excited to have you as part of our community.</p>
        <p>You can now book your stay and enjoy our luxury amenities.</p>
        """
        try:
            if send_email(email, f"Welcome to {get_setting('villa_name')}", welcome_body):
                flash('Registration successful! Please login.')
            else:
                flash('Registration successful, but welcome email could not be sent. Please login.')
                app.logger.warning(f"Failed to send welcome email to {email}")
        except Exception as e:
            flash('Registration successful, but welcome email could not be sent. Please login.')
            app.logger.error(f"Welcome email error: {str(e)}")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Check if the remember me checkbox is checked
        remember_me = 'remember' in request.form
        
        # Enhanced login - support both username and email
        user = User.query.filter((User.username==username)|(User.email==username)).first()
        
        if not user:
            flash('No account found with that username or email. Please check your credentials or register.')
            return render_template('login.html')
            
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember_me)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            
            # Create a welcome back notification
            create_notification(
                user_id=user.id,
                title="Welcome back!",
                message=f"You last logged in on {user.last_login.strftime('%d %b %Y')}.",
                type="info"
            )
            
            # Get the next page from the request args, or default to index
            next_page = request.args.get('next')
            
            if user.is_admin:
                return redirect(next_page or url_for('admin_dashboard'))
            return redirect(next_page or url_for('index'))
        
        flash('Invalid password. Please try again.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/')
def index():
    try:
        # Get featured gallery images
        featured_images = GalleryImage.query.filter_by(is_featured=True).order_by(GalleryImage.display_order).limit(6).all()
    except:
        featured_images = []
    
    try:
        # Get recent reviews
        recent_reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).limit(3).all()
    except:
        recent_reviews = []
    
    try:
        # Get villa statistics
        total_bookings = Booking.query.count()
        total_reviews = Review.query.filter_by(is_approved=True).count()
        avg_rating = db.session.query(db.func.avg(Review.rating)).filter_by(is_approved=True).scalar() or 0
    except:
        total_bookings = 0
        total_reviews = 0
        avg_rating = 0
    
    # Get pricing from settings
    weekday_price = int(get_setting('weekday_price', 10000))
    weekend_price = int(get_setting('weekend_price', 15000))
    extended_stay_price = int(get_setting('extended_stay_price', 8500))
    
    return render_template('index.html', 
                         featured_images=featured_images,
                         recent_reviews=recent_reviews,
                         total_bookings=total_bookings,
                         total_reviews=total_reviews,
                         avg_rating=round(avg_rating, 1),
                         weekday_price=weekday_price,
                         weekend_price=weekend_price,
                         extended_stay_price=extended_stay_price)

@app.route('/gallery')
def gallery():
    try:
        # Get gallery images organized by sections
        gallery_sections = {}
        images = GalleryImage.query.order_by(GalleryImage.display_order).all()
        
        for image in images:
            section = image.section
            if section not in gallery_sections:
                gallery_sections[section] = []
            gallery_sections[section].append(image)
            
            # Add 4BHK images to their own section if they have the 4bhk tag
            if section == '4bhk' or getattr(image, 'tags', '').lower().find('4bhk') >= 0:
                if '4bhk' not in gallery_sections:
                    gallery_sections['4bhk'] = []
                if section != '4bhk':  # Avoid duplicates
                    gallery_sections['4bhk'].append(image)
    except Exception as e:
        app.logger.error(f"Error in gallery route: {str(e)}")
        gallery_sections = {}
    
    return render_template('gallery.html', gallery_sections=gallery_sections)

@app.route('/api/calculate-price', methods=['POST'])
def calculate_price():
    """Backend API to calculate booking price"""
    try:
        data = request.get_json()
        
        # Handle both date formats (from form and from API)
        try:
            if 'date_range' in data:
                # Format from JavaScript: "DD/MM/YYYY to DD/MM/YYYY"
                date_parts = data['date_range'].split(' to ')
                check_in = datetime.strptime(date_parts[0], '%d/%m/%Y').date()
                check_out = datetime.strptime(date_parts[1], '%d/%m/%Y').date()
            else:
                # Direct format: YYYY-MM-DD
                check_in = datetime.strptime(data['check_in'], '%Y-%m-%d').date()
                check_out = datetime.strptime(data['check_out'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
            
        # Get other parameters
        adults = int(data.get('adults', 1))
        children = int(data.get('children', 0))
        guests = adults + children
        villa_type = data.get('villa_type', 'standard')
        meal_plan = data.get('meal_plan', 'none')
        amenities = data.get('amenities', [])
        
        # Validate guest count
        max_guests = int(get_setting('max_guests', '20'))
        if guests > max_guests:
            return jsonify({'error': f'Maximum {max_guests} guests allowed'}), 400
        
        if check_out <= check_in:
            return jsonify({'error': 'Check-out date must be after check-in date'}), 400
        
        # Calculate nights
        nights = (check_out - check_in).days
        
        # Calculate price based on weekdays and weekends
        weekdays = 0
        weekends = 0
        current_date = check_in
        while current_date < check_out:
            if current_date.weekday() in [5, 6]:  # Saturday, Sunday
                weekends += 1
            else:
                weekdays += 1
            current_date += timedelta(days=1)
        
        # Get base prices
        weekday_price = int(get_setting('weekday_price', 10000))
        weekend_price = int(get_setting('weekend_price', 15000))
        
        # Villa type pricing
        villa_surcharges = {
            'standard': 1.0,
            'deluxe': 1.2,
            'premium': 1.5
        }
        
        # Calculate base price
        base_price = (weekdays * weekday_price + weekends * weekend_price) * villa_surcharges.get(villa_type, 1.0)
        
        # Add meal plan costs
        meal_costs = {
            'none': 0,
            'breakfast': 500,
            'half-board': 1000,
            'full-board': 1500
        }
        meal_cost = meal_costs.get(meal_plan, 0) * guests * nights
        
        # Add amenities costs
        amenity_costs = {
            'airport_transfer': 2000,
            'private_chef': 5000,
            'spa_service': 3000,
            'guided_tour': 4000
        }
        
        amenities_cost = sum(amenity_costs.get(amenity, 0) for amenity in amenities)
        
        # Calculate total price
        total_price = base_price + meal_cost + amenities_cost
        
        # Apply GST (18%)
        gst = total_price * 0.18
        final_price = total_price + gst
        
        return jsonify({
            'base_price': round(base_price),
            'meal_cost': round(meal_cost),
            'amenities_cost': round(amenities_cost),
            'subtotal': round(total_price),
            'gst': round(gst),
            'total_price': round(final_price),
            'nights': nights,
            'weekdays': weekdays,
            'weekends': weekends
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/booked-dates', methods=['GET'])
def get_booked_dates():
    """API endpoint to get all booked dates"""
    try:
        # Get all confirmed and pending bookings
        bookings = Booking.query.filter(
            Booking.status.in_(['confirmed', 'pending'])
        ).all()
        
        # Create a list of all booked dates
        booked_dates = []
        # Create a list of confirmed dates
        confirmed_dates = []
        
        for booking in bookings:
            current_date = booking.check_in
            while current_date < booking.check_out:
                date_str = current_date.strftime('%Y-%m-%d')
                booked_dates.append(date_str)
                
                # If booking is confirmed, add to confirmed dates as well
                if booking.status == 'confirmed':
                    confirmed_dates.append(date_str)
                    
                current_date += timedelta(days=1)
        
        return jsonify({
            'booked_dates': booked_dates,
            'confirmed_dates': confirmed_dates
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        check_in_str = request.form.get('check_in')
        check_out_str = request.form.get('check_out')
        adults = int(request.form.get('adults', 1))
        children = int(request.form.get('children', 0))
        villa_type = request.form.get('villa_type', 'standard')
        meal_plan = request.form.get('meal_plan', 'none')
        coupon_code = request.form.get('coupon_code', '').strip()
        special_requests = request.form.get('special_requests', '')
        
        try:
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format', 'error')
            weekday_price = int(get_setting('weekday_price', 10000))
            weekend_price = int(get_setting('weekend_price', 15000))
            extended_stay_price = int(get_setting('extended_stay_price', 8500))
            return render_template('booking.html',
                                   weekday_price=weekday_price,
                                   weekend_price=weekend_price,
                                   extended_stay_price=extended_stay_price)
        
        amenities = request.form.getlist('amenities[]')
        try:
            price_data = compute_booking_price(check_in, check_out, adults, children, villa_type, meal_plan, amenities, coupon_code)
        except ValueError as e:
            flash(str(e), 'error')
            weekday_price = int(get_setting('weekday_price', 10000))
            weekend_price = int(get_setting('weekend_price', 15000))
            extended_stay_price = int(get_setting('extended_stay_price', 8500))
            return render_template('booking.html',
                                   weekday_price=weekday_price,
                                   weekend_price=weekend_price,
                                   extended_stay_price=extended_stay_price)
        villa_display_names = {
            'standard': 'Standard Villa',
            'deluxe': 'Deluxe Villa',
            'premium': 'Premium Villa'
        }
        villa_display = villa_display_names.get(villa_type, 'Standard Villa')
        booking = Booking(
            user_id=current_user.id if current_user.is_authenticated else None,
            check_in=check_in,
            check_out=check_out,
            guests=price_data['guests'],
            adults=adults,
            children=children,
            villa_type=villa_display,
            meal_plan=meal_plan,
            amenities=json.dumps(amenities),
            base_price=price_data['base_price'],
            meal_cost=price_data['meal_plan_cost'],
            amenities_cost=price_data['amenities_cost'],
            subtotal=price_data['subtotal'],
            gst=price_data['tax_amount'],
            total_price=price_data['total_price'],
            status='pending',
            payment_status='pending',
            special_requests=special_requests,
            booking_date=datetime.now(timezone.utc)
        )
        if price_data.get('coupon'):
            booking.coupon_id = price_data['coupon'].id
            price_data['coupon'].times_used = (price_data['coupon'].times_used or 0) + 1
        db.session.add(booking)
        db.session.commit()
        session['confirmed_booking_id'] = booking.id
        if current_user.is_authenticated:
            return redirect(url_for('booking_payment', booking_id=booking.id))
        return redirect(url_for('booking_confirmation', booking_id=booking.id))
    
    # GET request - render the booking form
    weekday_price = int(get_setting('weekday_price', 10000))
    weekend_price = int(get_setting('weekend_price', 15000))
    extended_stay_price = int(get_setting('extended_stay_price', 8500))
    
    return render_template('booking.html', 
                          weekday_price=weekday_price,
                          weekend_price=weekend_price,
                          extended_stay_price=extended_stay_price)
    

def compute_booking_price(check_in, check_out, adults, children, villa_type, meal_plan, amenities, coupon_code):
    guests = adults + children
    max_guests = int(get_setting('max_guests', '20'))
    if guests > max_guests:
        raise ValueError(f'Maximum {max_guests} guests allowed')
    if check_out <= check_in:
        raise ValueError('Check-out date must be after check-in date')
    conflicting_bookings = Booking.query.filter(
        db.or_(
            db.and_(Booking.check_in <= check_in, Booking.check_out > check_in),
            db.and_(Booking.check_in < check_out, Booking.check_out >= check_out),
            db.and_(Booking.check_in >= check_in, Booking.check_out <= check_out)
        ),
        Booking.status.in_(['confirmed', 'pending'])
    ).first()
    if conflicting_bookings:
        raise ValueError('Villa is not available for selected dates')
    nights = (check_out - check_in).days
    weekdays = 0
    weekends = 0
    current_date = check_in
    while current_date < check_out:
        if current_date.weekday() in [5, 6]:
            weekends += 1
        else:
            weekdays += 1
        current_date += timedelta(days=1)
    weekday_price = int(get_setting('weekday_price', 10000))
    weekend_price = int(get_setting('weekend_price', 15000))
    villa_surcharges = {
        'standard': 0,
        'deluxe': 2000,
        'premium': 5000
    }
    villa_surcharge = villa_surcharges.get(villa_type, 0) * nights
    base_price = (weekdays * weekday_price) + (weekends * weekend_price)
    base_guests = 8
    additional_guest_fee = 500
    additional_guests = max(0, guests - base_guests)
    additional_guest_cost = 0
    if additional_guests > 0:
        additional_guest_cost = additional_guests * additional_guest_fee * nights
    normalized_meal_plan = (meal_plan or '').replace('-', '_')
    meal_plan_costs = {
        'none': 0,
        'breakfast': 500,
        'half_board': 800,
        'full_board': 1200
    }
    meal_plan_cost = meal_plan_costs.get(normalized_meal_plan, 0) * guests * nights
    amenities_set = set(amenities or [])
    amenities_cost = 0
    if 'private-chef' in amenities_set or 'private_chef' in amenities_set:
        amenities_cost += 4000 * nights
    if 'barbeque' in amenities_set:
        amenities_cost += 1000 * guests
    if 'flavored-smoked' in amenities_set:
        amenities_cost += 1000 * nights
    subtotal = base_price + villa_surcharge + additional_guest_cost + meal_plan_cost + amenities_cost
    discount = 0
    applied_coupon = None
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code.upper()).first()
        if coupon and coupon.is_active:
            today = datetime.now().date()
            if coupon.valid_from.date() <= today <= coupon.valid_until.date():
                if not coupon.max_uses or coupon.times_used < coupon.max_uses:
                    discount = int(subtotal * (coupon.discount_percentage / 100))
                    applied_coupon = coupon
    tax_rate = 0.18
    tax_amount = int((subtotal - discount) * tax_rate)
    total_price = subtotal - discount + tax_amount
    return {
        'guests': guests,
        'nights': nights,
        'weekdays': weekdays,
        'weekends': weekends,
        'base_price': base_price,
        'villa_type': villa_type,
        'villa_surcharge': villa_surcharge,
        'additional_guest_cost': additional_guest_cost,
        'meal_plan_cost': meal_plan_cost,
        'amenities_cost': amenities_cost,
        'subtotal': subtotal,
        'discount': discount,
        'tax_rate': tax_rate * 100,
        'tax_amount': tax_amount,
        'total_price': total_price,
        'coupon': applied_coupon
    }


@app.route('/api/calculate-price', methods=['POST'])
def calculate_booking_price():
    try:
        data = request.get_json() or {}
        try:
            check_in = datetime.strptime(data['check_in'], '%Y-%m-%d').date()
            check_out = datetime.strptime(data['check_out'], '%Y-%m-%d').date()
        except (KeyError, ValueError):
            return jsonify({'error': 'Invalid date format'}), 400
        adults = int(data.get('adults', 1))
        children = int(data.get('children', 0))
        villa_type = data.get('villa_type', 'standard')
        meal_plan = data.get('meal_plan', 'none')
        amenities = data.get('amenities', [])
        coupon_code = data.get('coupon_code', '')
        result = compute_booking_price(check_in, check_out, adults, children, villa_type, meal_plan, amenities, coupon_code)
        response = {k: v for k, v in result.items() if k != 'coupon'}
        if result.get('coupon'):
            response['coupon'] = {
                'code': result['coupon'].code,
                'discount_percentage': result['coupon'].discount_percentage
            }
        return jsonify(response)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error calculating price: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-promo', methods=['POST'])
def validate_promo():
    """API endpoint to validate promo codes"""
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        
        if not code:
            return jsonify({'valid': False, 'message': 'No promo code provided'})
        
        # Find the coupon in the database
        coupon = Coupon.query.filter_by(code=code).first()
        
        if not coupon:
            return jsonify({'valid': False, 'message': 'Invalid promo code'})
        
        # Check if coupon is active
        if not coupon.is_active:
            return jsonify({'valid': False, 'message': 'This promo code is no longer active'})
        
        # Check expiration
        if coupon.valid_until and coupon.valid_until < datetime.now().date():
            return jsonify({'valid': False, 'message': 'This promo code has expired'})
        
        # Check usage limit
        if coupon.max_uses and coupon.current_uses >= coupon.max_uses:
            return jsonify({'valid': False, 'message': 'This promo code has reached its usage limit'})
        
        # Coupon is valid
        discount_info = f"{coupon.discount_value}% off" if coupon.discount_type == 'percent' else f"₹{coupon.discount_value} off"
        
        return jsonify({
            'valid': True,
            'message': f'Promo code applied: {discount_info}',
            'discount_type': coupon.discount_type,
            'discount_value': coupon.discount_value
        })
        
    except Exception as e:
        app.logger.error(f"Error validating promo code: {str(e)}")
        return jsonify({'valid': False, 'message': f'Error: {str(e)}'}), 500        #meal_plan = request.form.get('meal_plan', 'none')
        coupon_code = request.form.get('coupon_code', '').strip()
        special_requests = request.form.get('special_requests', '')
        
        # Get selected amenities
        amenities = request.form.getlist('amenities')
        
        # Store booking data in session
        session['booking'] = {
            'check_in': check_in_str,
            'check_out': check_out_str,
            'adults': adults,
            'children': children,
            'villa_type': villa_type,
            'meal_plan': meal_plan,
            'coupon_code': coupon_code,
            'special_requests': special_requests,
            'amenities': amenities
        }
        
        # Redirect to booking details page
        return redirect(url_for('booking_details'))
    
    return render_template('booking.html')

@app.route('/booking/details', methods=['GET', 'POST'])
@login_required
def booking_details():
    # Check if we have booking details in session
    if 'booking_details' not in session:
        flash('Please select dates first')
        return redirect(url_for('booking'))
    
    booking_details = session['booking_details']
    
    # Pre-fill user data from registration if not already in session
    if 'name' not in booking_details:
        booking_details['name'] = current_user.username
    if 'email' not in booking_details:
        booking_details['email'] = current_user.email
    if 'phone' not in booking_details:
        booking_details['phone'] = current_user.phone
    
    # Step 2: Guest Details
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            special_requests = request.form.get('special_requests', '')
            
            # Update session with guest details
            booking_details.update({
                'name': name,
                'email': email,
                'phone': phone,
                'special_requests': special_requests
            })
            
            session['booking_details'] = booking_details
            
            # Proceed to step 3: Confirmation
            return redirect(url_for('booking_review'))
            
        except Exception as e:
            flash(f'Error processing guest details: {str(e)}')
            return render_template('booking_details.html', booking=booking_details)
    
    # GET request - show guest details form
    return render_template('booking_details.html', booking=booking_details)

@app.route('/booking/review', methods=['GET', 'POST'])
def booking_review():
    # Check if we have booking details in session
    if 'booking' not in session:
        flash('Please start the booking process again', 'error')
        return redirect(url_for('booking'))
    
    booking_details = session['booking']
    
    # Step 3: Review and Confirm
    if request.method == 'POST':
        try:
            # Create booking record
            check_in = datetime.strptime(booking_details['check_in'], '%Y-%m-%d').date()
            check_out = datetime.strptime(booking_details['check_out'], '%Y-%m-%d').date()
            
            # Calculate total guests
            total_guests = int(booking_details.get('adults', 1)) + int(booking_details.get('children', 0))
            
            # Create a new booking with only the core fields that definitely exist in the database
            booking = Booking(
                user_id=current_user.id if current_user.is_authenticated else None,
                check_in=check_in,
                check_out=check_out,
                guests=total_guests,
                total_price=booking_details['total_price'],
                special_requests=booking_details.get('special_requests', ''),
                status='confirmed',
                payment_status='pending'
            )
            
            db.session.add(booking)
            db.session.commit()
            
            # Now try to update with additional fields if they exist in the model
            # This is done in a separate transaction to ensure the booking is created
            try:
                # Try to update with additional fields
                db.session.execute(
                    """
                    UPDATE booking 
                    SET villa_type = :villa_type,
                        meal_plan = :meal_plan
                    WHERE id = :id
                    """,
                    {
                        'id': booking.id,
                        'villa_type': booking_details.get('villa_type', 'Standard Villa'),
                        'meal_plan': booking_details.get('meal_plan', 'none')
                    }
                )
                db.session.commit()
                app.logger.info(f"Updated booking {booking.id} with additional fields")
            except Exception as e:
                # If there's an error, make sure to rollback the session
                db.session.rollback()
                app.logger.warning(f"Could not update booking with additional fields: {str(e)}")
            
            # Clear session data
            session.pop('booking', None)
            
            # Store booking ID in session for confirmation page
            session['confirmed_booking_id'] = booking.id
            
            # Redirect directly to confirmation page
            return redirect(url_for('booking_confirmation', booking_id=booking.id))
            
        except Exception as e:
            flash(f'Error creating booking: {str(e)}', 'error')
            return render_template('booking_review.html', booking=booking_details)
    
    # GET request - show review page
    return render_template('booking_review.html', booking=booking_details)

@app.route('/booking/payment/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def booking_payment(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Ensure user owns this booking
    if booking.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    # If booking is already paid, redirect to confirmation
    if booking.payment_status == 'paid':
        return redirect(url_for('booking_confirmation', booking_id=booking.id))
    
    # Step 4: Payment
    if request.method == 'POST':
        try:
            payment_method = request.form.get('payment_method')
            transaction_id = request.form.get('transaction_id', '')
            upi_reference = request.form.get('upi_reference', '')
            
            # Create payment record
            payment = Payment(
                booking_id=booking.id,
                amount=booking.total_price,
                payment_method=payment_method,
                transaction_id=transaction_id,
                payment_date=datetime.now(timezone.utc),
                upi_id='9673340163@ptsbi',
                upi_reference=upi_reference
            )
            
            # Update booking status based on payment method
            if payment_method == 'cash':
                # For 'Pay at Property', keep payment status as pending
                payment.payment_status = 'pending'
                booking.payment_status = 'pending'
                booking.status = 'confirmed'  # Booking is confirmed but payment is pending
            else:
                # For other payment methods, mark as paid
                payment.payment_status = 'completed'
                booking.payment_status = 'paid'
                booking.status = 'confirmed'
            
            db.session.add(payment)
            db.session.commit()
            
            # Send confirmation email
            payment_status_text = "Payment Pending (Pay at Property)" if payment_method == 'cash' else "Paid"
            transaction_info = f"<li><strong>Transaction ID:</strong> {transaction_id}</li>" if transaction_id else ""
            
            email_body = f"""
            <h2>Booking Confirmation</h2>
            <p>Dear {current_user.username},</p>
            <p>Your booking has been confirmed!</p>
            <ul>
                <li><strong>Check-in:</strong> {booking.check_in.strftime('%d/%m/%Y')}</li>
                <li><strong>Check-out:</strong> {booking.check_out.strftime('%d/%m/%Y')}</li>
                <li><strong>Guests:</strong> {booking.guests}</li>
                <li><strong>Total Price:</strong> ₹{booking.total_price:,}</li>
                <li><strong>Payment Method:</strong> {payment_method.upper()}</li>
                <li><strong>Payment Status:</strong> {payment_status_text}</li>
                {transaction_info}
            </ul>
            {"<p>Please complete your payment during check-in.</p>" if payment_method == 'cash' else ""}
            <p>We look forward to hosting you!</p>
            """
            try:
                if send_email(current_user.email, "Booking Confirmation", email_body):
                    app.logger.info(f"Booking confirmation email sent to {current_user.email}")
                else:
                    app.logger.warning(f"Failed to send booking confirmation email to {current_user.email}")
            except Exception as e:
                app.logger.error(f"Booking confirmation email error: {str(e)}")
            
            # Create notification
            if payment_method == 'cash':
                create_notification(
                    current_user.id,
                    "Booking Confirmed - Payment Pending",
                    f"Your booking #{booking.id} has been confirmed. Please complete the payment of ₹{booking.total_price:,} during check-in.",
                    "info"
                )
            else:
                create_notification(
                    current_user.id,
                    "Payment Successful",
                    f"Your payment of ₹{booking.total_price:,} for booking #{booking.id} has been received. Your booking is now confirmed.",
                    "success"
                )
            
            # Clear session data
            if 'booking_details' in session:
                session.pop('booking_details')
            
            if payment_method == 'cash':
                flash('Booking confirmed! Payment will be collected during check-in.')
            else:
                flash('Payment successful! Your booking is confirmed.')
            return redirect(url_for('booking_confirmation', booking_id=booking.id))
            
        except Exception as e:
            flash(f'Error processing payment: {str(e)}')
            return render_template('booking_payment.html', booking=booking)
    
    # GET request - show payment page
    return render_template('booking_payment.html', booking=booking)

@app.route('/booking/confirmation/<int:booking_id>')
def booking_confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Allow access to the booking confirmation without login
    # Only check ownership if user is logged in
    if current_user.is_authenticated and booking.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    # Check if this is the booking we just created (using session)
    if not current_user.is_authenticated and 'confirmed_booking_id' not in session:
        # Only allow access to confirmed bookings for non-authenticated users
        flash('Booking not found or access denied.')
        return redirect(url_for('booking'))
    
    # Get payment details if available
    payment = Payment.query.filter_by(booking_id=booking.id).first()
    
    return render_template('booking_confirmation.html', booking=booking, payment=payment)

@app.route('/menu')
def menu():
    # Get all active menu sections
    sections = MenuSection.query.filter_by(is_active=True).order_by(MenuSection.display_order).all()
    
    # Get all menu items grouped by section
    items_by_section = {}
    for section in sections:
        items = FoodMenu.query.filter_by(section_id=section.id, is_available=True).all()
        items_by_section[section.id] = items
    
    # Create meal packages section data
    meal_packages = {
        'veg_packages': [
            {'id': 'vp1', 'name': 'Full Meal Plan – Veg (One Night Food Package)', 'price': 1450, 'description': 'Minimum 12 Pax required'},
            {'id': 'vp2', 'name': 'Full Meal Plan – Veg (Two Night Food Package)', 'price': 1250, 'description': 'Minimum 12 Pax required'},
            {'id': 'vp3', 'name': 'Half Meal Plan – Veg (One Night Food Package)', 'price': 1300, 'description': 'Minimum 12 Pax required'},
            {'id': 'vp4', 'name': 'Half Meal Plan – Veg (Two Night Food Package)', 'price': 1100, 'description': 'Minimum 12 Pax required'},
            {'id': 'vp5', 'name': 'Skip Lunch Package - Veg (Without Barbeque)', 'price': 900, 'description': 'Minimum 15 Pax required'},
            {'id': 'vp6', 'name': 'Skip Lunch Package - Veg (With Barbeque)', 'price': 1150, 'description': 'Minimum 15 Pax required'},
        ],
        'non_veg_packages': [
            {'id': 'nvp1', 'name': 'Full Meal Plan – Non-Veg (One Night Food Package)', 'price': 1500, 'description': 'Minimum 12 Pax required'},
            {'id': 'nvp2', 'name': 'Full Meal Plan – Non-Veg (Two Night Food Package)', 'price': 1400, 'description': 'Minimum 12 Pax required'},
            {'id': 'nvp3', 'name': 'Half Meal Plan – Non-Veg (One Night Food Package)', 'price': 1400, 'description': 'Minimum 12 Pax required'},
            {'id': 'nvp4', 'name': 'Half Meal Plan – Non-Veg (Two Night Food Package)', 'price': 1300, 'description': 'Minimum 12 Pax required'},
            {'id': 'nvp5', 'name': 'Skip Lunch Package - Non-Veg (Without Barbeque)', 'price': 1000, 'description': 'Minimum 15 Pax required'},
            {'id': 'nvp6', 'name': 'Skip Lunch Package - Non-Veg (With Barbeque)', 'price': 1200, 'description': 'Minimum 15 Pax required'},
        ]
    }
    
    # Create a la carte menu items by category
    a_la_carte = {
        'breakfast': [
            {'id': 'b1', 'name': 'Plain Bread', 'price': 15, 'veg': True},
            {'id': 'b2', 'name': 'Plain Toast', 'price': 30, 'veg': True},
            {'id': 'b3', 'name': 'Bread Butter', 'price': 50, 'veg': True},
            {'id': 'b4', 'name': 'Toast Butter', 'price': 60, 'veg': True},
            {'id': 'b5', 'name': 'Bread Jam', 'price': 50, 'veg': True},
            {'id': 'b6', 'name': 'Toast Jam', 'price': 60, 'veg': True},
            {'id': 'b7', 'name': 'Bread Butter Jam', 'price': 60, 'veg': True},
            {'id': 'b8', 'name': 'Toast Butter Jam', 'price': 70, 'veg': True},
            {'id': 'b9', 'name': 'Plain Maggie', 'price': 60, 'veg': True},
            {'id': 'b10', 'name': 'Vegetable Maggie', 'price': 70, 'veg': True},
            {'id': 'b11', 'name': 'Cheese Maggie', 'price': 80, 'veg': True},
            {'id': 'b12', 'name': 'Tadka Maggie', 'price': 80, 'veg': True},
            {'id': 'b13', 'name': 'Upma', 'price': 80, 'veg': True},
            {'id': 'b14', 'name': 'Poha', 'price': 80, 'veg': True},
            {'id': 'b15', 'name': 'Aloo Paratha', 'price': 110, 'veg': True},
            {'id': 'b16', 'name': 'Gobi Paratha', 'price': 110, 'veg': True},
            {'id': 'b17', 'name': 'Onion Paratha', 'price': 110, 'veg': True},
            {'id': 'b18', 'name': 'Mix Veg Paratha', 'price': 130, 'veg': True},
            {'id': 'b19', 'name': 'Paneer Paratha', 'price': 140, 'veg': True},
            {'id': 'b20', 'name': 'Puri Bhaji', 'price': 140, 'veg': True},
            {'id': 'b21', 'name': 'Chole Puri', 'price': 140, 'veg': True},
            {'id': 'b22', 'name': 'French Fries', 'price': 140, 'veg': True},
        ],
        'breakfast_eggs': [
            {'id': 'be1', 'name': 'Boiled Egg', 'price': 50, 'veg': False},
            {'id': 'be2', 'name': 'Plain Omelette', 'price': 80, 'veg': False},
            {'id': 'be3', 'name': 'Masala Omelette', 'price': 90, 'veg': False},
            {'id': 'be4', 'name': 'Egg Half Fry', 'price': 90, 'veg': False},
            {'id': 'be5', 'name': 'Scrambled Egg', 'price': 90, 'veg': False},
            {'id': 'be6', 'name': 'Egg Bhurji', 'price': 90, 'veg': False},
            {'id': 'be7', 'name': 'Cheese Omelette', 'price': 110, 'veg': False},
        ],
        'sandwiches': [
            {'id': 's1', 'name': 'Veg Club Sandwich', 'price': 80, 'veg': True},
            {'id': 's2', 'name': 'Veg Club Grilled Sandwich', 'price': 110, 'veg': True},
            {'id': 's3', 'name': 'Cheese Sandwich', 'price': 90, 'veg': True},
            {'id': 's4', 'name': 'Cheese Grilled Sandwich', 'price': 120, 'veg': True},
            {'id': 's5', 'name': 'Veg Cheese Sandwich', 'price': 100, 'veg': True},
            {'id': 's6', 'name': 'Veg Cheese Grilled Sandwich', 'price': 130, 'veg': True},
            {'id': 's7', 'name': 'Bombay Masala Sandwich', 'price': 120, 'veg': True},
            {'id': 's8', 'name': 'Bombay Masala Grilled Sandwich', 'price': 150, 'veg': True},
        ],
        'egg_sandwiches': [
            {'id': 'es1', 'name': 'Omelette Sandwich', 'price': 100, 'veg': False},
            {'id': 'es2', 'name': 'Omelette Grilled Sandwich', 'price': 130, 'veg': False},
            {'id': 'es3', 'name': 'Omelette Cheese Sandwich', 'price': 120, 'veg': False},
            {'id': 'es4', 'name': 'Omelette Cheese Grilled Sandwich', 'price': 150, 'veg': False},
        ],
        'beverages': [
            {'id': 'bv1', 'name': 'Tea', 'price': 30, 'veg': True},
            {'id': 'bv2', 'name': 'Lemon Tea', 'price': 30, 'veg': True},
            {'id': 'bv3', 'name': 'Coffee', 'price': 50, 'veg': True},
            {'id': 'bv4', 'name': 'Black Coffee', 'price': 30, 'veg': True},
            {'id': 'bv5', 'name': 'Hot Milk', 'price': 80, 'veg': True},
            {'id': 'bv6', 'name': 'Bournvita', 'price': 80, 'veg': True},
            {'id': 'bv7', 'name': 'Hot Chocolate', 'price': 90, 'veg': True},
            {'id': 'bv8', 'name': 'Green Tea', 'price': 40, 'veg': True},
        ],
        'veg_soups': [
            {'id': 'vs1', 'name': 'Veg Manchow Soup', 'price': 120, 'veg': True},
            {'id': 'vs2', 'name': 'Veg Hot N Sour Soup', 'price': 120, 'veg': True},
            {'id': 'vs3', 'name': 'Tomato Soup', 'price': 120, 'veg': True},
            {'id': 'vs4', 'name': 'Veg Clear Soup', 'price': 120, 'veg': True},
            {'id': 'vs5', 'name': 'Veg Coriander Soup', 'price': 120, 'veg': True},
            {'id': 'vs6', 'name': 'Veg Sweet Corn Soup', 'price': 120, 'veg': True},
        ],
        'non_veg_soups': [
            {'id': 'nvs1', 'name': 'Chicken Manchow Soup', 'price': 140, 'veg': False},
            {'id': 'nvs2', 'name': 'Chicken Hot N Sour Soup', 'price': 140, 'veg': False},
            {'id': 'nvs3', 'name': 'Chicken Clear Soup', 'price': 140, 'veg': False},
            {'id': 'nvs4', 'name': 'Cream Of Chicken Soup', 'price': 140, 'veg': False},
            {'id': 'nvs5', 'name': 'Chicken Coriander Soup', 'price': 140, 'veg': False},
        ],
        'veg_starters': [
            {'id': 'vst1', 'name': 'Veg Manchurian Dry', 'price': 190, 'veg': True},
            {'id': 'vst2', 'name': 'Veg 65', 'price': 190, 'veg': True},
            {'id': 'vst3', 'name': 'Veg Crispy', 'price': 190, 'veg': True},
            {'id': 'vst4', 'name': 'Veg Schezwan Dry', 'price': 190, 'veg': True},
            {'id': 'vst5', 'name': 'Veg Ching Pong', 'price': 190, 'veg': True},
            {'id': 'vst6', 'name': 'Veg Gold Coin', 'price': 190, 'veg': True},
            {'id': 'vst7', 'name': 'Paneer 65', 'price': 220, 'veg': True},
            {'id': 'vst8', 'name': 'Paneer Crispy', 'price': 220, 'veg': True},
            {'id': 'vst9', 'name': 'Paneer Manchurian Dry', 'price': 220, 'veg': True},
            {'id': 'vst10', 'name': 'Paneer Chilly Dry', 'price': 220, 'veg': True},
        ],
        'non_veg_starters': [
            {'id': 'nvst1', 'name': 'Chicken Chilly Dry', 'price': 250, 'veg': False},
            {'id': 'nvst2', 'name': 'Chicken Manchurian Dry', 'price': 250, 'veg': False},
            {'id': 'nvst3', 'name': 'Chicken 65', 'price': 250, 'veg': False},
            {'id': 'nvst4', 'name': 'Chicken Crispy', 'price': 250, 'veg': False},
            {'id': 'nvst5', 'name': 'Chicken Lollipop (8 Pieces)', 'price': 280, 'veg': False},
            {'id': 'nvst6', 'name': 'Chicken Lollipop Masala', 'price': 290, 'veg': False},
        ],
        'tandoor_veg': [
            {'id': 'tv1', 'name': 'Veg Sheek Kebab', 'price': 250, 'veg': True},
            {'id': 'tv2', 'name': 'Paneer Achari Tikka', 'price': 250, 'veg': True},
            {'id': 'tv3', 'name': 'Paneer Tikka', 'price': 250, 'veg': True},
            {'id': 'tv4', 'name': 'Tandoori Aloo', 'price': 250, 'veg': True},
            {'id': 'tv5', 'name': 'Paneer Pudina Tikka', 'price': 250, 'veg': True},
            {'id': 'tv6', 'name': 'Paneer Malai Tikka', 'price': 250, 'veg': True},
            {'id': 'tv7', 'name': 'Paneer Haryali Tikka', 'price': 250, 'veg': True},
            {'id': 'tv8', 'name': 'Tandoori Gobi', 'price': 250, 'veg': True},
        ],
        'tandoor_non_veg': [
            {'id': 'tnv1', 'name': 'Chicken Tikka', 'price': 250, 'veg': False},
            {'id': 'tnv2', 'name': 'Chicken Pahadi Kebab', 'price': 250, 'veg': False},
            {'id': 'tnv3', 'name': 'Chicken Malai Kebab', 'price': 250, 'veg': False},
            {'id': 'tnv4', 'name': 'Chicken Methi Kebab', 'price': 250, 'veg': False},
            {'id': 'tnv5', 'name': 'Chicken Seekh Kebab', 'price': 250, 'veg': False},
            {'id': 'tnv6', 'name': 'Tandoori Chicken Half', 'price': 250, 'veg': False},
            {'id': 'tnv7', 'name': 'Tandoori Chicken Full', 'price': 550, 'veg': False},
            {'id': 'tnv8', 'name': 'Chicken Achari Tikka', 'price': 250, 'veg': False},
            {'id': 'tnv9', 'name': 'Chicken Kasturi Kebab', 'price': 250, 'veg': False},
        ],
        'chinese_veg': [
            {'id': 'cv1', 'name': 'Veg Fried Rice', 'price': 220, 'veg': True},
            {'id': 'cv2', 'name': 'Veg Hakka Noodles', 'price': 220, 'veg': True},
            {'id': 'cv3', 'name': 'Veg Schezwan Rice', 'price': 220, 'veg': True},
            {'id': 'cv4', 'name': 'Veg Schezwan Noodles', 'price': 220, 'veg': True},
            {'id': 'cv5', 'name': 'Veg Triple Fried Rice', 'price': 220, 'veg': True},
            {'id': 'cv6', 'name': 'Veg Hong Kong Rice', 'price': 220, 'veg': True},
            {'id': 'cv7', 'name': 'Veg Hong Kong Noodles', 'price': 220, 'veg': True},
        ],
        'chinese_non_veg': [
            {'id': 'cnv1', 'name': 'Chicken Fried Rice', 'price': 250, 'veg': False},
            {'id': 'cnv2', 'name': 'Chicken Schezwan Rice', 'price': 250, 'veg': False},
            {'id': 'cnv3', 'name': 'Chicken Hakka Noodles', 'price': 250, 'veg': False},
            {'id': 'cnv4', 'name': 'Chicken Schezwan Noodles', 'price': 250, 'veg': False},
            {'id': 'cnv5', 'name': 'Chicken Triple Rice', 'price': 250, 'veg': False},
            {'id': 'cnv6', 'name': 'Chicken Hong Kong Rice', 'price': 250, 'veg': False},
            {'id': 'cnv7', 'name': 'Chicken Hong Kong Noodles', 'price': 250, 'veg': False},
        ],
        'dal': [
            {'id': 'd1', 'name': 'Dal Fry', 'price': 150, 'veg': True},
            {'id': 'd2', 'name': 'Dal Tadka', 'price': 180, 'veg': True},
            {'id': 'd3', 'name': 'Dal Kolhapuri', 'price': 180, 'veg': True},
            {'id': 'd4', 'name': 'Dal Butter Tadka', 'price': 180, 'veg': True},
            {'id': 'd5', 'name': 'Dal Makhani', 'price': 180, 'veg': True},
        ],
        'indian_veg': [
            {'id': 'iv1', 'name': 'Palak Paneer', 'price': 220, 'veg': True},
            {'id': 'iv2', 'name': 'Panner Butter Masala', 'price': 220, 'veg': True},
            {'id': 'iv3', 'name': 'Paneer Kadhai', 'price': 220, 'veg': True},
            {'id': 'iv4', 'name': 'Paneer Handi', 'price': 220, 'veg': True},
            {'id': 'iv5', 'name': 'Paneer Do Payzza', 'price': 220, 'veg': True},
            {'id': 'iv6', 'name': 'Paneer Mutter', 'price': 220, 'veg': True},
            {'id': 'iv7', 'name': 'Paneer Kolhapuri', 'price': 220, 'veg': True},
            {'id': 'iv8', 'name': 'Paneer Pasanda', 'price': 250, 'veg': True},
            {'id': 'iv9', 'name': 'Mix Veg', 'price': 190, 'veg': True},
            {'id': 'iv10', 'name': 'Veg Kadhai', 'price': 190, 'veg': True},
            {'id': 'iv11', 'name': 'Veg Handi', 'price': 190, 'veg': True},
            {'id': 'iv12', 'name': 'Aloo Jeera Dry', 'price': 180, 'veg': True},
            {'id': 'iv13', 'name': 'Aloo Gobi Mutter Dry', 'price': 180, 'veg': True},
            {'id': 'iv14', 'name': 'Veg Kofta Curry', 'price': 190, 'veg': True},
            {'id': 'iv15', 'name': 'Aloo Mutter', 'price': 160, 'veg': True},
            {'id': 'iv16', 'name': 'Mushroom Masala', 'price': 180, 'veg': True},
            {'id': 'iv17', 'name': 'Mushroom Tikka Masala', 'price': 190, 'veg': True},
        ]
    }
    
    return render_template('menu.html', 
                          sections=sections, 
                          items_by_section=items_by_section,
                          meal_packages=meal_packages,
                          a_la_carte=a_la_carte)

@app.route('/cart')
@login_required
def cart():
    """Display the cart page"""
    return render_template('cart.html')

@app.route('/update-cart', methods=['POST'])
@csrf.exempt
def update_cart():
    if not current_user.is_authenticated:
        # Store cart in session for non-authenticated users
        session['cart'] = request.json.get('cart', [])
        return jsonify({'status': 'success', 'message': 'Cart updated in session'})
    
    # For authenticated users, update the database
    cart_data = request.json.get('cart', [])
    
    # Clear existing cart items for this user
    FoodOrder.query.filter_by(user_id=current_user.id, status='cart').delete()
    
    # Add new cart items
    for item in cart_data:
        menu_item = FoodMenu.query.get(item['id'])
        if menu_item:
            order = FoodOrder(
                user_id=current_user.id,
                menu_id=item['id'],
                quantity=item['quantity'],
                status='cart'
            )
            db.session.add(order)
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Cart updated in database'})

@app.route('/api/user/active-bookings')
@login_required
def get_active_bookings():
    """Get active bookings for the current user"""
    try:
        # Get user's active bookings (confirmed or pending)
        bookings = Booking.query.filter_by(
            user_id=current_user.id
        ).filter(
            Booking.status.in_(['confirmed', 'pending']),
            Booking.check_out >= datetime.now().date()
        ).order_by(Booking.check_in.asc()).all()
        
        bookings_data = [{
            'id': booking.id,
            'room_type': booking.room_type,
            'check_in_date': booking.check_in.strftime('%d %b, %Y'),
            'check_out_date': booking.check_out.strftime('%d %b, %Y'),
            'guests': booking.guests,
            'status': booking.status
        } for booking in bookings]
        
        return jsonify({'success': True, 'bookings': bookings_data})
    except Exception as e:
        app.logger.error(f"Error fetching active bookings: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to fetch bookings', 'error': str(e)}), 500

@app.route('/api/order', methods=['POST'])
@login_required
def api_order():
    """API endpoint for placing orders from the cart"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data!'}), 400
            
        if 'items' not in data or not data['items']:
            return jsonify({'success': False, 'message': 'No items in cart!'}), 400
        
        booking_id = data.get('booking_id')
        if not booking_id:
            return jsonify({'success': False, 'message': 'No booking selected!'}), 400
        
        # Verify booking belongs to user and is active
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found!'}), 404
            
        if booking.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Invalid booking selected!'}), 403
            
        if booking.status not in ['confirmed', 'pending']:
            return jsonify({'success': False, 'message': 'Booking is not active!'}), 400
        
        special_instructions = data.get('special_instructions', '')
        items = data['items']
        total_price = 0
        order_items = []
        
        # Calculate total and validate items
        for item_data in items:
            item_id = item_data.get('id')
            if not item_id:
                return jsonify({'success': False, 'message': 'Invalid item data!'}), 400
                
            quantity = int(item_data.get('quantity', 1))
            if quantity <= 0:
                return jsonify({'success': False, 'message': 'Invalid quantity!'}), 400
            
            menu_item = FoodMenu.query.get(item_id)
            if not menu_item:
                return jsonify({'success': False, 'message': f'Item with ID {item_id} not found!'}), 404
                
            if not menu_item.is_available:
                return jsonify({'success': False, 'message': f'Item {menu_item.name} is not available!'}), 400
            
            item_total = menu_item.price * quantity
            total_price += item_total
            order_items.append({
                'id': item_id,
                'name': menu_item.name,
                'price': menu_item.price,
                'quantity': quantity,
                'total': item_total
            })
        
        # Create food order
        food_order = FoodOrder(
            user_id=current_user.id,
            booking_id=booking_id,
            items=json.dumps(order_items),
            total_price=total_price,
            special_instructions=special_instructions
        )
        db.session.add(food_order)
        db.session.commit()
        
        # Create notification
        create_notification(
            current_user.id,
            "Order Placed",
            f"Your food order of ₹{total_price:,} has been placed successfully.",
            "success"
        )
        
        return jsonify({
            'success': True, 
            'message': 'Order placed successfully!',
            'order_id': food_order.id
        })
        
    except ValueError as e:
        app.logger.error(f"Value error in order: {str(e)}")
        return jsonify({'success': False, 'message': 'Invalid data format!'}), 400
    except Exception as e:
        app.logger.error(f"Error placing order: {str(e)}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred. Please try again.'}), 500

@app.route('/order', methods=['POST'])
@login_required
def order():
    """Legacy order endpoint for direct orders from menu page"""
    try:
        items_data = request.form.get('items')
        special_instructions = request.form.get('special_instructions', '')
        
        if not items_data:
            flash('No items selected!')
            return redirect(url_for('menu'))
        
        items = json.loads(items_data)
        total_price = 0
        order_items = []
        
        # Calculate total and validate items
        for item_id, quantity in items.items():
            menu_item = FoodMenu.query.get(item_id)
            if not menu_item or not menu_item.is_available:
                flash(f'Item {menu_item.name if menu_item else item_id} is not available!')
                return redirect(url_for('menu'))
            
            item_total = menu_item.price * quantity
            total_price += item_total
            order_items.append({
                'id': item_id,
                'name': menu_item.name,
                'price': menu_item.price,
                'quantity': quantity,
                'total': item_total
            })
        
        # Find latest booking for user
        booking = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).first()
        if not booking:
            flash('No active booking found! Please book your stay first.')
            return redirect(url_for('menu'))
        
        # Create food order
        food_order = FoodOrder(
            user_id=current_user.id,
            booking_id=booking.id,
            items=json.dumps(order_items),
            total_price=total_price,
            special_instructions=special_instructions
        )
        db.session.add(food_order)
        db.session.commit()
        
        # Create notification
        create_notification(
            current_user.id,
            "Order Placed",
            f"Your food order of ₹{total_price:,} has been placed successfully.",
            "success"
        )
        
        flash('Order placed successfully!')
        return redirect(url_for('profile'))
        
    except Exception as e:
        flash(f'Error placing order: {str(e)}')
        return redirect(url_for('menu'))

@app.route('/profile')
@login_required
def profile():
    try:
        # Get user's bookings
        bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    except:
        bookings = []
    
    try:
        # Get user's orders
        orders = FoodOrder.query.filter_by(user_id=current_user.id).order_by(FoodOrder.timestamp.desc()).all()
    except:
        orders = []
    
    try:
        # Get user's reviews
        reviews = Review.query.filter_by(user_id=current_user.id).order_by(Review.created_at.desc()).all()
    except:
        reviews = []
    
    try:
        # Get unread notifications
        notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).all()
    except:
        notifications = []
    
    return render_template('profile.html', 
                         user=current_user,
                         bookings=bookings,
                         orders=orders,
                         reviews=reviews,
                         notifications=notifications)

@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username or email already exists for another user
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email),
            User.id != current_user.id
        ).first()
        
        if existing_user:
            flash('Username or email already exists!')
            return redirect(url_for('profile'))
        
        # Update user information
        current_user.username = username
        current_user.email = email
        
        # Update password if provided
        if password and password.strip():
            current_user.password_hash = generate_password_hash(password)
        
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))
    
    return redirect(url_for('profile'))

@app.route('/profile/upload_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    if 'profile_pic' not in request.files:
        flash('No file part')
        return redirect(url_for('profile'))
    
    file = request.files['profile_pic']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('profile'))
    
    if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg', 'gif'}):
        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(app.static_folder, 'uploads')
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
        
        # Generate secure filename
        filename = secure_filename(file.filename)
        # Add timestamp to filename to avoid duplicates
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        
        # Save the file
        file_path = os.path.join(uploads_dir, filename)
        file.save(file_path)
        
        # Update user profile picture in database
        current_user.profile_pic = filename
        db.session.commit()
        
        flash('Profile picture updated successfully!')
    else:
        flash('Invalid file type. Please upload an image file (png, jpg, jpeg, gif).')
    
    return redirect(url_for('profile'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form.get('phone', '')
        subject = request.form.get('subject', 'General Inquiry')
        message = request.form['message']
        
        contact = Contact(
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            message=message
        )
        db.session.add(contact)
        db.session.commit()
        
        # Send confirmation email
        email_body = f"""
        <h2>Thank you for contacting us!</h2>
        <p>Dear {name},</p>
        <p>We have received your message and will get back to you soon.</p>
        <p><strong>Your message:</strong></p>
        <p>{message}</p>
        """
        try:
            if send_email(email, "Message Received", email_body):
                flash('Message sent successfully! We will get back to you soon.')
            else:
                flash('Message received, but confirmation email could not be sent.')
                app.logger.warning(f"Failed to send contact confirmation email to {email}")
        except Exception as e:
            flash('Message received, but confirmation email could not be sent.')
            app.logger.error(f"Contact confirmation email error: {str(e)}")
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/contact-us')
def contact_us():
    # This route will render the standalone contact page that matches the image
    return render_template('standalone_contact.html')

@app.route('/review/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def review(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        rating = int(request.form['rating'])
        comment = request.form.get('comment', '')
        
        # Check if review already exists
        existing_review = Review.query.filter_by(booking_id=booking_id).first()
        if existing_review:
            flash('You have already reviewed this booking!')
            return redirect(url_for('profile'))
        
        review = Review(
            user_id=current_user.id,
            booking_id=booking_id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()
        
        flash('Review submitted successfully!')
        return redirect(url_for('profile'))
    
    return render_template('review.html', booking=booking)

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    
    try:
        # Get statistics
        total_users = User.query.count()
        # Only count confirmed bookings
        total_bookings = Booking.query.filter_by(status='confirmed').count()
        total_orders = FoodOrder.query.count()
        # Only sum revenue from confirmed bookings
        total_revenue = db.session.query(db.func.sum(Booking.total_price)).filter(Booking.status == 'confirmed').scalar() or 0
        
        # Recent activities
        recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
        recent_orders = FoodOrder.query.order_by(FoodOrder.timestamp.desc()).limit(5).all()
        recent_contacts = Contact.query.filter_by(status='unread').order_by(Contact.created_at.desc()).limit(5).all()
    except:
        total_users = 0
        total_bookings = 0
        total_orders = 0
        total_revenue = 0
        recent_bookings = []
        recent_orders = []
        recent_contacts = []
    
    return render_template('admin/admin_dashboard.html',
                         total_users=total_users,
                         total_bookings=total_bookings,
                         total_orders=total_orders,
                         total_revenue=total_revenue,
                         recent_bookings=recent_bookings,
                         recent_orders=recent_orders,
                         recent_contacts=recent_contacts)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/admin_users.html', users=users)

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    if not current_user.is_admin:
        abort(403)
    
    # Get status filter from query parameters
    status_filter = request.args.get('status')
    search_query = request.args.get('search', '')
    date_filter = request.args.get('date_filter', 'all')
    
    # Start with base query
    query = Booking.query
    
    # Apply status filter if provided
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Apply search filter if provided
    if search_query:
        # Join with User table to search by username or email
        query = query.join(User).filter(
            db.or_(
                Booking.id.like(f'%{search_query}%'),
                User.username.like(f'%{search_query}%'),
                User.email.like(f'%{search_query}%')
            )
        )
    
    # Apply date filter if provided
    today = datetime.now().date()
    if date_filter == 'upcoming':
        query = query.filter(Booking.check_in >= today)
    elif date_filter == 'past':
        query = query.filter(Booking.check_out < today)
    elif date_filter == 'today':
        query = query.filter(
            db.or_(
                Booking.check_in == today,
                Booking.check_out == today,
                db.and_(Booking.check_in <= today, Booking.check_out >= today)
            )
        )
    elif date_filter == 'this_week':
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        query = query.filter(
            db.or_(
                db.and_(Booking.check_in >= start_of_week, Booking.check_in <= end_of_week),
                db.and_(Booking.check_out >= start_of_week, Booking.check_out <= end_of_week),
                db.and_(Booking.check_in <= start_of_week, Booking.check_out >= end_of_week)
            )
        )
    elif date_filter == 'this_month':
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        query = query.filter(
            db.or_(
                db.and_(Booking.check_in >= start_of_month, Booking.check_in <= end_of_month),
                db.and_(Booking.check_out >= start_of_month, Booking.check_out <= end_of_month),
                db.and_(Booking.check_in <= start_of_month, Booking.check_out >= end_of_month)
            )
        )
    
    # Get final results ordered by creation date
    bookings = query.order_by(Booking.created_at.desc()).all()
    
    # Get booking counts by status
    total_bookings = Booking.query.count()
    pending_count = Booking.query.filter_by(status='pending').count()
    confirmed_count = Booking.query.filter_by(status='confirmed').count()
    cancelled_count = Booking.query.filter_by(status='cancelled').count()
    
    booking_stats = {
        'total': total_bookings,
        'pending': pending_count,
        'confirmed': confirmed_count,
        'cancelled': cancelled_count
    }
    
    return render_template('admin/admin_bookings.html', bookings=bookings, booking_stats=booking_stats)

@app.route('/admin/bookings/calendar')
@login_required
def admin_bookings_calendar():
    if not current_user.is_admin:
        abort(403)
    
    # Get all confirmed bookings
    bookings = Booking.query.filter_by(status='confirmed').all()
    
    # Format bookings for calendar display
    calendar_events = []
    for booking in bookings:
        user = User.query.get(booking.user_id)
        calendar_events.append({
            'id': booking.id,
            'title': f'{user.username} - {booking.guests} guests',
            'start': booking.check_in.strftime('%Y-%m-%d'),
            'end': booking.check_out.strftime('%Y-%m-%d'),
            'color': '#4CAF50'  # Green for confirmed bookings
        })
    
    # Add pending bookings with different color
    pending_bookings = Booking.query.filter_by(status='pending').all()
    for booking in pending_bookings:
        user = User.query.get(booking.user_id)
        calendar_events.append({
            'id': booking.id,
            'title': f'{user.username} - {booking.guests} guests (Pending)',
            'start': booking.check_in.strftime('%Y-%m-%d'),
            'end': booking.check_out.strftime('%Y-%m-%d'),
            'color': '#FFC107'  # Yellow for pending bookings
        })
    
    return render_template('admin/admin_bookings_calendar.html', calendar_events=calendar_events)

# Export CSV route moved to the bottom of the file

@app.route('/admin/update-menu-from-images', methods=['GET', 'POST'])
@login_required
def admin_update_menu_from_images():
    if not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        try:
            # Clear all existing menu items
            FoodMenu.query.delete()
            db.session.commit()
            
            # Create or get sections based on the uploaded images
            sections = {
                'breakfast': create_or_get_section('Breakfast', 'Breakfast', 'fas fa-coffee', 1),
                'breakfast_eggs': create_or_get_section('Break Fast With Eggs', 'Break Fast With Eggs', 'fas fa-egg', 2),
                'sandwich': create_or_get_section('Sandwich', 'Sandwich', 'fas fa-bread-slice', 3),
                'hot_beverages': create_or_get_section('Hot Beverages', 'Hot Beverages', 'fas fa-mug-hot', 4),
                'veg_soups': create_or_get_section('Veg Soups', 'Veg Soups', 'fas fa-utensils', 5),
                'non_veg_soups': create_or_get_section('Non-Veg Soups', 'Non-Veg Soups', 'fas fa-drumstick-bite', 6),
                'veg_chinese_starter': create_or_get_section('Veg Chinese Starter', 'Veg Chinese Starter', 'fas fa-utensils', 7),
                'non_veg_chinese_starter': create_or_get_section('Non-Veg Chinese Starter', 'Non-Veg Chinese Starter', 'fas fa-drumstick-bite', 8),
                'chinese_veg': create_or_get_section('Chinese Main Course Veg', 'Chinese Main Course Veg', 'fas fa-utensils', 9),
                'chinese_non_veg': create_or_get_section('Chinese Main Course Non-Veg', 'Chinese Main Course Non-Veg', 'fas fa-drumstick-bite', 10),
                'indian_veg': create_or_get_section('Indian Main Course Veg', 'Indian Main Course Veg', 'fas fa-utensils', 11),
                'indian_non_veg': create_or_get_section('Indian Main Course Non-Veg', 'Indian Main Course Non-Veg', 'fas fa-drumstick-bite', 12),
                'rice_biryani': create_or_get_section('Rice And Dum Biryani Veg/Non-Veg', 'Rice And Dum Biryani', 'fas fa-seedling', 13),
                'papad_salad': create_or_get_section('Papad And Salad', 'Papad And Salad', 'fas fa-leaf', 14),
                'quick_bite': create_or_get_section('Quick Bite', 'Quick Bite', 'fas fa-hamburger', 15),
                'cold_drinks': create_or_get_section('Cold Drinks', 'Cold Drinks', 'fas fa-glass-whiskey', 16),
                'desserts': create_or_get_section('Desserts', 'Desserts', 'fas fa-ice-cream', 17)
            }
            
            # Add menu items from the images
            # Breakfast items
            add_menu_items(sections['breakfast'].id, 'Breakfast', [
                {'name': 'Plain Bread', 'price': 15},
                {'name': 'Plain Toast', 'price': 30},
                {'name': 'Bread Butter', 'price': 50},
                {'name': 'Toast Butter', 'price': 60},
                {'name': 'Bread Jam', 'price': 50},
                {'name': 'Toast Jam', 'price': 60},
                {'name': 'Bread Butter Jam', 'price': 60},
                {'name': 'Toast Butter Jam', 'price': 70},
                {'name': 'Cream Apple', 'price': 80},
                {'name': 'Upma', 'price': 80},
                {'name': 'Poha', 'price': 80},
                {'name': 'Aloo Paratha', 'price': 110},
                {'name': 'Gobi Paratha', 'price': 110},
                {'name': 'Onion Paratha', 'price': 110},
                {'name': 'Paneer Paratha', 'price': 140},
                {'name': 'Fresh Fries', 'price': 140}
            ])
            
            # Breakfast with Eggs
            add_menu_items(sections['breakfast_eggs'].id, 'Break Fast With Eggs', [
                {'name': 'Boiled Egg', 'price': 50},
                {'name': 'Scrambled Egg', 'price': 90},
                {'name': 'Egg Bhurji', 'price': 90},
                {'name': 'Egg Half Fry', 'price': 90},
                {'name': 'Plain Omelette', 'price': 80},
                {'name': 'Masala Omelette', 'price': 90},
                {'name': 'Cheese Omelette', 'price': 110}
            ])
            
            # Sandwich
            add_menu_items(sections['sandwich'].id, 'Sandwich', [
                {'name': 'Veg Club Sandwich', 'price': 80},
                {'name': 'Cheese Sandwich', 'price': 90},
                {'name': 'Veg Cheese Sandwich', 'price': 100},
                {'name': 'Cheese Grilled Sandwich', 'price': 120},
                {'name': 'Veg Club Grilled Sandwich', 'price': 110},
                {'name': 'Veg Cheese Grilled Sandwich', 'price': 130},
                {'name': 'Bombay Masala Sandwich', 'price': 120},
                {'name': 'Bombay Masala Grilled Sandwich', 'price': 150}
            ])
            
            # Hot Beverages
            add_menu_items(sections['hot_beverages'].id, 'Hot Beverages', [
                {'name': 'Tea', 'price': 30},
                {'name': 'Lemon Tea', 'price': 30},
                {'name': 'Coffee', 'price': 30},
                {'name': 'Black Coffee', 'price': 30},
                {'name': 'Hot Milk', 'price': 40},
                {'name': 'Bournvita', 'price': 60},
                {'name': 'Horlicks', 'price': 60},
                {'name': 'Green Tea', 'price': 40}
            ])
            
            # Veg Soups
            add_menu_items(sections['veg_soups'].id, 'Veg Soups', [
                {'name': 'Tomato Soup', 'price': 100},
                {'name': 'Veg Clear Soup', 'price': 100},
                {'name': 'Sweet Corn Soup', 'price': 110},
                {'name': 'Veg Hot & Sour Soup', 'price': 110},
                {'name': 'Veg Manchow Soup', 'price': 110},
                {'name': 'Veg Noodle Soup', 'price': 120}
            ])
            
            # Non-Veg Soups
            add_menu_items(sections['non_veg_soups'].id, 'Non-Veg Soups', [
                {'name': 'Chicken Clear Soup', 'price': 120},
                {'name': 'Chicken Sweet Corn Soup', 'price': 130},
                {'name': 'Chicken Hot & Sour Soup', 'price': 130},
                {'name': 'Chicken Manchow Soup', 'price': 130},
                {'name': 'Chicken Noodle Soup', 'price': 140}
            ])
            
            # Veg Chinese Starter
            add_menu_items(sections['veg_chinese_starter'].id, 'Veg Chinese Starter', [
                {'name': 'Veg Manchurian Dry', 'price': 180},
                {'name': 'Veg Salt & Pepper', 'price': 180},
                {'name': 'Veg Chilli', 'price': 180},
                {'name': 'Veg 65', 'price': 180},
                {'name': 'Paneer Chilli Dry', 'price': 200},
                {'name': 'Paneer 65', 'price': 200},
                {'name': 'Paneer Salt & Pepper', 'price': 200},
                {'name': 'Mushroom Chilli', 'price': 200},
                {'name': 'Mushroom 65', 'price': 200},
                {'name': 'Mushroom Salt & Pepper', 'price': 200},
                {'name': 'Gobi Manchurian', 'price': 180},
                {'name': 'Gobi 65', 'price': 180},
                {'name': 'Honey Chilli Potato', 'price': 180},
                {'name': 'Crispy Veg', 'price': 180},
                {'name': 'Crispy Baby Corn', 'price': 200},
                {'name': 'Crispy Corn Salt & Pepper', 'price': 200}
            ])
            
            # Non-Veg Chinese Starter
            add_menu_items(sections['non_veg_chinese_starter'].id, 'Non-Veg Chinese Starter', [
                {'name': 'Chicken Lollipop', 'price': 210},
                {'name': 'Chicken Drums of Heaven', 'price': 250},
                {'name': 'Chicken Chilli', 'price': 210},
                {'name': 'Chicken 65', 'price': 210},
                {'name': 'Chicken Salt & Pepper', 'price': 210},
                {'name': 'Chicken Manchurian', 'price': 210},
                {'name': 'Chicken Crispy', 'price': 210}
            ])
            
            # Chinese Main Course Veg
            add_menu_items(sections['chinese_veg'].id, 'Chinese Main Course Veg', [
                {'name': 'Veg Manchurian Gravy', 'price': 200},
                {'name': 'Veg Chilli Gravy', 'price': 200},
                {'name': 'Mix Veg in Hot Garlic', 'price': 200},
                {'name': 'Veg Hong Kong', 'price': 200},
                {'name': 'Veg Schezwan', 'price': 200},
                {'name': 'Paneer Chilli Gravy', 'price': 220},
                {'name': 'Paneer Manchurian Gravy', 'price': 220}
            ])
            
            # Chinese Main Course Non-Veg
            add_menu_items(sections['chinese_non_veg'].id, 'Chinese Main Course Non-Veg', [
                {'name': 'Chicken Manchurian Gravy', 'price': 220},
                {'name': 'Chicken Chilli Gravy', 'price': 220},
                {'name': 'Chicken Hot Garlic', 'price': 220},
                {'name': 'Chicken Hong Kong', 'price': 220},
                {'name': 'Chicken Schezwan', 'price': 220}
            ])
            
            # Indian Main Course Veg
            add_menu_items(sections['indian_veg'].id, 'Indian Main Course Veg', [
                {'name': 'Malai Kofta', 'price': 220},
                {'name': 'Paneer Butter Masala', 'price': 220},
                {'name': 'Paneer Tikka Masala', 'price': 220},
                {'name': 'Kadai Paneer', 'price': 220},
                {'name': 'Shahi Paneer', 'price': 220},
                {'name': 'Mutter Paneer', 'price': 220},
                {'name': 'Paneer Pasanda', 'price': 220},
                {'name': 'Paneer Bhurji', 'price': 220},
                {'name': 'Mix Veg', 'price': 180},
                {'name': 'Veg Kolhapuri', 'price': 180},
                {'name': 'Veg Jaipuri', 'price': 180},
                {'name': 'Veg Handi', 'price': 180},
                {'name': 'Veg Kofta', 'price': 180},
                {'name': 'Veg Makhanwala', 'price': 180},
                {'name': 'Mexican Salsa Masala', 'price': 180}
            ])
            
            # Indian Main Course Non-Veg
            add_menu_items(sections['indian_non_veg'].id, 'Indian Main Course Non-Veg', [
                {'name': 'Butter Chicken With Bone (Half)', 'price': 300},
                {'name': 'Butter Chicken With Bone (Full)', 'price': 550},
                {'name': 'Butter Chicken Boneless (Half)', 'price': 300},
                {'name': 'Butter Chicken Boneless (Full)', 'price': 550},
                {'name': 'Chicken Kadai', 'price': 300},
                {'name': 'Chicken Handi', 'price': 300},
                {'name': 'Chicken Tikka Masala', 'price': 300},
                {'name': 'Chicken Masala', 'price': 300},
                {'name': 'Chicken Kolhapuri', 'price': 300},
                {'name': 'Chicken Chettinad', 'price': 300}
            ])
            
            # Rice And Dum Biryani
            add_menu_items(sections['rice_biryani'].id, 'Rice And Dum Biryani', [
                {'name': 'Steamed Rice', 'price': 130},
                {'name': 'Jeera Rice', 'price': 150},
                {'name': 'Veg Pulao', 'price': 180},
                {'name': 'Veg Biryani', 'price': 200},
                {'name': 'Paneer Biryani', 'price': 220},
                {'name': 'Egg Biryani', 'price': 220},
                {'name': 'Chicken Dum Biryani (Half)', 'price': 300},
                {'name': 'Chicken Dum Biryani (Full)', 'price': 500}
            ])
            
            # Papad And Salad
            add_menu_items(sections['papad_salad'].id, 'Papad And Salad', [
                {'name': 'Roasted Papad', 'price': 20},
                {'name': 'Masala Papad', 'price': 30},
                {'name': 'Fry Papad', 'price': 20},
                {'name': 'Green Salad', 'price': 60}
            ])
            
            # Quick Bite
            add_menu_items(sections['quick_bite'].id, 'Quick Bite', [
                {'name': 'Plain Maggi', 'price': 60},
                {'name': 'Masala Maggi', 'price': 70},
                {'name': 'Cheese Maggi', 'price': 80},
                {'name': 'Veg Maggi', 'price': 80},
                {'name': 'Chicken Maggi', 'price': 100}
            ])
            
            # Cold Drinks
            add_menu_items(sections['cold_drinks'].id, 'Cold Drinks', [
                {'name': 'Mineral Water', 'price': 20},
                {'name': 'Aerated Drinks', 'price': 40},
                {'name': 'Fresh Lime', 'price': 40},
                {'name': 'Fresh Lime Soda', 'price': 50},
                {'name': 'Cold Coffee', 'price': 80},
                {'name': 'Cold Coffee with Ice Cream', 'price': 100}
            ])
            
            # Desserts
            add_menu_items(sections['desserts'].id, 'Desserts', [
                {'name': 'Vanilla', 'price': 100},
                {'name': 'Strawberry', 'price': 100},
                {'name': 'Butterscotch', 'price': 100},
                {'name': 'Chocolate', 'price': 100},
                {'name': 'Tutti Frutti', 'price': 100}
            ])
            {'name': 'Coffee', 'price': 50},
            {'name': 'Black Coffee', 'price': 30},
            {'name': 'Hot Milk', 'price': 80},
            {'name': 'Bournvita', 'price': 80},
            {'name': 'Hot Chocolate', 'price': 90},
            {'name': 'Green Tea', 'price': 40}
        
            
            # Add more menu items for other sections...
            # Veg Soups
            add_menu_items(sections['veg_soups'].id, 'Veg Soups', [
                {'name': 'Veg Manchow Soup', 'price': 120},
                {'name': 'Veg Hot N Sour Soup', 'price': 120},
                {'name': 'Tomato Soup', 'price': 120},
                {'name': 'Veg Clear Soup', 'price': 120},
                {'name': 'Veg Coriander Soup', 'price': 120},
                {'name': 'Veg Sweet Corn Soup', 'price': 120}
            ])
            
            # Non-Veg Soups
            add_menu_items(sections['non_veg_soups'].id, 'Non-Veg Soups', [
                {'name': 'Chicken Manchow Soup', 'price': 140},
                {'name': 'Chicken Hot N Sour Soup', 'price': 140},
                {'name': 'Chicken Clear Soup', 'price': 140},
                {'name': 'Cream Of Chicken Soup', 'price': 140},
                {'name': 'Chicken Coriander Soup', 'price': 140}
            ])
            
            # Continue with other sections...
            
            flash('Menu updated successfully from images!')
            return redirect(url_for('admin_menu'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating menu: {str(e)}', 'error')
            return redirect(url_for('admin_menu'))
    
    return render_template('admin/update_menu_from_images.html')

def create_or_get_section(name, display_name, icon, order):
    """Create a menu section if it doesn't exist, or get it if it does"""
    section = MenuSection.query.filter_by(name=name).first()
    if not section:
        section = MenuSection(
            name=name,
            display_name=display_name,
            icon=icon,
            display_order=order,
            is_active=True
        )
        db.session.add(section)
        db.session.commit()
    return section

def add_menu_items(section_id, section_name, items):
    """Add menu items to a section"""
    for item in items:
        # Check if item already exists
        existing = FoodMenu.query.filter_by(name=item['name'], section_id=section_id).first()
        if not existing:
            menu_item = FoodMenu(
                name=item['name'],
                price=item['price'],
                description=item.get('description', ''),
                section_id=section_id,
                section=section_name,
                is_available=True
            )
            db.session.add(menu_item)
    db.session.commit()

@app.route('/admin/menu')
@login_required
def admin_menu():
    if not current_user.is_admin:
        abort(403)
    return render_template('admin/admin_menu.html')

@app.route('/api/menu-items')
@login_required
def api_menu_items():
    if not current_user.is_admin:
        abort(403)
    
    # Get all menu items with their section information
    menu_items = db.session.query(
        FoodMenu.id, 
        FoodMenu.name, 
        FoodMenu.price, 
        FoodMenu.description,
        FoodMenu.is_veg,
        FoodMenu.section_id,
        MenuSection.name.label('section_name')
    ).join(MenuSection, FoodMenu.section_id == MenuSection.id).all()
    
    # Convert to list of dictionaries
    items_list = []
    for item in menu_items:
        items_list.append({
            'id': item.id,
            'name': item.name,
            'price': item.price,
            'description': item.description,
            'is_veg': item.is_veg,
            'section_id': item.section_id,
            'section_name': item.section_name
        })
    
    return jsonify(items_list)

@app.route('/api/menu-sections')
@login_required
def api_menu_sections():
    if not current_user.is_admin:
        abort(403)
    
    # Get all menu sections
    sections = MenuSection.query.all()
    
    # Convert to list of dictionaries
    sections_list = []
    for section in sections:
        sections_list.append({
            'id': section.id,
            'name': section.name
        })
    
    return jsonify(sections_list)

@app.route('/api/update-menu-item', methods=['POST'])
@login_required
def api_update_menu_item():
    if not current_user.is_admin:
        abort(403)
    
    item_id = request.form.get('item_id')
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description', '')
    is_veg = request.form.get('type') == 'veg'
    section_id = request.form.get('section_id')
    
    if not all([item_id, name, price, section_id]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # Update the menu item
    menu_item = FoodMenu.query.get(item_id)
    if not menu_item:
        return jsonify({'success': False, 'message': 'Menu item not found'}), 404
    
    menu_item.name = name
    menu_item.price = int(price)
    menu_item.description = description
    menu_item.is_veg = is_veg
    menu_item.section_id = section_id
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Menu item updated successfully'})

@app.route('/api/delete-menu-item/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)
    
    # Delete the menu item
    menu_item = FoodMenu.query.get(item_id)
    if not menu_item:
        return jsonify({'success': False, 'message': 'Menu item not found'}), 404
    
    db.session.delete(menu_item)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Menu item deleted successfully'})

@app.route('/admin/menu/add', methods=['GET', 'POST'])
@login_required
def admin_add_menu_item():
    if not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        name = request.form['name']
        price = int(request.form['price'])
        description = request.form.get('description', '')
        section_id = request.form.get('section_id')
        subcategory = request.form.get('subcategory', '')
        preparation_time = int(request.form.get('preparation_time', 15))
        
        # Get section name for backward compatibility
        section_name = 'General'
        if section_id:
            section = MenuSection.query.get(section_id)
            if section:
                section_name = section.name
        
        menu_item = FoodMenu(
            name=name,
            price=price,
            description=description,
            section_id=section_id,
            section=section_name,
            subcategory=subcategory,
            preparation_time=preparation_time
        )
        db.session.add(menu_item)
        db.session.commit()
        
        flash('Menu item added successfully!')
        return redirect(url_for('admin_menu'))
    
    sections = MenuSection.query.filter_by(is_active=True).order_by(MenuSection.display_order).all()
    return render_template('admin/admin_menu_form.html', action='Add', sections=sections)

@app.route('/admin/menu/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)
    item = FoodMenu.query.get_or_404(item_id)
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.price = int(request.form.get('price'))
        item.description = request.form.get('description', '')
        section_id = request.form.get('section_id')
        item.subcategory = request.form.get('subcategory', '')
        item.preparation_time = int(request.form.get('preparation_time', 15))
        item.is_available = 'is_available' in request.form
        
        # Update section
        if section_id:
            section = MenuSection.query.get(section_id)
            if section:
                item.section_id = section_id
                item.section = section.name
        
        db.session.commit()
        flash('Menu item updated successfully!')
        return redirect(url_for('admin_menu'))
    
    sections = MenuSection.query.filter_by(is_active=True).order_by(MenuSection.display_order).all()
    return render_template('admin/admin_menu_form.html', action='Edit', item=item, sections=sections)

@app.route('/admin/menu/delete/<int:item_id>', methods=['POST'])
@login_required
def admin_delete_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)
    item = FoodMenu.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Menu item deleted successfully!')
    return redirect(url_for('admin_menu'))

@app.route('/admin/toggle-menu-item/<int:item_id>', methods=['POST'])
@login_required
def admin_toggle_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)
    item = FoodMenu.query.get_or_404(item_id)
    item.is_available = not item.is_available
    db.session.commit()
    status = "available" if item.is_available else "unavailable"
    flash(f'Menu item "{item.name}" is now {status}!')
    return redirect(url_for('admin_menu'))
    if not current_user.is_admin:
        abort(403)
    item = FoodMenu.query.get_or_404(item_id)
    item.is_available = not item.is_available
    db.session.commit()
    status = "available" if item.is_available else "unavailable"
    flash(f'Menu item "{item.name}" is now {status}!')
    return redirect(url_for('admin_menu'))

@app.route('/admin/sections')
@login_required
def admin_sections():
    if not current_user.is_admin:
        abort(403)
    sections = MenuSection.query.order_by(MenuSection.display_order).all()
    return render_template('admin/admin_sections.html', sections=sections)

@app.route('/admin/sections/add', methods=['GET', 'POST'])
@login_required
def admin_add_section():
    if not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        name = request.form['name']
        display_name = request.form['display_name']
        description = request.form.get('description', '')
        icon = request.form.get('icon', 'fas fa-utensils')
        display_order = int(request.form.get('display_order', 0))
        
        section = MenuSection(
            name=name,
            display_name=display_name,
            description=description,
            icon=icon,
            display_order=display_order
        )
        db.session.add(section)
        db.session.commit()
        
        flash('Menu section added successfully!')
        return redirect(url_for('admin_sections'))
    
    return render_template('admin/admin_section_form.html', action='Add')

@app.route('/admin/sections/edit/<int:section_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_section(section_id):
    if not current_user.is_admin:
        abort(403)
    section = MenuSection.query.get_or_404(section_id)
    if request.method == 'POST':
        section.name = request.form.get('name')
        section.display_name = request.form.get('display_name')
        section.description = request.form.get('description', '')
        section.icon = request.form.get('icon', 'fas fa-utensils')
        section.display_order = int(request.form.get('display_order', 0))
        section.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('Menu section updated successfully!')
        return redirect(url_for('admin_sections'))
    
    return render_template('admin/admin_section_form.html', action='Edit', section=section)

@app.route('/admin/sections/delete/<int:section_id>', methods=['POST'])
@login_required
def admin_delete_section(section_id):
    if not current_user.is_admin:
        abort(403)
    section = MenuSection.query.get_or_404(section_id)
    
    # Check if section has menu items
    if section.menu_items:
        flash('Cannot delete section that has menu items. Please move or delete the items first.')
        return redirect(url_for('admin_sections'))
    
    db.session.delete(section)
    db.session.commit()
    flash('Menu section deleted successfully!')
    return redirect(url_for('admin_sections'))

@app.route('/admin/sections/toggle/<int:section_id>', methods=['POST'])
@login_required
def admin_toggle_section(section_id):
    if not current_user.is_admin:
        abort(403)
    section = MenuSection.query.get_or_404(section_id)
    
    # Toggle the is_active status
    section.is_active = not section.is_active
    db.session.commit()
    
    status = "enabled" if section.is_active else "disabled"
    flash(f'Menu section "{section.display_name}" {status} successfully!')
    return redirect(url_for('admin_menu'))

@app.route('/admin/menu/assign-section/<int:item_id>', methods=['GET', 'POST'])
@login_required
def admin_assign_section(item_id):
    if not current_user.is_admin:
        abort(403)
    item = FoodMenu.query.get_or_404(item_id)
    sections = MenuSection.query.filter_by(is_active=True).order_by(MenuSection.display_order).all()
    
    if request.method == 'POST':
        section_id = request.form.get('section_id')
        if section_id:
            section = MenuSection.query.get(section_id)
            if section:
                item.section_id = section_id
                item.section = section.name  # Update for backward compatibility
                db.session.commit()
                flash(f'Menu item "{item.name}" assigned to section "{section.display_name}" successfully!')
                return redirect(url_for('admin_menu'))
        
        flash('Please select a valid section.')
    
    return render_template('admin/admin_assign_section.html', item=item, sections=sections)

@app.route('/admin/gallery')
@login_required
def admin_gallery():
    if not current_user.is_admin:
        abort(403)
    images = GalleryImage.query.order_by(GalleryImage.display_order).all()
    return render_template('admin/admin_gallery.html', images=images)

@app.route('/admin/gallery/add', methods=['POST'])
@login_required
def admin_add_gallery_image():
    if not current_user.is_admin:
        abort(403)
    
    # Check if image file was uploaded
    if 'image' not in request.files:
        flash('No image file uploaded', 'error')
        return redirect(url_for('admin_gallery'))
        
    image_file = request.files['image']
    if image_file.filename == '':
        flash('No image selected', 'error')
        return redirect(url_for('admin_gallery'))
    
    # Process the image file
    if image_file and allowed_file(image_file.filename, {'jpg', 'jpeg', 'png', 'gif'}):
        # Secure the filename and save the file
        filename = secure_filename(image_file.filename)
        # Create a unique filename to avoid overwriting
        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'gallery', unique_filename)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save the file
        image_file.save(file_path)
        
        # Get the relative path for storage in the database
        relative_path = os.path.join('gallery', unique_filename).replace('\\', '/')
        
        section = request.form['section']
        caption = request.form.get('caption', '')
        alt_text = request.form.get('alt_text', '')
        is_featured = 'is_featured' in request.form
        display_order = int(request.form.get('display_order', 1))
        tags = request.form.get('tags', '')
        
        # Check if we're editing an existing image
        image_id = request.form.get('image_id')
        if image_id and image_id.strip():
            # Update existing image
            image = GalleryImage.query.get(image_id)
            if image:
                # If updating an existing image, delete the old file if it exists
                if image.image_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], image.image_path)):
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image.image_path))
                    except Exception as e:
                        app.logger.error(f"Error deleting old image: {e}")
                
                image.section = section
                image.image_path = relative_path
                image.caption = caption
                image.alt_text = alt_text
                image.is_featured = is_featured
                image.display_order = display_order
                image.tags = tags
                flash('Gallery image updated successfully!', 'success')
            else:
                flash('Image not found', 'error')
                return redirect(url_for('admin_gallery'))
        else:
            # Create new image
            image = GalleryImage(
                section=section,
                image_path=relative_path,
                caption=caption,
                alt_text=alt_text,
                is_featured=is_featured,
                display_order=display_order,
                tags=tags
            )
            db.session.add(image)
            flash('Gallery image added successfully!', 'success')
        
        db.session.commit()
        return redirect(url_for('admin_gallery'))
    else:
        flash('Invalid file type. Allowed types: jpg, jpeg, png, gif', 'error')
        return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery/delete/<int:image_id>', methods=['POST'])
@login_required
def admin_delete_gallery_image(image_id):
    if not current_user.is_admin:
        abort(403)
    
    image = GalleryImage.query.get_or_404(image_id)
    
    # Delete the image file if it exists
    if image.image_path:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], image.image_path)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                app.logger.error(f"Error deleting image file: {e}")
    
    # Delete the database record
    db.session.delete(image)
    db.session.commit()
    
    flash('Gallery image deleted successfully!', 'success')
    return redirect(url_for('admin_gallery'))

@app.route('/admin/gallery/update-order', methods=['POST'])
@login_required
def admin_update_gallery_order():
    if not current_user.is_admin:
        abort(403)
    
    image_id = request.form.get('image_id')
    new_order = request.form.get('display_order')
    
    if not image_id or not new_order:
        return jsonify({'success': False, 'message': 'Missing required parameters'}), 400
    
    try:
        image_id = int(image_id)
        new_order = int(new_order)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid parameters'}), 400
    
    image = GalleryImage.query.get(image_id)
    if not image:
        return jsonify({'success': False, 'message': 'Image not found'}), 404
    
    image.display_order = new_order
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Display order updated successfully'})

@app.route('/admin/gallery/get-image/<int:image_id>', methods=['GET'])
@login_required
def admin_get_gallery_image(image_id):
    if not current_user.is_admin:
        abort(403)
    
    image = GalleryImage.query.get(image_id)
    if not image:
        return jsonify({'success': False, 'message': 'Image not found'}), 404
    
    # Convert the image object to a dictionary
    image_data = {
        'id': image.id,
        'section': image.section,
        'image_path': image.image_path,
        'caption': image.caption,
        'alt_text': image.alt_text,
        'is_featured': image.is_featured,
        'display_order': image.display_order,
        'tags': image.tags
    }
    
    return jsonify({'success': True, 'image': image_data})

@app.route('/admin/contacts')
@login_required
def admin_contacts():
    if not current_user.is_admin:
        abort(403)
    
    # Get contacts with additional statistics
    contacts = Contact.query.order_by(Contact.created_at.desc()).all()
    
    # Calculate statistics
    total_contacts = len(contacts)
    unread_contacts = len([c for c in contacts if c.status == 'unread'])
    read_contacts = len([c for c in contacts if c.status == 'read'])
    replied_contacts = len([c for c in contacts if c.status == 'replied'])
    
    # Get recent contacts (last 7 days)
    from datetime import timedelta
    recent_date = datetime.now(timezone.utc) - timedelta(days=7)
    # Make sure we're comparing datetimes with the same timezone awareness
    recent_contacts = len([c for c in contacts if (c.created_at.replace(tzinfo=timezone.utc) if not c.created_at.tzinfo else c.created_at) >= recent_date])
    
    stats = {
        'total': total_contacts,
        'unread': unread_contacts,
        'read': read_contacts,
        'replied': replied_contacts,
        'recent': recent_contacts
    }
    
    return render_template('admin/admin_contacts.html', contacts=contacts, stats=stats)

@app.route('/admin/reply_contact/<int:contact_id>', methods=['POST'])
@login_required
def admin_reply_contact(contact_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    contact = Contact.query.get_or_404(contact_id)
    reply_message = request.form['reply_message']
    
    # Send reply email
    email_body = f"""
    <h2>Reply to your inquiry</h2>
    <p>Dear {contact.name},</p>
    <p>{reply_message}</p>
    <p>Best regards,<br>The Royal Chalet Team</p>
    """
    
    try:
        if send_email(contact.email, f"Re: {contact.subject}", email_body):
            contact.status = 'replied'
            contact.replied_at = datetime.now(timezone.utc)
            db.session.commit()
            app.logger.info(f"Admin reply sent to {contact.email}")
            
            # Get updated statistics
            total_contacts = Contact.query.count()
            unread_contacts = Contact.query.filter_by(status='unread').count()
            read_contacts = Contact.query.filter_by(status='read').count()
            replied_contacts = Contact.query.filter_by(status='replied').count()
            recent_contacts = Contact.query.filter(Contact.created_at >= (datetime.now() - timedelta(days=7))).count()
            
            stats = {
                'total': total_contacts,
                'unread': unread_contacts,
                'read': read_contacts,
                'replied': replied_contacts,
                'recent': recent_contacts
            }
            
            return jsonify({
                'success': True,
                'message': 'Reply sent successfully!',
                'stats': stats
            })
        else:
            app.logger.warning(f"Failed to send admin reply to {contact.email}")
            return jsonify({
                'success': False,
                'message': 'Error sending reply email! Please check the email configuration.'
            })
    except Exception as e:
        app.logger.error(f"Admin reply email error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error sending reply email: {str(e)}'
        })

@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
@login_required
def get_contact_details(contact_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    contact = Contact.query.get_or_404(contact_id)
    
    # Mark as read if it was unread
    if contact.status == 'unread':
        contact.status = 'read'
        db.session.commit()
    
    return jsonify({
        'id': contact.id,
        'name': contact.name,
        'email': contact.email,
        'phone': contact.phone,
        'subject': contact.subject,
        'message': contact.message,
        'status': contact.status,
        'created_at': contact.created_at.strftime('%B %d, %Y at %I:%M %p'),
        'replied_at': contact.replied_at.strftime('%B %d, %Y at %I:%M %p') if contact.replied_at else None
    })

@app.route('/api/contacts/<int:contact_id>/mark-read', methods=['POST'])
@login_required
def mark_contact_as_read(contact_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    contact = Contact.query.get_or_404(contact_id)
    contact.status = 'read'
    db.session.commit()
    
    # Get updated statistics
    total_contacts = Contact.query.count()
    unread_contacts = Contact.query.filter_by(status='unread').count()
    read_contacts = Contact.query.filter_by(status='read').count()
    replied_contacts = Contact.query.filter_by(status='replied').count()
    recent_contacts = Contact.query.filter(Contact.created_at >= (datetime.now() - timedelta(days=7))).count()
    
    stats = {
        'total': total_contacts,
        'unread': unread_contacts,
        'read': read_contacts,
        'replied': replied_contacts,
        'recent': recent_contacts
    }
    
    return jsonify({
        'success': True,
        'stats': stats
    })

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    """Admin settings page"""
    if request.method == 'POST':
        try:
            # Process existing settings
            for key in request.form:
                if key != 'csrf_token':
                    setting = VillaSettings.query.filter_by(setting_key=key).first()
                    if setting:
                        setting.setting_value = request.form[key]
                    else:
                        setting = VillaSettings(setting_key=key, setting_value=request.form[key])
                        db.session.add(setting)
            
            # Process new settings for guest pricing
            max_guests = request.form.get('max_guests', '20')
            base_guests = request.form.get('base_guests', '8')
            additional_guest_fee = request.form.get('additional_guest_fee', '500')
            
            # Save the settings
            update_setting('max_guests', max_guests)
            update_setting('base_guests', base_guests)
            update_setting('additional_guest_fee', additional_guest_fee)
            
            # Update email configuration from database settings
            update_email_config_from_db()
            
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('admin_settings'))
            
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')
    
    # Get all settings
    settings = {}
    for setting in VillaSettings.query.all():
        settings[setting.setting_key] = setting.setting_value
    
    return render_template('admin/admin_settings.html', settings=settings)

# User management routes
@app.route('/admin/users/promote/<int:user_id>', methods=['POST'])
@login_required
def admin_promote_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f'User {user.username} promoted to admin.')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/demote/<int:user_id>', methods=['POST'])
@login_required
def admin_demote_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot demote yourself.')
        return redirect(url_for('admin_users'))
    user.is_admin = False
    db.session.commit()
    flash(f'User {user.username} demoted from admin.')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.')
        return redirect(url_for('admin_users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} deleted.')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/new', methods=['GET', 'POST'])
@login_required
def admin_add_user():
    if not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        is_admin = 'is_admin' in request.form
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            db.or_(
                User.username == username,
                User.email == email
            )
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists. Please choose a different username.', 'error')
            else:
                flash('Email already exists. Please use a different email address.', 'error')
            return render_template('admin/admin_user_form.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_admin,
            phone=phone,
            address=address,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'User {username} created successfully!', 'success')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/admin_user_form.html')

@app.route('/admin/users/export')
@login_required
def admin_export_users():
    if not current_user.is_admin:
        abort(403)
    
    # Get search query if provided
    search_query = request.args.get('search', '')
    
    # Start with base query
    query = User.query
    
    # Apply search filter if provided
    if search_query:
        query = query.filter(
            db.or_(
                User.username.like(f'%{search_query}%'),
                User.email.like(f'%{search_query}%')
            )
        )
    
    # Get users ordered by creation date
    users = query.order_by(User.created_at.desc()).all()
    
    # Create a StringIO object to write CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['User ID', 'Username', 'Email', 'Role', 'Phone', 'Address', 'Created At', 'Last Login'])
    
    # Write data rows
    for user in users:
        writer.writerow([
            user.id,
            user.username,
            user.email,
            'Administrator' if user.is_admin else 'User',
            user.phone or '',
            user.address or '',
            user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else '',
            user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else ''
        ])
    
    # Set up response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=royal_chalet_users_{timestamp}.csv'
        }
    )

@app.route('/admin/bookings/confirm/<int:booking_id>', methods=['POST'])
@login_required
def admin_confirm_booking(booking_id):
    if not current_user.is_admin:
        abort(403)
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.status == 'pending':
        booking.status = 'confirmed'
        db.session.commit()
        
        # Create notification for user
        create_notification(
            booking.user_id,
            "Booking Confirmed",
            f"Your booking from {booking.check_in.strftime('%d/%m/%Y')} to {booking.check_out.strftime('%d/%m/%Y')} has been confirmed.",
            "success"
        )
        
        flash(f'Booking {booking.id} confirmed successfully.')
    else:
        flash(f'Booking {booking.id} could not be confirmed. Current status: {booking.status}')
    
    return redirect(url_for('admin_bookings'))

@app.route('/admin/bookings/cancel/<int:booking_id>', methods=['POST'])
@login_required
def admin_cancel_booking(booking_id):
    if not current_user.is_admin:
        abort(403)
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'cancelled'
    db.session.commit()
    
    # Create notification for user
    create_notification(
        booking.user_id,
        "Booking Cancelled",
        f"Your booking from {booking.check_in.strftime('%d/%m/%Y')} to {booking.check_out.strftime('%d/%m/%Y')} has been cancelled.",
        "warning"
    )
    
    flash(f'Booking {booking.id} cancelled.')
    return redirect(url_for('admin_bookings'))

@app.route('/api/validate-coupon', methods=['POST'])
def validate_coupon():
    data = request.json
    coupon_code = data.get('coupon_code', '').strip().upper()
    
    if not coupon_code:
        return jsonify({'valid': False, 'message': 'Please enter a valid coupon code'})
    
    # Query the database for the coupon
    coupon = Coupon.query.filter_by(code=coupon_code).first()
    
    # Check if coupon exists and is valid
    if not coupon:
        return jsonify({'valid': False, 'message': 'Invalid coupon code'})
    
    if not coupon.is_active:
        return jsonify({'valid': False, 'message': 'This coupon is no longer active'})
    
    today = datetime.now().date()
    if today < coupon.valid_from.date() or today > coupon.valid_until.date():
        return jsonify({'valid': False, 'message': 'This coupon is not valid for the current date'})
    
    if coupon.max_uses and coupon.times_used >= coupon.max_uses:
        return jsonify({'valid': False, 'message': 'This coupon has reached its maximum usage limit'})
    
    # Coupon is valid
    return jsonify({
        'valid': True,
        'discount_percentage': coupon.discount_percentage,
        'message': f'Coupon applied: {coupon.discount_percentage}% discount'
    })

@app.route('/admin/coupons')
@login_required
@admin_required
def admin_coupons():
    coupons = Coupon.query.all()
    current_date = datetime.now().date()
    return render_template('admin/admin_coupons.html', coupons=coupons, current_date=current_date)

@app.route('/admin/coupons/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_coupon():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        discount_percentage = request.form.get('discount_percentage', type=int)
        valid_from = datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d')
        valid_until = datetime.strptime(request.form.get('valid_until'), '%Y-%m-%d')
        max_uses = request.form.get('max_uses', type=int)
        is_active = 'is_active' in request.form
        description = request.form.get('description', '').strip()
        
        # Validate input
        if not code or not discount_percentage:
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('admin_add_coupon'))
        
        if discount_percentage < 1 or discount_percentage > 100:
            flash('Discount percentage must be between 1 and 100', 'error')
            return redirect(url_for('admin_add_coupon'))
        
        if valid_until < valid_from:
            flash('End date must be after start date', 'error')
            return redirect(url_for('admin_add_coupon'))
        
        # Check if coupon code already exists
        existing_coupon = Coupon.query.filter_by(code=code).first()
        if existing_coupon:
            flash('A coupon with this code already exists', 'error')
            return redirect(url_for('admin_add_coupon'))
        
        # Create new coupon
        new_coupon = Coupon(
            code=code,
            discount_percentage=discount_percentage,
            valid_from=valid_from,
            valid_until=valid_until,
            max_uses=max_uses,
            is_active=is_active,
            description=description
        )
        
        db.session.add(new_coupon)
        db.session.commit()
        
        flash('Coupon created successfully', 'success')
        return redirect(url_for('admin_coupons'))
    
    return render_template('admin/admin_coupon_form.html', coupon=None)

@app.route('/admin/coupons/edit/<int:coupon_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        discount_percentage = request.form.get('discount_percentage', type=int)
        valid_from = datetime.strptime(request.form.get('valid_from'), '%Y-%m-%d')
        valid_until = datetime.strptime(request.form.get('valid_until'), '%Y-%m-%d')
        max_uses = request.form.get('max_uses', type=int)
        is_active = 'is_active' in request.form
        description = request.form.get('description', '').strip()
        
        # Validate input
        if not code or not discount_percentage:
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
        
        if discount_percentage < 1 or discount_percentage > 100:
            flash('Discount percentage must be between 1 and 100', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
        
        if valid_until < valid_from:
            flash('End date must be after start date', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
        
        # Check if coupon code already exists (excluding this coupon)
        existing_coupon = Coupon.query.filter(Coupon.code == code, Coupon.id != coupon_id).first()
        if existing_coupon:
            flash('A coupon with this code already exists', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
        
        # Update coupon
        coupon.code = code
        coupon.discount_percentage = discount_percentage
        coupon.valid_from = valid_from
        coupon.valid_until = valid_until
        coupon.max_uses = max_uses
        coupon.is_active = is_active
        coupon.description = description
        
        db.session.commit()
        
        flash('Coupon updated successfully', 'success')
        return redirect(url_for('admin_coupons'))
    
    return render_template('admin/admin_coupon_form.html', coupon=coupon)

@app.route('/admin/bookings/export-csv')
@login_required
def export_bookings_csv():
    if not current_user.is_admin:
        abort(403)
    
    # Get filter parameters from request
    status_filter = request.args.get('status')
    search_query = request.args.get('search', '')
    date_filter = request.args.get('date_filter', 'all')
    
    # Start with base query
    query = Booking.query.join(User)
    
    # Apply status filter if provided
    if status_filter:
        query = query.filter(Booking.status == status_filter)
    
    # Apply search filter if provided
    if search_query:
        query = query.filter(
            db.or_(
                Booking.id.like(f'%{search_query}%'),
                User.username.like(f'%{search_query}%'),
                User.email.like(f'%{search_query}%')
            )
        )
    
    # Apply date filter if provided
    today = datetime.now().date()
    if date_filter == 'upcoming':
        query = query.filter(Booking.check_in >= today)
    elif date_filter == 'past':
        query = query.filter(Booking.check_out < today)
    elif date_filter == 'today':
        query = query.filter(
            db.or_(
                Booking.check_in == today,
                Booking.check_out == today,
                db.and_(Booking.check_in <= today, Booking.check_out >= today)
            )
        )
    elif date_filter == 'this_week':
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        query = query.filter(
            db.or_(
                db.and_(Booking.check_in >= start_of_week, Booking.check_in <= end_of_week),
                db.and_(Booking.check_out >= start_of_week, Booking.check_out <= end_of_week),
                db.and_(Booking.check_in <= start_of_week, Booking.check_out >= end_of_week)
            )
        )
    elif date_filter == 'this_month':
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        query = query.filter(
            db.or_(
                db.and_(Booking.check_in >= start_of_month, Booking.check_in <= end_of_month),
                db.and_(Booking.check_out >= start_of_month, Booking.check_out <= end_of_month),
                db.and_(Booking.check_in <= start_of_month, Booking.check_out >= end_of_month)
            )
        )
    
    # Get bookings with user information
    bookings = query.order_by(Booking.created_at.desc()).all()
    
    # Create a StringIO object to write CSV data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['Booking ID', 'User', 'Email', 'Check-in', 'Check-out', 'Nights', 'Guests', 'Total Price', 'Status', 'Payment Status', 'Created At'])
    
    # Write data rows
    for booking in bookings:
        # Calculate number of nights
        nights = (booking.check_out - booking.check_in).days
        
        writer.writerow([
            booking.id,
            booking.user.username,
            booking.user.email,
            booking.check_in.strftime('%Y-%m-%d'),
            booking.check_out.strftime('%Y-%m-%d'),
            nights,
            booking.guests,
            f'₹{booking.total_price}',
            booking.status.capitalize(),
            booking.payment_status.capitalize(),
            booking.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    # Set up response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=royal_chalet_bookings_{timestamp}.csv'
        }
    )

@app.route('/admin/bookings/new', methods=['GET', 'POST'])
@login_required
def admin_new_booking():
    if not current_user.is_admin:
        abort(403)
    
    # Get all users for the dropdown
    users = User.query.all()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        try:
            user_id = int(request.form['user_id'])
            check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
            check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
            guests = int(request.form['guests'])
            total_price = float(request.form['total_price'])
            status = request.form['status']
            special_requests = request.form.get('special_requests', '')
            
            # Validate dates
            if check_in >= check_out:
                flash('Check-out date must be after check-in date', 'error')
                return render_template('admin/admin_booking_form.html', users=users, today=today)
            
            # Check for availability (no overlapping bookings)
            overlapping_bookings = Booking.query.filter(
                Booking.status != 'cancelled',
                Booking.check_in < check_out,
                Booking.check_out > check_in
            ).all()
            
            if overlapping_bookings:
                flash('The selected dates overlap with existing bookings', 'error')
                return render_template('admin/admin_booking_form.html', users=users, today=today)
            
            # Create new booking
            booking = Booking(
                user_id=user_id,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                total_price=total_price,
                special_requests=special_requests,
                status=status,
                payment_status='pending'
            )
            
            db.session.add(booking)
            db.session.commit()
            
            # Create notification for user
            create_notification(
                user_id,
                "New Booking Created",
                f"A new booking from {check_in.strftime('%d/%m/%Y')} to {check_out.strftime('%d/%m/%Y')} has been created for you by an administrator.",
                "info"
            )
            
            flash(f'Booking created successfully for {booking.user.username}', 'success')
            return redirect(url_for('admin_bookings'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating booking: {str(e)}', 'error')
    
    return render_template('admin/admin_booking_form.html', users=users, today=today)

# Password reset routes
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            
            email_body = f"""
            <h2>Password Reset Request</h2>
            <p>You requested a password reset for your account.</p>
            <p>Click the link below to reset your password:</p>
            <a href="{reset_url}">Reset Password</a>
            <p>If you didn't request this, please ignore this email.</p>
            """
            
            try:
                if send_email(email, "Password Reset Request", email_body):
                    flash('Password reset email sent! Check your inbox.')
                else:
                    flash('Error sending reset email! Please check the email configuration.')
            except Exception as e:
                flash(f'Error sending reset email: {str(e)}')
                app.logger.error(f"Email sending error: {str(e)}")
        else:
            flash('Email not found!')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadSignature):
        flash('Invalid or expired reset token!')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match!')
            return render_template('reset_password.html')
        
        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash('Password reset successful! Please login.')
            return redirect(url_for('login'))
        else:
            flash('User not found!')
    
    return render_template('reset_password.html')

@app.route('/about')
def about():
    # This route will redirect to the about section on the index page
    return redirect(url_for('index', _anchor='about'))

@app.route('/faq')
def faq():
    # This route will redirect to the faq section on the index page
    return redirect(url_for('index', _anchor='faq'))

@app.route('/notifications')
@login_required
def notifications_page():
    # Get all notifications for the user, ordered by creation date (newest first)
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/api/notifications')
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).all()
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'created_at': n.created_at.isoformat()
    } for n in notifications])

@app.route('/api/mark-notification-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403

@app.route('/api/mark-all-notifications-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    # Mark all unread notifications as read
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001)
