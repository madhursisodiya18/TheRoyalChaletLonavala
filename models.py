from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
from extensions import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    phone = db.Column(db.String(15))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    orders = db.relationship('FoodOrder', backref='user', lazy=True)
    reviews = db.relationship('Review', backref='user', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Allow null for guest bookings
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    guests = db.Column(db.Integer, default=1)
    adults = db.Column(db.Integer, default=1)
    children = db.Column(db.Integer, default=0)
    villa_type = db.Column(db.String(50), default='Standard Villa')
    meal_plan = db.Column(db.String(50), nullable=True)
    amenities = db.Column(db.Text, nullable=True)  # Stored as JSON string
    base_price = db.Column(db.Integer, nullable=True)
    meal_cost = db.Column(db.Integer, nullable=True, default=0)
    amenities_cost = db.Column(db.Integer, nullable=True, default=0)
    subtotal = db.Column(db.Integer, nullable=True)
    gst = db.Column(db.Integer, nullable=True, default=0)
    total_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled, completed
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, refunded
    special_requests = db.Column(db.Text)
    booking_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    order = db.relationship('FoodOrder', backref='booking', lazy=True)
    payment = db.relationship('Payment', backref='booking', uselist=False, lazy=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupon.id'), nullable=True)
    coupon = db.relationship('Coupon', backref='bookings', lazy=True)

class MenuSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50), default='fas fa-utensils')
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    menu_items = db.relationship('FoodMenu', backref='menu_section', lazy=True)

class FoodMenu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    image = db.Column(db.String(200))
    description = db.Column(db.String(300))
    section_id = db.Column(db.Integer, db.ForeignKey('menu_section.id'), nullable=False)
    section = db.Column(db.String(50), nullable=False, default='General')  # Keep for backward compatibility
    subcategory = db.Column(db.String(50), nullable=True)
    is_available = db.Column(db.Boolean, default=True)
    is_veg = db.Column(db.Boolean, default=True)  # True for vegetarian, False for non-vegetarian
    preparation_time = db.Column(db.Integer, default=15)  # in minutes
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class FoodOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    items = db.Column(db.String(500), nullable=False)  # JSON string of items with quantities
    total_price = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, preparing, ready, delivered
    special_instructions = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    delivered_at = db.Column(db.DateTime)

class GalleryImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(50), nullable=False)
    image_path = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(100))
    alt_text = db.Column(db.String(200))
    is_featured = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    tags = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_approved = db.Column(db.Boolean, default=False)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(15))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='unread')  # unread, read, replied
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    replied_at = db.Column(db.DateTime)

class VillaSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, success, warning, error
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(50), default='upi')  # upi, card, netbanking
    transaction_id = db.Column(db.String(100))
    payment_status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    payment_date = db.Column(db.DateTime)
    upi_id = db.Column(db.String(100))
    upi_reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    discount_percentage = db.Column(db.Integer, nullable=False)
    valid_from = db.Column(db.DateTime, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=False)
    max_uses = db.Column(db.Integer, nullable=True)
    times_used = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Coupon {self.code}>'