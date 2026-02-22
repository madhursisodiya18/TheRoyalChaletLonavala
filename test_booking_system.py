from flask import Flask
from extensions import db
from models import Booking, User
from datetime import datetime, timedelta, timezone
import os

# Create Flask app
app = Flask(__name__)

# Configure database
db_path = os.path.join(os.path.abspath('instance'), 'villa_booking.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

with app.app_context():
    try:
        print('\n===== Testing Booking System =====\n')
        
        # 1. Test the Booking model schema
        print('1. Testing Booking model schema...')
        booking_columns = [column.name for column in Booking.__table__.columns]
        required_columns = ['id', 'user_id', 'check_in', 'check_out', 'guests', 'total_price', 
                           'status', 'payment_status', 'special_requests', 'created_at', 'updated_at']
        
        missing_columns = [col for col in required_columns if col not in booking_columns]
        if missing_columns:
            print(f'❌ Missing columns in Booking model: {missing_columns}')
        else:
            print('✅ All required columns exist in Booking model')
            
        # 2. Test date availability query
        print('\n2. Testing date availability query...')
        check_in = datetime.strptime('2025-08-02', '%Y-%m-%d').date()
        check_out = datetime.strptime('2025-08-03', '%Y-%m-%d').date()
        
        try:
            # This is the query that was failing before
            query = db.session.query(Booking).filter(
                ((Booking.check_in <= check_in) & (Booking.check_out > check_in)) |
                ((Booking.check_in < check_out) & (Booking.check_out >= check_out)) |
                ((Booking.check_in >= check_in) & (Booking.check_out <= check_out))
            ).filter(Booking.status.in_(['confirmed', 'pending'])).limit(1)
            
            result = query.all()
            print(f'✅ Date availability query executed successfully')
        except Exception as e:
            print(f'❌ Date availability query failed: {str(e)}')
        
        # 3. Test creating a booking with payment_status
        print('\n3. Testing booking creation with payment_status...')
        
        # Find or create a test user
        test_user = User.query.filter_by(email='test@example.com').first()
        if not test_user:
            test_user = User(
                username='testuser',
                email='test@example.com',
                password_hash='password',  # In a real app, this would be hashed
                is_admin=False
            )
            db.session.add(test_user)
            db.session.commit()
            print(f'Created test user with ID {test_user.id}')
        
        # Create a test booking
        test_booking = Booking(
            user_id=test_user.id,
            check_in=datetime.now(timezone.utc).date(),
            check_out=(datetime.now(timezone.utc) + timedelta(days=2)).date(),
            guests=2,
            total_price=20000,
            status='test',
            payment_status='test_pending',
            special_requests='Test booking to verify payment_status column'
        )
        
        db.session.add(test_booking)
        db.session.commit()
        print(f'✅ Created test booking with ID {test_booking.id}')
        
        # 4. Test updating payment_status
        print('\n4. Testing payment_status update...')
        test_booking.payment_status = 'test_paid'
        db.session.commit()
        
        # Verify the update
        updated_booking = Booking.query.get(test_booking.id)
        if updated_booking.payment_status == 'test_paid':
            print(f'✅ Successfully updated payment_status to {updated_booking.payment_status}')
        else:
            print(f'❌ Failed to update payment_status. Current value: {updated_booking.payment_status}')
        
        # 5. Clean up
        print('\n5. Cleaning up test data...')
        db.session.delete(test_booking)
        db.session.commit()
        print('✅ Test booking deleted')
        
        print('\n===== All tests completed =====\n')
        
    except Exception as e:
        print(f'\n❌ Unexpected error: {str(e)}')