# Royal Chalet - Villa Booking System

Luxury villa booking and in-stay food ordering platform built with Flask and SQLite.

## Overview

Royal Chalet is a complete villa reservation and hospitality management system.  
Guests can discover the property, check availability, create bookings, and order food during their stay, while admins manage bookings, menu items, gallery images, coupons, and other content from a dedicated dashboard.

The project is designed as a real-world, production-style Flask application with:
- A rich front-end built using Tailwind CSS and custom JavaScript
- A relational data model for bookings, orders, payments, and reviews
- Separate experiences for guests and administrators

## Tech Stack (What We Use)

- **Backend**
  - Python 3
  - Flask (routing, templating)
  - Flask-Login (authentication and sessions)
  - Flask-SQLAlchemy (ORM and database access)
  - Flask-WTF / WTForms (secure forms and validation)
- **Database**
  - SQLite (default, file-based database)
- **Frontend**
  - HTML + Jinja2 templates
  - Tailwind CSS (utility-first styling, built via CLI)
  - Custom JavaScript in `static/js/main.js` for interactive UI
- **Other**
  - Waitress (optional production-ready WSGI server)
  - Pillow (image handling for gallery and uploads)

## Main Features (What We Have Built)

- **User Accounts**
  - Registration, login, logout with secure password hashing
  - User profiles with contact details and booking history
  - Separate admin users with elevated permissions

- **Villa Booking System**
  - Create bookings with check-in / check-out dates and guest counts
  - Store pricing breakdown (base price, meals, amenities, GST, total)
  - Track booking status (`pending`, `confirmed`, `cancelled`, `completed`)
  - Apply coupons and discounts at booking level

- **Food Menu & Ordering**
  - Structured menu sections (starters, mains, desserts, etc.) via `MenuSection`
  - Individual menu items with price, description, vegetarian flag, and preparation time
  - In-stay food ordering linked to a booking (`FoodOrder`)
  - Order status tracking (`pending`, `preparing`, `ready`, `delivered`)

- **Payments**
  - `Payment` model to store transaction amount, method (UPI/card/netbanking), IDs, and status
  - Basic support for tracking payment lifecycle (`pending`, `completed`, `failed`)

- **Content & Engagement**
  - Dynamic gallery images with captions, alt text, and sections
  - Guest reviews and ratings linked to bookings
  - Contact form with message status tracking
  - Notification system to store user-specific alerts

- **Admin Dashboard**
  - Manage bookings and view guest details
  - Manage menu sections and menu items
  - Review food orders and booking payments
  - Manage gallery images, coupons, contact messages, and basic villa settings

- **UI/UX**
  - Tailwind-based responsive design
  - Landing page sections for about, FAQ, gallery, etc.
  - Smooth interactions and page transitions using JavaScript

## Project Structure

High-level structure of the project:

```text
Royal Chalet/
├── app.py                 # Main Flask application (routes, views, logic)
├── models.py              # Database models and relationships
├── extensions.py          # Flask extensions (db, csrf, etc.)
├── create_db.py           # Database initialization script with seed data
├── update_menu.py         # Script to create/update menu sections and items
├── run_menu_update.bat    # Convenience script to run update_menu.py on Windows
├── build.bat              # Helper script to build Tailwind CSS on Windows
├── requirements.txt       # Python dependencies
├── package.json           # Node dependencies for Tailwind CSS
├── instance/              # SQLite database and instance-specific files
├── static/                # Static assets (CSS, JS, images)
│   ├── css/               # Tailwind input and generated CSS
│   ├── js/                # Frontend JavaScript (main.js and others)
│   └── images/            # Gallery and payment-related images
└── templates/             # HTML/Jinja templates
    ├── admin/             # Admin dashboard templates
    └── ...                # Public pages (home, booking, menu, contact, etc.)
```

## Setup & Installation

### 1. Prerequisites

- Python 3.x installed and available on PATH
- `pip` for installing Python packages
- (Optional) Node.js and npm for building Tailwind CSS

### 2. Create and Activate Virtual Environment (Recommended)

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.\.venv\Scripts\activate       # Windows (PowerShell or CMD)
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Build Tailwind CSS (Optional but Recommended)

If you plan to modify styles or rebuild CSS:

- Install Node dependencies (once):

```bash
npm install
```

- Build Tailwind CSS:

```bash
npm run build-prod
```

On Windows you can also use:

```bash
build.bat
```

This will generate `static/css/tailwind.css`.

### 5. Initialize Database

```bash
python create_db.py
```

This will:
- Create all necessary database tables
- Add sample users (admin and guest)
- Populate the menu with Indian cuisine items and sections

### 6. Run the Application

```bash
python app.py
```

The application will be available at:

```text
http://localhost:5001
```

You can change the port in `app.py` if needed.

## Default Login Credentials

### Admin User
- Username: `admin`
- Password: `admin123`

### Sample User
- Username: `guest`
- Password: `guest123`

Use the admin account to access the admin dashboard and manage the system.  
Use the guest account to explore the booking and food ordering experience from a normal user’s perspective.

## How to Use the Application

- **As a Guest**
  - Browse the landing page, gallery, and FAQ sections
  - Register a new account or log in with the sample user
  - Create a villa booking by selecting dates, guests, and any add-ons
  - Place food orders linked to your booking
  - View booking history and order details from your profile
  - Leave a review and rating for completed stays

- **As an Admin**
  - Log in using the admin credentials
  - View and manage all bookings, including status and payment details
  - Configure menu sections and items (categories, prices, veg/non-veg, availability)
  - Manage gallery images and featured content
  - Review and respond to contact messages
  - Create and manage discount coupons

## Database Structure (What Data We Store)

The application uses SQLite with the following main tables:

- `user`             – User accounts, profile info, and role (admin/guest)
- `booking`          – Villa booking details, pricing, status, and coupon link
- `food_menu`        – Menu items with sections, price, and dietary info
- `menu_section`     – Logical grouping of menu items (e.g., Starters, Main Course)
- `food_order`       – Food orders linked to bookings and users
- `payment`          – Payment records, methods, amounts, and statuses
- `gallery_image`    – Images used in the gallery, with captions and tags
- `review`           – Guest ratings and comments for completed bookings
- `contact`          – Messages submitted via the contact form
- `villa_settings`   – Configurable settings for the villa and website
- `notification`     – Notifications stored per user
- `coupon`           – Discount codes and their usage rules and limits

## Helper Scripts

- `create_db.py`
  - Creates all tables and inserts sample data (users, menu items)
- `update_menu.py`
  - Creates or updates `MenuSection` records and related `FoodMenu` entries
- `run_menu_update.bat`
  - Windows batch file to run `update_menu.py` (activates `.venv` if present)
- `build.bat`
  - Builds Tailwind CSS using the Node-based toolchain on Windows

## Troubleshooting

### Database Issues

If you encounter database errors like `no such table: user`:

1. **Delete the existing database** (if any):

   ```bash
   rm instance/villa_booking.db           # Linux / macOS
   del instance\villa_booking.db          # Windows (PowerShell / CMD)
   ```

2. **Recreate the database**:

   ```bash
   python create_db.py
   ```

3. **Test the database**:

   The database is automatically exercised when `create_db.py` runs and when you start the app.

### Common Issues

1. **Port already in use**
   - Change the port in `app.py` where the Flask app is started.
2. **Missing dependencies**
   - Run `pip install -r requirements.txt` again.
3. **Permission errors**
   - Ensure write permissions for the `instance` directory.
4. **Static files not updating**
   - Rebuild Tailwind CSS using `npm run build-prod` or `build.bat`.

## Development Notes

- Database tables are created automatically on startup if they do not exist.
- Tailwind CSS is compiled from `static/css/input.css` into `static/css/tailwind.css`.
- Frontend behaviors (animations, scrolling, page transitions) live in `static/js/main.js`.

## Support

For issues or questions, use the troubleshooting section above, inspect error logs, or review the models and routes in:
- [app.py](file:///c:/Users/Lenovo/Downloads/Royal%20Chalet/app.py)
- [models.py](file:///c:/Users/Lenovo/Downloads/Royal%20Chalet/models.py)
