from datetime import datetime, date
import pytz
from app import db
from models import User, Attendance, AbsenteeApproval
import logging

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

def get_morning_absentees(target_date=None):
    """Get list of faculty who were absent in morning session"""
    if target_date is None:
        target_date = datetime.now(IST).date()
    
    try:
        # Get all faculty members
        all_faculty = User.query.filter_by(role='faculty').all()
        
        # Get faculty who attended morning session
        morning_attendees = db.session.query(User).join(Attendance).filter(
            Attendance.date == target_date,
            Attendance.session == 'morning'
        ).all()
        
        # Find absentees (those not in attendees list)
        attendee_ids = {user.id for user in morning_attendees}
        absentees = [faculty for faculty in all_faculty if faculty.id not in attendee_ids]
        
        return absentees
        
    except Exception as e:
        logging.error(f"Error getting morning absentees: {e}")
        return []

def get_evening_absentees(target_date=None):
    """Get list of faculty who were absent in evening session"""
    if target_date is None:
        target_date = datetime.now(IST).date()
    
    try:
        # Get all faculty members
        all_faculty = User.query.filter_by(role='faculty').all()
        
        # Get faculty who attended evening session
        evening_attendees = db.session.query(User).join(Attendance).filter(
            Attendance.date == target_date,
            Attendance.session == 'evening'
        ).all()
        
        # Find absentees (those not in attendees list)
        attendee_ids = {user.id for user in evening_attendees}
        absentees = [faculty for faculty in all_faculty if faculty.id not in attendee_ids]
        
        return absentees
        
    except Exception as e:
        logging.error(f"Error getting evening absentees: {e}")
        return []

def create_absentee_approval_request(user_id, target_date, session):
    """Create an absentee approval request"""
    try:
        # Check if request already exists
        existing_request = AbsenteeApproval.query.filter_by(
            user_id=user_id,
            date=target_date,
            session=session
        ).first()
        
        if existing_request:
            return existing_request
        
        # Create new request
        approval_request = AbsenteeApproval()
        approval_request.user_id = user_id
        approval_request.date = target_date
        approval_request.session = session
        approval_request.is_approved = None  # Pending
        
        db.session.add(approval_request)
        db.session.commit()
        
        return approval_request
        
    except Exception as e:
        logging.error(f"Error creating absentee approval request: {e}")
        return None

def approve_absentee(approval_id, approved_by, is_approved, reason=None):
    """Approve or deny an absentee request"""
    try:
        approval_request = AbsenteeApproval.query.get(approval_id)
        if not approval_request:
            return False, "Request not found"
        
        approval_request.is_approved = is_approved
        approval_request.approved_by = approved_by
        approval_request.reason = reason
        approval_request.approved_at = datetime.now(IST)
        
        db.session.commit()
        
        status = "approved" if is_approved else "denied"
        return True, f"Request {status} successfully"
        
    except Exception as e:
        logging.error(f"Error approving absentee: {e}")
        return False, str(e)

def get_pending_approvals(target_date=None):
    """Get all pending absentee approvals for a date"""
    if target_date is None:
        target_date = datetime.now(IST).date()
    
    try:
        pending_approvals = db.session.query(AbsenteeApproval, User).join(User).filter(
            AbsenteeApproval.date == target_date,
            AbsenteeApproval.is_approved.is_(None)
        ).all()
        
        return pending_approvals
        
    except Exception as e:
        logging.error(f"Error getting pending approvals: {e}")
        return []

def get_approved_absentees(target_date=None):
    """Get all approved absentees for a date"""
    if target_date is None:
        target_date = datetime.now(IST).date()
    
    try:
        approved_absentees = db.session.query(AbsenteeApproval, User).join(User).filter(
            AbsenteeApproval.date == target_date,
            AbsenteeApproval.is_approved == True
        ).all()
        
        return approved_absentees
        
    except Exception as e:
        logging.error(f"Error getting approved absentees: {e}")
        return []