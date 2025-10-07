import qrcode
import secrets
import string
from datetime import datetime, date, timedelta
from app import db
from models import QRCode
import logging

def generate_qr_code_string():
    """Generate a random QR code string"""
    length = 32
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_monthly_qr_codes():
    """Generate QR codes for the entire month"""
    current_date = date.today()
    start_of_month = current_date.replace(day=1)
    
    # Calculate the last day of the month
    if current_date.month == 12:
        end_of_month = start_of_month.replace(year=current_date.year + 1, month=1) - timedelta(days=1)
    else:
        end_of_month = start_of_month.replace(month=current_date.month + 1) - timedelta(days=1)
    
    generated_codes = []
    current_day = start_of_month
    
    while current_day <= end_of_month:
        # Check if QR code already exists for this date
        existing_qr = QRCode.query.filter_by(date=current_day).first()
        
        if not existing_qr:
            # Generate new QR code
            qr_string = generate_qr_code_string()
            
            new_qr = QRCode(
                code=qr_string,
                date=current_day,
                is_active=True
            )
            
            db.session.add(new_qr)
            generated_codes.append(new_qr)
            
            logging.info(f"Generated QR code for {current_day}: {qr_string}")
        
        current_day += timedelta(days=1)
    
    db.session.commit()
    return generated_codes

def get_today_qr_code():
    """Get the QR code for today"""
    today = date.today()
    return QRCode.query.filter_by(date=today, is_active=True).first()

def create_qr_code_image(qr_string):
    """Create QR code image (for display purposes)"""
    import qrcode
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_string)
    qr.make(fit=True)
    
    return qr.make_image(fill_color="black", back_color="white")
