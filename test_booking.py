from flask import Flask
from extensions import db
from models import Booking
from datetime import datetime, timedelta, timezone

# Create Flask app
app = Flask(__name__)

# Configure database
import os
db_path = os.path.join(os.path.abspath('instance'), 'villa_booking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

with app.app_context():
    try:
        # Try to query a booking with payment_status
        query = db.session.query(Booking).filter(Booking.payment_status.in_(['pending', 'paid'])).limit(1)
        booking = query.first()
        
        if booking:
            print(f'✅ Successfully queried booking with payment_status: {booking.payment_status}')
        else:
            print('✅ Query executed successfully but no bookings found')
            
        # Try to create a test booking with payment_status
        test_booking = Booking(
            user_id=1,  # Assuming admin user with ID 1 exists
            check_in=datetime.now(timezone.utc).date(),
            check_out=(datetime.now(timezone.utc) + timedelta(days=2)).date(),
            guests=2,
            total_price=20000,
            status='test',
            payment_status='test',
            special_requests='Test booking to verify payment_status column'
        )
        
        db.session.add(test_booking)
        db.session.commit()
        print(f'✅ Successfully created test booking with ID {test_booking.id} and payment_status: {test_booking.payment_status}')
        
        # Clean up the test booking
        db.session.delete(test_booking)
        db.session.commit()
        print('✅ Test booking deleted')
        
    except Exception as e:
        print(f'❌ Error: {str(e)}')