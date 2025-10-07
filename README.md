# Smart Attendance System

A Flask-based Smart Attendance System for college faculties with QR code scanning, time-restricted attendance, and automated email notifications with Excel and PDF reports.

## Features

- **Faculty Management**: Admin can register faculty members and manage user accounts
- **QR Code System**: Daily unique QR codes with time-restricted attendance (9:30-9:45 AM IST)
- **Attendance Tracking**: Real-time attendance marking with scan time logging
- **Automated Reports**: Daily email reports at 9:45 AM IST with Excel and PDF attachments
- **Role-based Access**: Separate dashboards for admin and faculty
- **Time Zone Support**: All operations use Indian Standard Time (IST)

## Quick Start

### Option 1: Download and Run Locally

1. **Download the application files**
2. **Install Python 3.8+** if not already installed
3. **Install dependencies**:
   ```bash
   pip install flask flask-sqlalchemy werkzeug pytz qrcode openpyxl reportlab gunicorn schedule
   ```
4. **Set up email credentials** (create a `.env` file):
   ```
   SMTP_EMAIL=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   SESSION_SECRET=your_secret_key
   DATABASE_URL=sqlite:///attendance.db
   ```
5. **Run the application**:
   ```bash
   python main.py
   ```
6. **Access the system** at `http://localhost:5000`

### Option 2: Deploy on Replit

1. Fork this Replit project
2. Add your email credentials in Replit Secrets:
   - `SMTP_EMAIL`: Your Gmail address
   - `SMTP_PASSWORD`: Your Gmail app password
3. Run the project

## Default Credentials

- **Admin Username**: `admin`
- **Admin Password**: `admin123`

## Email Configuration

The system sends daily attendance reports to:
- nlramcharanplacement@gmail.com
- 2224m1a3133@vemu.org

To change email recipients, modify the `ADMIN_EMAILS` list in `email_service.py`.

## Gmail App Password Setup

1. Enable 2-Factor Authentication on your Gmail account
2. Go to Google Account settings
3. Generate an App Password for "Mail"
4. Use this app password in your configuration

## System Requirements

- Python 3.8+
- SQLite database (created automatically)
- Internet connection for email sending
- Camera access for QR code scanning (optional - manual entry available)

## File Structure

```
├── app.py              # Flask application setup
├── main.py             # Application entry point
├── routes.py           # Web routes and controllers
├── models.py           # Database models
├── email_service.py    # Email functionality with attachments
├── qr_service.py       # QR code generation
├── scheduler.py        # Automated email scheduling
├── templates/          # HTML templates
├── static/             # CSS and JavaScript files
└── instance/           # Database storage
```

## Usage

### For Administrators

1. Log in with admin credentials
2. Generate monthly QR codes
3. Register faculty members
4. View attendance reports
5. Download QR codes for display

### For Faculty

1. Log in with faculty credentials
2. Scan QR code during attendance window (9:30-9:45 AM IST)
3. View attendance status on dashboard

## Attendance Window

- **Time**: 9:30 AM to 9:45 AM (Indian Standard Time)
- **Frequency**: Daily
- **Method**: QR code scanning or manual code entry

## Email Reports

Daily attendance reports are automatically sent at 9:45 AM IST containing:

- **HTML Email**: Summary with present/absent faculty lists
- **Excel Attachment**: Color-coded spreadsheet with detailed data
- **PDF Attachment**: Professional formatted report

## Troubleshooting

### Email Not Working
- Verify Gmail app password is correct
- Check that 2FA is enabled on Gmail account
- Ensure environment variables are set properly

### QR Code Not Scanning
- Check camera permissions in browser
- Ensure proper lighting when scanning
- Use manual code entry as fallback

### Attendance Window Issues
- Verify system time is correct
- Check timezone settings (should be IST)
- Confirm attendance window times in code

## Security Features

- Password hashing for user accounts
- Session-based authentication
- Time-restricted QR codes
- Role-based access control

## Support

For technical support or customization requests, contact the system administrator.

## License

This project is developed for educational/institutional use.