from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, make_response, send_from_directory, abort, Response, Blueprint
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from extensions import db, csrf
from sqlalchemy import text
import os
import json
import uuid
import logging
import io
import csv
from datetime import date, datetime, timedelta, timezone
import locale
from functools import wraps
from types import SimpleNamespace

from models import User, Booking, BookingAddon, FoodMenu, FoodOrder, Review, Contact, VillaSettings, Notification, MenuSection, Coupon, Category, MenuItem
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
# Production: set SECRET_KEY (e.g. openssl rand -hex 32). See .env.example
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'true').lower() in ('1', 'true', 'yes', 'on')

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

# SQLite DB always lives next to the app package (not the shell working directory)
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
_INSTANCE_DIR = os.path.join(_APP_ROOT, 'instance')
os.makedirs(_INSTANCE_DIR, exist_ok=True)

db_path = os.path.join(_INSTANCE_DIR, 'villa_booking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
csrf.init_app(app)

admin_menu_bp = Blueprint('admin_menu', __name__)
booking_api_bp = Blueprint('booking_api', __name__)

with app.app_context():
    # Create tables if they don't exist
    db.create_all()

    def ensure_booking_coupon_discount_column():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if 'sqlite' not in uri:
            return
        try:
            with db.engine.begin() as conn:
                rows = conn.execute(text('PRAGMA table_info(booking)')).fetchall()
                col_names = {r[1] for r in rows}
                if 'coupon_discount_amount' not in col_names:
                    conn.execute(
                        text('ALTER TABLE booking ADD COLUMN coupon_discount_amount INTEGER DEFAULT 0')
                    )
                    app.logger.info('Added booking.coupon_discount_amount column')
        except Exception:
            app.logger.exception('ensure_booking_coupon_discount_column failed')

    def ensure_coupon_columns():
        uri = app.config.get('SQLALCHEMY_DATABASE_URI') or ''
        if 'sqlite' not in uri:
            return
        try:
            with db.engine.begin() as conn:
                rows = conn.execute(text('PRAGMA table_info(coupon)')).fetchall()
                if not rows:
                    return
                col_names = {r[1] for r in rows}
                # SQLite: avoid NOT NULL on ADD COLUMN unless every row gets a default
                statements = []
                if 'times_used' not in col_names:
                    statements.append(
                        text('ALTER TABLE coupon ADD COLUMN times_used INTEGER DEFAULT 0')
                    )
                if 'description' not in col_names:
                    statements.append(text('ALTER TABLE coupon ADD COLUMN description TEXT'))
                if 'discount_type' not in col_names:
                    statements.append(
                        text("ALTER TABLE coupon ADD COLUMN discount_type VARCHAR(20) DEFAULT 'percentage'")
                    )
                if 'discount_value' not in col_names:
                    statements.append(
                        text('ALTER TABLE coupon ADD COLUMN discount_value INTEGER DEFAULT 0')
                    )
                if 'max_uses' not in col_names:
                    statements.append(text('ALTER TABLE coupon ADD COLUMN max_uses INTEGER'))
                if 'is_active' not in col_names:
                    statements.append(text('ALTER TABLE coupon ADD COLUMN is_active BOOLEAN DEFAULT 1'))
                if 'created_at' not in col_names:
                    statements.append(
                        text('ALTER TABLE coupon ADD COLUMN created_at DATETIME')
                    )
                for stmt in statements:
                    conn.execute(stmt)
                if statements:
                    app.logger.info('Coupon table: applied %s schema patch(es)', len(statements))
        except Exception:
            app.logger.exception('ensure_coupon_columns failed')

    ensure_booking_coupon_discount_column()
    ensure_coupon_columns()
    
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


@app.template_filter('coupon_as_date')
def coupon_as_date(value):
    """Normalize Coupon.valid_* (datetime or date) to a date for comparisons and inputs."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
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
                         recent_reviews=recent_reviews,
                         total_bookings=total_bookings,
                         total_reviews=total_reviews,
                         avg_rating=round(avg_rating, 1),
                         weekday_price=weekday_price,
                         weekend_price=weekend_price,
                         extended_stay_price=extended_stay_price)

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

@app.route('/booking', methods=['GET'])
def booking():
    weekday_price = int(get_setting('weekday_price', 10000))
    weekend_price = int(get_setting('weekend_price', 15000))
    max_guests = int(get_setting('max_guests', '20'))
    coupons_enabled = str(get_setting('enable_coupons', 'true')).lower() in ('1', 'true', 'yes', 'on')
    return render_template(
        'booking_wizard.html',
        weekday_price=weekday_price,
        weekend_price=weekend_price,
        max_guests=max_guests,
        coupons_enabled=coupons_enabled,
    )


def resolve_coupon_for_booking(coupon_code):
    """Return (coupon, error_message). coupon is None if code empty; error_message if invalid."""
    if coupon_code is None:
        return None, None
    code = str(coupon_code).strip().upper()
    if not code:
        return None, None
    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        return None, 'Invalid coupon code'
    if not coupon.is_active:
        return None, 'This coupon is no longer active'
    today = datetime.now().date()
    vf = coupon.valid_from.date() if hasattr(coupon.valid_from, 'date') else coupon.valid_from
    vu = coupon.valid_until.date() if hasattr(coupon.valid_until, 'date') else coupon.valid_until
    if today < vf or today > vu:
        return None, 'This coupon is not valid for the current date'
    used = getattr(coupon, 'times_used', None)
    if used is None:
        used = 0
    if coupon.max_uses is not None and int(used) >= coupon.max_uses:
        return None, 'This coupon has reached its maximum usage limit'
    return coupon, None


def coupon_discount_rupees(coupon, subtotal_before_discount):
    """Rupees to subtract from subtotal before tax; never below zero or above subtotal."""
    if not coupon or subtotal_before_discount <= 0:
        return 0
    subtotal_before_discount = int(subtotal_before_discount)
    dtype = (getattr(coupon, 'discount_type', None) or 'percentage').lower()
    if dtype == 'fixed':
        v = int(getattr(coupon, 'discount_value', 0) or 0)
        return min(max(0, v), subtotal_before_discount)
    pct = int(getattr(coupon, 'discount_percentage', 0) or 0)
    pct = max(0, min(100, pct))
    return int(round(subtotal_before_discount * (pct / 100.0)))


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
        coupon, _cerr = resolve_coupon_for_booking(coupon_code)
        if coupon:
            discount = coupon_discount_rupees(coupon, subtotal)
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
    try:
        data = request.get_json() or {}
        code = data.get('code', '').strip().upper()
        if not code:
            return jsonify({'valid': False, 'message': 'No promo code provided'})
        coupon, err = resolve_coupon_for_booking(code)
        if err:
            return jsonify({'valid': False, 'message': err})
        if not coupon:
            return jsonify({'valid': False, 'message': 'Invalid promo code'})
        dtype = (getattr(coupon, 'discount_type', None) or 'percentage').lower()
        if dtype == 'fixed':
            msg = f'Promo code applied: ₹{int(coupon.discount_value or 0)} off'
            return jsonify({
                'valid': True,
                'message': msg,
                'discount_type': 'fixed',
                'discount_value': int(coupon.discount_value or 0),
            })
        return jsonify({
            'valid': True,
            'message': f'Promo code applied: {coupon.discount_percentage}% discount',
            'discount_type': 'percent',
            'discount_value': coupon.discount_percentage,
        })
    except Exception as e:
        app.logger.error(f"Error validating promo code: {str(e)}")
        return jsonify({'valid': False, 'message': f'Error: {str(e)}'}), 500

@booking_api_bp.route('/booking/check-availability', methods=['POST'], endpoint='check_availability')
@csrf.exempt
def booking_check_availability():
    data = request.get_json() or {}
    check_in_str = data.get('check_in')
    check_out_str = data.get('check_out')
    if not check_in_str or not check_out_str:
        return jsonify({'available': False, 'message': 'Missing dates'}), 400
    try:
        check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
        check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'available': False, 'message': 'Invalid date format'}), 400
    if check_out <= check_in:
        return jsonify({'available': False, 'message': 'Check-out must be after check-in'}), 400
    conflicting = Booking.query.filter(
        db.or_(
            db.and_(Booking.check_in <= check_in, Booking.check_out > check_in),
            db.and_(Booking.check_in < check_out, Booking.check_out >= check_out),
            db.and_(Booking.check_in >= check_in, Booking.check_out <= check_out),
        ),
        Booking.status.in_(['pending', 'confirmed']),
    ).first()
    if conflicting:
        return jsonify({'available': False, 'message': 'These dates are not available'}), 200
    return jsonify({'available': True}), 200

@booking_api_bp.route('/booking/create', methods=['POST'], endpoint='create')
@csrf.exempt
def booking_create():
    data = request.get_json() or {}
    check_in_str = data.get('check_in')
    check_out_str = data.get('check_out')
    guests = data.get('guests') or 1
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    address = (data.get('address') or '').strip()
    special_request = (data.get('special_request') or '').strip()
    addons_data = data.get('addons') or []

    if not check_in_str or not check_out_str:
        return jsonify({'success': False, 'message': 'Missing dates'}), 400
    if not full_name or not email or not phone or not address:
        return jsonify({'success': False, 'message': 'Missing guest details'}), 400

    try:
        check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
        check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400

    if check_out <= check_in:
        return jsonify({'success': False, 'message': 'Check-out must be after check-in'}), 400

    conflicting = Booking.query.filter(
        db.or_(
            db.and_(Booking.check_in <= check_in, Booking.check_out > check_in),
            db.and_(Booking.check_in < check_out, Booking.check_out >= check_out),
            db.and_(Booking.check_in >= check_in, Booking.check_out <= check_out),
        ),
        Booking.status.in_(['pending', 'confirmed']),
    ).first()
    if conflicting:
        return jsonify({'success': False, 'message': 'These dates are no longer available'}), 200

    weekday_p = int(get_setting('weekday_price', 10000))
    weekend_p = int(get_setting('weekend_price', 15000))
    coupons_enabled = str(get_setting('enable_coupons', 'true')).lower() in ('1', 'true', 'yes', 'on')
    coupon_code_raw = (data.get('coupon_code') or '').strip()

    current = check_in
    base_price = 0
    while current < check_out:
        day = current.weekday()
        is_weekend = day in (5, 6)
        base_price += weekend_p if is_weekend else weekday_p
        current += timedelta(days=1)

    addons_total = 0
    normalized_addons = []
    for a in addons_data:
        name = (a.get('name') or '').strip()
        try:
            price = int(a.get('price') or 0)
        except Exception:
            price = 0
        if name and price > 0:
            normalized_addons.append({'name': name, 'price': price})
            addons_total += price

    subtotal_before_discount = base_price + addons_total
    coupon_obj = None
    discount_amt = 0
    if coupon_code_raw:
        if not coupons_enabled:
            return jsonify({'success': False, 'message': 'Coupons are not enabled at this time'}), 400
        coupon_obj, cerr = resolve_coupon_for_booking(coupon_code_raw)
        if cerr:
            return jsonify({'success': False, 'message': cerr}), 400
        discount_amt = coupon_discount_rupees(coupon_obj, subtotal_before_discount)

    subtotal_after_discount = subtotal_before_discount - discount_amt
    tax_amount = int(round(subtotal_after_discount * 0.12))
    total = subtotal_after_discount + tax_amount

    booking_code = datetime.now(timezone.utc).strftime('%y%m%d') + '-' + uuid.uuid4().hex[:6].upper()

    booking = Booking(
        user_id=current_user.id if current_user.is_authenticated else None,
        user_name=full_name,
        email=email,
        phone=phone,
        address=address,
        check_in=check_in,
        check_out=check_out,
        guests=int(guests),
        base_price=base_price,
        subtotal=subtotal_after_discount,
        gst=tax_amount,
        total_price=total,
        status='pending',
        payment_status='pending',
        special_requests=special_request,
        booking_date=datetime.now(timezone.utc),
        booking_uid=booking_code,
        coupon_id=coupon_obj.id if coupon_obj else None,
        coupon_discount_amount=discount_amt if coupon_obj else 0,
    )
    db.session.add(booking)
    db.session.flush()

    for a in normalized_addons:
        addon = BookingAddon(
            booking_id=booking.id,
            addon_name=a['name'],
            addon_price=a['price'],
        )
        db.session.add(addon)

    if coupon_obj:
        c_row = Coupon.query.get(coupon_obj.id)
        if c_row and c_row.max_uses is not None and (c_row.times_used or 0) >= c_row.max_uses:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'This coupon has reached its maximum usage limit'}), 400
        if c_row:
            c_row.times_used = (c_row.times_used or 0) + 1

    db.session.commit()

    confirmation_url = url_for('booking_confirmation', booking_id=booking.id)
    return jsonify({'success': True, 'booking_id': booking_code, 'confirmation_url': confirmation_url}), 200

@app.route('/booking/confirmation/<int:booking_id>')
def booking_confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    payment_status = booking.payment_status or 'pending'
    addons = getattr(booking, 'addons', [])
    return render_template('booking_confirmation.html', booking=booking, addons=addons, payment_status=payment_status)

@app.route('/menu', endpoint='menu')
def menu():
    sections = MenuSection.query.filter_by(is_active=True).order_by(MenuSection.display_order.asc()).all()
    items_by_section = {}
    for section in sections:
        items = (
            FoodMenu.query.filter_by(section_id=section.id, is_available=True)
            .order_by(FoodMenu.name.asc())
            .all()
        )
        items_by_section[section.id] = items

    return render_template(
        'menu.html',
        sections=sections,
        items_by_section=items_by_section,
    )

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
        query = query.outerjoin(User).filter(
            db.or_(
                Booking.id.like(f'%{search_query}%'),
                Booking.user_name.like(f'%{search_query}%'),
                Booking.email.like(f'%{search_query}%'),
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
        user = User.query.get(booking.user_id) if booking.user_id else None
        guest_name = None
        if user:
            guest_name = user.username
        elif getattr(booking, "user_name", None):
            guest_name = booking.user_name
        else:
            guest_name = "Guest"
        
        calendar_events.append({
            'id': booking.id,
            'title': f'{guest_name} - {booking.guests} guests',
            'start': booking.check_in.strftime('%Y-%m-%d'),
            'end': booking.check_out.strftime('%Y-%m-%d'),
            'color': '#4CAF50'
        })
    
    # Add pending bookings with different color
    pending_bookings = Booking.query.filter_by(status='pending').all()
    for booking in pending_bookings:
        user = User.query.get(booking.user_id) if booking.user_id else None
        guest_name = None
        if user:
            guest_name = user.username
        elif getattr(booking, "user_name", None):
            guest_name = booking.user_name
        else:
            guest_name = "Guest"
        
        calendar_events.append({
            'id': booking.id,
            'title': f'{guest_name} - {booking.guests} guests (Pending)',
            'start': booking.check_in.strftime('%Y-%m-%d'),
            'end': booking.check_out.strftime('%Y-%m-%d'),
            'color': '#FFC107'
        })
    
    return render_template('admin/admin_bookings_calendar.html', calendar_events=calendar_events)


@app.route('/admin/booking/<int:booking_id>')
@login_required
def admin_booking_details(booking_id):
    if not current_user.is_admin:
        abort(403)
    
    booking = Booking.query.get_or_404(booking_id)
    return render_template('admin/admin_booking_details.html', booking=booking)


@app.route('/admin/booking/delete/<int:booking_id>', methods=['POST'])
@login_required
def admin_booking_delete(booking_id):
    if not current_user.is_admin:
        abort(403)
    
    booking = Booking.query.get_or_404(booking_id)
    db.session.delete(booking)
    db.session.commit()
    flash('Booking deleted successfully!', 'success')
    return redirect(url_for('admin_bookings'))


@app.route('/admin/booking/update-status/<int:booking_id>', methods=['POST'])
@login_required
def admin_booking_update_status(booking_id):
    if not current_user.is_admin:
        abort(403)
    
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    if new_status in ['pending', 'confirmed', 'cancelled']:
        booking.status = new_status
        db.session.commit()
        flash(f'Booking status updated to {new_status}!', 'success')
    
    return redirect(url_for('admin_booking_details', booking_id=booking.id))


@app.route('/admin/bookings/new', methods=['GET', 'POST'])
@login_required
def admin_bookings_new():
    if not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        check_in = datetime.strptime(request.form.get('check_in'), '%Y-%m-%d')
        check_out = datetime.strptime(request.form.get('check_out'), '%Y-%m-%d')
        guests = int(request.form.get('guests'))
        total_price = float(request.form.get('total_price'))
        status = request.form.get('status')
        special_requests = request.form.get('special_requests')
        
        booking = Booking(
            user_id=user_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            total_price=total_price,
            status=status,
            special_requests=special_requests
        )
        db.session.add(booking)
        db.session.commit()
        flash('Booking created successfully!', 'success')
        return redirect(url_for('admin_bookings'))
    
    users = User.query.all()
    return render_template('admin/admin_booking_form.html', users=users, booking=None, today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/admin/booking/edit/<int:booking_id>', methods=['GET', 'POST'])
@login_required
def admin_booking_edit(booking_id):
    if not current_user.is_admin:
        abort(403)
    
    booking = Booking.query.get_or_404(booking_id)
    
    if request.method == 'POST':
        booking.user_id = request.form.get('user_id')
        booking.check_in = datetime.strptime(request.form.get('check_in'), '%Y-%m-%d')
        booking.check_out = datetime.strptime(request.form.get('check_out'), '%Y-%m-%d')
        booking.guests = int(request.form.get('guests'))
        booking.total_price = float(request.form.get('total_price'))
        booking.status = request.form.get('status')
        booking.special_requests = request.form.get('special_requests')
        
        db.session.commit()
        flash('Booking updated successfully!', 'success')
        return redirect(url_for('admin_bookings'))
    
    users = User.query.all()
    return render_template('admin/admin_booking_form.html', users=users, booking=booking, today=datetime.now().strftime('%Y-%m-%d'))

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

@admin_menu_bp.route('/menu')
@login_required
def admin_menu_dashboard():
    if not current_user.is_admin:
        abort(403)

    page = request.args.get('page', 1, type=int)
    per_page = 15
    search_query = request.args.get('q', '', type=str).strip()
    section_id = request.args.get('section', type=int)

    sections = MenuSection.query.order_by(MenuSection.name.asc()).all()

    items_query = FoodMenu.query

    if section_id:
        items_query = items_query.filter(FoodMenu.section_id == section_id)

    if search_query:
        ilike_pattern = f"%{search_query}%"
        items_query = items_query.filter(
            (FoodMenu.name.ilike(ilike_pattern)) | (FoodMenu.description.ilike(ilike_pattern))
        )

    # Use a different ordering if created_at is not available, or use id
    items_query = items_query.order_by(FoodMenu.id.desc())
    pagination = items_query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'admin/admin_menu.html',
        sections=sections,
        items=pagination.items,
        pagination=pagination,
        search_query=search_query,
        selected_section_id=section_id,
    )


@admin_menu_bp.route('/menu/add', methods=['GET', 'POST'])
@login_required
def admin_add_menu_item():
    if not current_user.is_admin:
        abort(403)

    sections = MenuSection.query.order_by(MenuSection.name.asc()).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '').strip()
        description = request.form.get('description', '').strip()
        section_id = request.form.get('section_id')
        is_veg = request.form.get('is_veg') == 'true'
        is_available = request.form.get('is_available') == 'true'
        image_file = request.files.get('image')

        errors = []

        if not name:
            errors.append('Name is required.')
        if not price:
            errors.append('Price is required.')
        else:
            try:
                price = float(price)
                if price <= 0:
                    errors.append('Price must be positive.')
            except ValueError:
                errors.append('Price must be a number.')

        if not section_id:
            errors.append('Section is required.')

        image_path = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'menu')
            os.makedirs(upload_folder, exist_ok=True)
            image_path = os.path.join('menu', filename)
            image_file.save(os.path.join(upload_folder, filename))

        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('admin_menu.admin_menu_dashboard'))

        menu_item = FoodMenu(
            name=name,
            description=description,
            price=price,
            section_id=int(section_id),
            is_veg=is_veg,
            is_available=is_available,
            image_url=image_path,
        )
        db.session.add(menu_item)
        db.session.commit()

        flash('Menu item added successfully.', 'success')
        return redirect(url_for('admin_menu.admin_menu_dashboard'))

    return redirect(url_for('admin_menu.admin_menu_dashboard'))


@admin_menu_bp.route('/menu/<int:item_id>/edit', methods=['POST'])
@login_required
def admin_edit_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)

    item = FoodMenu.query.get_or_404(item_id)

    name = request.form.get('name', '').strip()
    price = request.form.get('price', '').strip()
    description = request.form.get('description', '').strip()
    section_id = request.form.get('section_id')
    is_veg = request.form.get('is_veg') == 'true'
    is_available = request.form.get('is_available') == 'true'
    image_file = request.files.get('image')

    if name:
        item.name = name
    if price:
        try:
            item.price = float(price)
        except ValueError:
            flash('Price must be a number.', 'error')
            return redirect(url_for('admin_menu.admin_menu_dashboard'))
    item.description = description
    if section_id:
        item.section_id = int(section_id)
    item.is_veg = is_veg
    item.is_available = is_available

    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'menu')
        os.makedirs(upload_folder, exist_ok=True)
        image_path = os.path.join('menu', filename)
        image_file.save(os.path.join(upload_folder, filename))
        item.image_url = image_path

    db.session.commit()
    flash('Menu item updated successfully.', 'success')
    return redirect(url_for('admin_menu.admin_menu_dashboard'))


@admin_menu_bp.route('/menu/<int:item_id>/delete', methods=['POST'])
@login_required
def admin_delete_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)

    item = FoodMenu.query.get_or_404(item_id)
    
    # Optional: Delete image file
    if item.image_url:
        try:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], item.image_url)
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            app.logger.error(f"Error deleting menu image: {e}")

    db.session.delete(item)
    db.session.commit()
    flash('Menu item deleted successfully.', 'success')
    return redirect(url_for('admin_menu.admin_menu_dashboard'))


@admin_menu_bp.route('/menu/<int:item_id>/toggle-availability', methods=['POST'])
@login_required
def admin_toggle_menu_item(item_id):
    if not current_user.is_admin:
        abort(403)

    item = FoodMenu.query.get_or_404(item_id)
    item.is_available = not item.is_available
    db.session.commit()
    status = "available" if item.is_available else "unavailable"
    flash(f'Menu item "{item.name}" is now {status}!')
    return redirect(url_for('admin_menu.admin_menu_dashboard'))

@app.route('/admin/sections')
@login_required
def admin_sections():
    if not current_user.is_admin:
        abort(403)
    return redirect(url_for('admin_menu.admin_menu_dashboard'))

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

def update_setting(key, value):
    """Update or create a villa setting"""
    setting = VillaSettings.query.filter_by(setting_key=key).first()
    if setting:
        setting.setting_value = value
    else:
        setting = VillaSettings(setting_key=key, setting_value=value)
        db.session.add(setting)

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
                    update_setting(key, request.form[key])
            
            # Process new settings for guest pricing
            max_guests = request.form.get('max_guests', '20')
            base_guests = request.form.get('base_guests', '8')
            additional_guest_fee = request.form.get('additional_guest_fee', '500')
            
            # Save the settings
            update_setting('max_guests', max_guests)
            update_setting('base_guests', base_guests)
            update_setting('additional_guest_fee', additional_guest_fee)
            
            # Commit the changes to the database
            db.session.commit()
            
            # Update email configuration from database settings
            update_email_config_from_db()
            
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('admin_settings'))
            
        except Exception as e:
            db.session.rollback()
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
@csrf.exempt
def validate_coupon():
    data = request.get_json(silent=True) or {}
    coupon_code = data.get('coupon_code', '')
    if str(get_setting('enable_coupons', 'true')).lower() not in ('1', 'true', 'yes', 'on'):
        return jsonify({'valid': False, 'message': 'Coupons are not enabled at this time'})
    coupon, err = resolve_coupon_for_booking(coupon_code)
    if err:
        return jsonify({'valid': False, 'message': err})
    if not coupon:
        return jsonify({'valid': False, 'message': 'Please enter a valid coupon code'})
    dtype = (getattr(coupon, 'discount_type', None) or 'percentage').lower()
    if dtype == 'fixed':
        msg = f'Coupon applied: ₹{int(coupon.discount_value or 0)} off your stay'
    else:
        msg = f'Coupon applied: {coupon.discount_percentage}% discount'
    return jsonify({
        'valid': True,
        'code': coupon.code,
        'discount_type': dtype,
        'discount_percentage': int(coupon.discount_percentage or 0),
        'discount_value': int(coupon.discount_value or 0),
        'message': msg,
    })

def _parse_coupon_form_dates(form):
    vf_raw = form.get('valid_from')
    vu_raw = form.get('valid_until')
    if not vf_raw or not vu_raw:
        return None, None, 'Please provide valid from and valid until dates'
    try:
        valid_from = datetime.strptime(vf_raw, '%Y-%m-%d')
        valid_until = datetime.strptime(vu_raw, '%Y-%m-%d')
    except (TypeError, ValueError):
        return None, None, 'Invalid date format'
    return valid_from, valid_until, None


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
        discount_type = request.form.get('discount_type', 'percentage') or 'percentage'
        discount_value = request.form.get('discount_value', type=int)
        valid_from, valid_until, date_err = _parse_coupon_form_dates(request.form)
        if date_err:
            flash(date_err, 'error')
            return redirect(url_for('admin_add_coupon'))
        max_uses = request.form.get('max_uses', type=int)
        is_active = 'is_active' in request.form
        description = request.form.get('description', '').strip()
        
        # Validate input
        if not code or (discount_type == 'percentage' and not discount_percentage) or (discount_type == 'fixed' and not discount_value):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('admin_add_coupon'))
        
        if discount_type == 'percentage' and (discount_percentage < 1 or discount_percentage > 100):
            flash('Discount percentage must be between 1 and 100', 'error')
            return redirect(url_for('admin_add_coupon'))

        if discount_type == 'fixed' and discount_value < 1:
            flash('Fixed discount amount must be at least ₹1', 'error')
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
            discount_percentage=discount_percentage if discount_type == 'percentage' else 0,
            discount_type=discount_type,
            discount_value=discount_value if discount_type == 'fixed' else 0,
            valid_from=valid_from,
            valid_until=valid_until,
            max_uses=max_uses,
            is_active=is_active,
            description=description
        )
        
        try:
            db.session.add(new_coupon)
            db.session.commit()
            flash('Coupon created successfully', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating coupon: {str(e)}")
            flash(f'Error creating coupon: {str(e)}', 'error')
            return redirect(url_for('admin_add_coupon'))
        
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
        discount_type = request.form.get('discount_type', 'percentage') or 'percentage'
        discount_value = request.form.get('discount_value', type=int)
        valid_from, valid_until, date_err = _parse_coupon_form_dates(request.form)
        if date_err:
            flash(date_err, 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
        max_uses = request.form.get('max_uses', type=int)
        is_active = 'is_active' in request.form
        description = request.form.get('description', '').strip()
        
        # Validate input
        if not code or (discount_type == 'percentage' and not discount_percentage) or (discount_type == 'fixed' and not discount_value):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
        
        if discount_type == 'percentage' and (discount_percentage < 1 or discount_percentage > 100):
            flash('Discount percentage must be between 1 and 100', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))

        if discount_type == 'fixed' and discount_value < 1:
            flash('Fixed discount amount must be at least ₹1', 'error')
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
        coupon.discount_type = discount_type
        coupon.discount_percentage = discount_percentage if discount_type == 'percentage' else 0
        coupon.discount_value = discount_value if discount_type == 'fixed' else 0
        coupon.valid_from = valid_from
        coupon.valid_until = valid_until
        coupon.max_uses = max_uses
        coupon.is_active = is_active
        coupon.description = description
        
        try:
            db.session.add(coupon)
            db.session.commit()
            flash('Coupon updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating coupon: {str(e)}")
            flash(f'Error updating coupon: {str(e)}', 'error')
            return redirect(url_for('admin_edit_coupon', coupon_id=coupon_id))
            
        return redirect(url_for('admin_coupons'))
    
    return render_template('admin/admin_coupon_form.html', coupon=coupon)

@app.route('/admin/coupons/toggle/<int:coupon_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.is_active = not coupon.is_active
    db.session.commit()
    flash('Coupon status updated successfully', 'success')
    return redirect(url_for('admin_coupons'))

@app.route('/admin/coupons/delete/<int:coupon_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_coupon(coupon_id):
    coupon = Coupon.query.get_or_404(coupon_id)
    db.session.delete(coupon)
    db.session.commit()
    flash('Coupon deleted successfully', 'success')
    return redirect(url_for('admin_coupons'))

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


app.register_blueprint(admin_menu_bp, url_prefix='/admin')
app.register_blueprint(booking_api_bp, url_prefix='/api')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)