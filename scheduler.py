import schedule
import time
import threading
from datetime import datetime, time as dt_time
import pytz
from email_service import send_attendance_email
import logging

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

def should_send_email(hour, minute):
    """Check if it's time to send email in IST"""
    now_ist = datetime.now(IST)
    return now_ist.hour == hour and now_ist.minute == minute

def schedule_daily_email():
    """Schedule daily emails at multiple times: 9:45 AM, 1:45 PM, 2:00 PM, 2:15 PM IST"""
    # Track sent emails for each time slot per date
    sent_times = {}
    
    # Email schedule times (hour, minute)
    email_times = [
        (9, 45),   # 9:45 AM
        (13, 45),  # 1:45 PM
        (14, 0),   # 2:00 PM
        (14, 15)   # 2:15 PM
    ]
    
    while True:
        now_ist = datetime.now(IST)
        current_date = now_ist.date()
        current_time = (now_ist.hour, now_ist.minute)
        
        # Initialize tracking for new date
        if current_date not in sent_times:
            sent_times[current_date] = set()
        
        # Check if current time matches any email time and hasn't been sent today
        if current_time in email_times and current_time not in sent_times[current_date]:
            
            time_str = f"{now_ist.hour:02d}:{now_ist.minute:02d}"
            logging.info(f"Sending email at {now_ist.strftime('%Y-%m-%d')} {time_str} IST")
            success = send_attendance_email()
            
            if success:
                sent_times[current_date].add(current_time)
                logging.info(f"Email sent successfully at {time_str}")
            else:
                logging.error(f"Failed to send email at {time_str}")
        
        # Clean up old date tracking (keep only last 7 days)
        if len(sent_times) > 7:
            oldest_date = min(sent_times.keys())
            del sent_times[oldest_date]
        
        time.sleep(60)  # Check every minute

def start_scheduler():
    """Start the scheduler in a separate thread"""
    scheduler_thread = threading.Thread(target=schedule_daily_email, daemon=True)
    scheduler_thread.start()
    logging.info("Email scheduler started")

# Auto-start scheduler when module is imported
if __name__ != '__main__':
    start_scheduler()
