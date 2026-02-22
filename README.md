# Royal Chalet - Villa Booking System

A Flask-based web application for villa booking with food ordering capabilities.

## Features

- User registration and authentication
- Villa booking system
- Food menu with ordering
- Admin dashboard for management
- Gallery showcase
- Responsive design

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Initialize Database
```bash
python create_db.py
```

This will:
- Create all necessary database tables
- Add sample users (admin and guest)
- Populate the menu with Indian cuisine items

### 3. Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5001`

## Default Login Credentials

### Admin User
- Username: `admin`
- Password: `admin123`

### Sample User
- Username: `guest`
- Password: `guest123`

## Database Structure

The application uses SQLite with the following tables:
- `user` - User accounts and authentication
- `booking` - Villa booking information
- `food_menu` - Menu items with categories
- `food_order` - Food orders linked to bookings
- `gallery_image` - Gallery images for the villa

## Troubleshooting

### Database Issues
If you encounter database errors like "no such table: user":

1. **Delete the existing database** (if any):
   ```bash
   rm instance/villa_booking.db
   ```

2. **Recreate the database**:
   ```bash
   python create_db.py
   ```

3. **Test the database**:
   ```bash
   # The database is automatically tested when created
   ```

### Common Issues

1. **Port already in use**: Change the port in `app.py` line 486
2. **Missing dependencies**: Run `pip install -r requirements.txt`
3. **Permission errors**: Ensure write permissions for the `instance` directory

## File Structure

```
Royal Chalet/
├── app.py                 # Main Flask application
├── models.py              # Database models
├── extensions.py          # Flask extensions
├── create_db.py           # Database initialization script
├── requirements.txt       # Python dependencies
├── instance/             # Database and instance files
├── static/               # Static files (CSS, JS, images)
└── templates/            # HTML templates
```

## Development

The application automatically creates database tables on startup if they don't exist. This prevents the "no such table" error from occurring.

## Support

For issues or questions, check the troubleshooting section above or examine the error logs. 