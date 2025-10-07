import os
import logging
import json
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from app import app, db
from models import User, QRCode, Attendance, EmailLog, AbsenteeApproval, BiometricCredential, AttendancePhoto

# User Management Service Functions
def delete_user_safely(user_id, admin_username):
    """
    Safely delete a user and all related data while preserving data integrity.
    
    Args:
        user_id: ID of user to delete
        admin_username: Username of admin performing the deletion (for audit)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        # Prevent deletion of admin users
        if user.role == 'admin':
            return False, "Cannot delete admin users"
        
        username = user.username
        
        # 1. Delete AttendancePhoto records (linked to Attendance records)
        attendance_ids = [att.id for att in user.attendances]
        if attendance_ids:
            AttendancePhoto.query.filter(AttendancePhoto.attendance_id.in_(attendance_ids)).delete(synchronize_session=False)
        
        # 2. Delete Attendance records
        Attendance.query.filter_by(user_id=user_id).delete()
        
        # 3. Delete AbsenteeApproval records
        AbsenteeApproval.query.filter_by(user_id=user_id).delete()
        
        # 4. Delete BiometricCredential records
        BiometricCredential.query.filter_by(user_id=user_id).delete()
        
        # 5. Finally delete the User record
        db.session.delete(user)
        
        # Commit all changes
        db.session.commit()
        
        # Log the deletion for audit
        logging.info(f"User {username} (ID: {user_id}) deleted by admin {admin_username}")
        
        return True, f"User {username} and all associated data deleted successfully"
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Failed to delete user {user_id}: {e}")
        return False, f"Failed to delete user: {str(e)}"

def delete_all_faculty(admin_username):
    """
    Delete all faculty users while preserving admin accounts.
    
    Args:
        admin_username: Username of admin performing the deletion
    
    Returns:
        tuple: (success: bool, message: str, count: int)
    """
    try:
        # Get all faculty users only (not workers or other roles)
        faculty_users = User.query.filter(User.role == 'faculty').all()
        deleted_count = 0
        failed_users = []
        
        for user in faculty_users:
            success, message = delete_user_safely(user.id, admin_username)
            if success:
                deleted_count += 1
            else:
                failed_users.append(f"{user.username}: {message}")
        
        if failed_users:
            return False, f"Deleted {deleted_count} users, but failed to delete: {'; '.join(failed_users)}", deleted_count
        else:
            return True, f"Successfully deleted all {deleted_count} faculty users", deleted_count
            
    except Exception as e:
        logging.error(f"Failed to delete all faculty: {e}")
        return False, f"Failed to delete faculty users: {str(e)}", 0

@app.route('/setup_admin', methods=['GET', 'POST'])
def setup_admin():
    """Secure one-time admin setup for college deployment"""
    # Check if any admin already exists
    if User.query.filter_by(role='admin').first():
        return jsonify({'error': 'Admin setup not available - contact system administrator'}), 403
        
    if request.method == 'POST':
        # Get secure setup key from environment
        required_setup_key = os.environ.get('ADMIN_SETUP_KEY')
        if not required_setup_key:
            return jsonify({'error': 'Setup not configured - contact system administrator'}), 500
            
        setup_key = request.form.get('setup_key')
        if setup_key != required_setup_key:
            logging.warning(f"Invalid setup key attempt from {request.remote_addr}")
            return jsonify({'error': 'Invalid setup credentials'}), 401
            
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        if not all([username, password, email]):
            return jsonify({'error': 'All fields required'}), 400
            
        # Validate password strength
        if not password or len(password) < 12:
            return jsonify({'error': 'Password must be at least 12 characters'}), 400
            
        # Create secure admin user
        admin_user = User()
        admin_user.username = username
        admin_user.email = email
        admin_user.password_hash = generate_password_hash(password)
        admin_user.role = 'admin'
        admin_user.full_name = 'System Administrator'
        admin_user.department = 'Administration'
        admin_user.staff_type = 'admin'
        
        try:
            db.session.add(admin_user)
            db.session.commit()
            logging.info(f"Admin user {username} created successfully from {request.remote_addr}")
            
            # Remove setup capability after first admin
            return jsonify({'success': True, 'message': 'Admin created successfully - setup now disabled'})
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to create admin: {e}")
            return jsonify({'error': 'Failed to create admin'}), 500
    
    # GET request - show secure setup form
    if not os.environ.get('ADMIN_SETUP_KEY'):
        return jsonify({'error': 'Setup not available'}), 403
        
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Secure Admin Setup</title></head>
    <body>
    <form method="POST" style="max-width:400px;margin:50px auto;padding:20px;border:1px solid #ccc;">
        <h3>Secure Admin Setup</h3>
        <p style="color:#666;font-size:12px;">Contact system administrator for setup key</p>
        <input type="text" name="username" placeholder="Admin Username" required style="width:100%;margin:10px 0;padding:10px;"><br>
        <input type="password" name="password" placeholder="Secure Password (12+ chars)" required style="width:100%;margin:10px 0;padding:10px;"><br>
        <input type="email" name="email" placeholder="Admin Email" required style="width:100%;margin:10px 0;padding:10px;"><br>
        <input type="password" name="setup_key" placeholder="Secure Setup Key" required style="width:100%;margin:10px 0;padding:10px;"><br>
        <button type="submit" style="width:100%;padding:10px;background:#007bff;color:white;border:none;">Create Admin</button>
    </form>
    </body>
    </html>
    '''
from datetime import datetime, date, time
import pytz
import logging
import json
from functools import wraps
# Face recognition service removed - using biometric authentication
from location_service import location_service

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')
from qr_service import generate_monthly_qr_codes, get_today_qr_code, create_qr_code_image
from email_service import send_attendance_email, send_registration_confirmation_email
from enhanced_email_service import send_morning_absentee_alert, send_final_attendance_report
from absentee_service import approve_absentee, get_pending_approvals
import math

# Define dual attendance time windows - DISABLED FOR TESTING
MORNING_START_TIME = time(0, 0)   # 12:00 AM (Always available for testing)
MORNING_END_TIME = time(23, 59)   # 11:59 PM (Always available for testing)
EVENING_START_TIME = time(0, 0)   # 12:00 AM (Always available for testing)
EVENING_END_TIME = time(23, 59)   # 11:59 PM (Always available for testing)

def get_current_session():
    """Determine current attendance session based on time - ALWAYS MORNING FOR TESTING"""
    now_ist = datetime.now(IST).time()
    
    # For testing: always return morning session so attendance can be marked anytime
    return 'morning'

@app.route('/api/verify_location', methods=['POST'])
def verify_location():
    """API endpoint to verify if user is within college premises"""
    try:
        data = request.get_json()
        user_lat = data.get('latitude')
        user_lon = data.get('longitude')
        
        is_allowed, message = location_service.validate_attendance_location(user_lat, user_lon)
        
        # Store location verification in session if allowed
        if is_allowed:
            session['location_verified'] = True
            session['last_location_check'] = datetime.now().isoformat()
        
        return jsonify({
            'allowed': is_allowed,
            'message': message,
            'college_name': 'VEMU Institute of Technology',
            'boundary_type': 'Polygon boundary with 50m buffer zone'
        })
        
    except Exception as e:
        logging.error(f"Location verification error: {e}")
        return jsonify({
            'allowed': False,
            'error': str(e),
            'message': 'Location verification failed'
        }), 400

@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('faculty_dashboard'))
    
    # Check if user has bypassed location gate
    if 'location_verified' not in session:
        return render_template('location_gate.html')
    
    return redirect(url_for('login'))

@app.route('/location_gate')
def location_gate():
    """Display location verification gate"""
    return render_template('location_gate.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('faculty_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

# Face login completely removed - using biometric authentication via WebAuthn API

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Get filter parameters
    selected_department = request.args.get('department', '')
    selected_branch = request.args.get('branch', '')
    selected_staff_type = request.args.get('staff_type', '')
    
    # Get statistics
    total_faculty = User.query.filter_by(role='faculty').count()
    today_attendance = Attendance.query.filter_by(date=date.today()).count()
    
    # Get all departments and branches for filter dropdowns
    departments = db.session.query(User.department).filter(
        User.role == 'faculty',
        User.department.isnot(None),
        User.department != ''
    ).distinct().all()
    departments = [dept[0] for dept in departments if dept[0]]
    
    branches = db.session.query(User.branch).filter(
        User.role == 'faculty',
        User.branch.isnot(None),
        User.branch != ''
    ).distinct().all()
    branches = [branch[0] for branch in branches if branch[0]]
    
    # Build faculty query with filters
    faculty_query = User.query.filter_by(role='faculty')
    
    if selected_department:
        faculty_query = faculty_query.filter(User.department == selected_department)
    if selected_branch:
        faculty_query = faculty_query.filter(User.branch == selected_branch)
    if selected_staff_type:
        faculty_query = faculty_query.filter(User.staff_type == selected_staff_type)
    
    # Get faculty list with last attendance
    faculty_list = []
    for faculty in faculty_query.all():
        last_attendance = Attendance.query.filter_by(user_id=faculty.id).order_by(Attendance.date.desc()).first()
        faculty.last_attendance = last_attendance.date if last_attendance else None
        faculty_list.append(faculty)
    
    # Get recent attendances and convert to IST
    recent_attendances = db.session.query(Attendance, User).join(User).filter(
        Attendance.date == date.today()
    ).order_by(Attendance.scan_time.desc()).limit(10).all()
    
    # Convert scan times to IST
    for attendance, user in recent_attendances:
        if attendance.scan_time:
            attendance.scan_time_ist = attendance.scan_time.replace(tzinfo=pytz.UTC).astimezone(IST)
    
    # Prepare JSON data for user management JavaScript
    users_data = []
    for faculty in faculty_list:
        if faculty.role != 'admin':
            users_data.append({
                'id': faculty.id,
                'name': faculty.full_name or faculty.username,
                'username': faculty.username,
                'department': faculty.department or 'N/A'
            })
    
    users_json = json.dumps(users_data)
    
    return render_template('admin_dashboard.html', 
                         total_faculty=total_faculty,
                         today_attendance=today_attendance,
                         recent_attendances=recent_attendances,
                         faculty_list=faculty_list,
                         departments=departments,
                         branches=branches,
                         selected_department=selected_department,
                         selected_branch=selected_branch,
                         selected_staff_type=selected_staff_type,
                         users=faculty_list,
                         users_json=users_json)

@app.route('/admin/register_faculty', methods=['GET', 'POST'])
def register_faculty():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        full_name = request.form['full_name']
        department = request.form['department']
        branch = request.form.get('branch', '')
        password = request.form['password']
        # Face capture removed - using biometric registration
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if existing_user:
            error_message = 'Username or email already exists'
            if is_ajax:
                return jsonify({'success': False, 'error': error_message}), 400
            else:
                flash(error_message, 'error')
        else:
            # Create new faculty user
            new_faculty = User()
            new_faculty.username = username
            new_faculty.email = email
            new_faculty.full_name = full_name
            new_faculty.department = department
            new_faculty.branch = branch
            new_faculty.password_hash = generate_password_hash(password)
            new_faculty.role = 'faculty'
            new_faculty.staff_type = request.form.get('staff_type', 'teaching_faculty')
            
            db.session.add(new_faculty)
            db.session.commit()
            
            logging.info(f"New faculty registered: {new_faculty.username} (ID: {new_faculty.id})")
            
            # Check if biometric registration was scheduled
            biometric_scheduled = request.form.get('biometric_credential_data')
            biometric_message = ""
            if biometric_scheduled == 'schedule_biometric_registration':
                # Set a session flag for this user to complete biometric registration
                biometric_message = " Please ask them to register their fingerprint when they first log in."
                logging.info(f"Biometric registration scheduled for user {new_faculty.username}")
            
            # Send registration confirmation email
            try:
                send_registration_confirmation_email(email, full_name, new_faculty.staff_type, department)
                success_message = f'Faculty {full_name} registered successfully! Confirmation email sent.{biometric_message}'
            except Exception as e:
                logging.error(f"Failed to send registration email to {email}: {e}")
                success_message = f'Faculty {full_name} registered successfully! (Email notification failed){biometric_message}'
            
            if is_ajax:
                return jsonify({
                    'success': True, 
                    'message': success_message,
                    'user_id': new_faculty.id,
                    'username': username,
                    'full_name': full_name,
                    'biometric_scheduled': biometric_scheduled == 'schedule_biometric_registration'
                })
            else:
                flash(success_message, 'success')
                return redirect(url_for('admin_dashboard'))
    
    return render_template('register_faculty.html')

@app.route('/admin/register_non_teaching_faculty', methods=['GET', 'POST'])
def register_non_teaching_faculty():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        full_name = request.form['full_name']
        department = request.form['department']
        branch = request.form.get('branch', '')
        password = request.form['password']
        # Face capture removed - using biometric registration
        staff_type = 'non_teaching_faculty'
        
        # Check if username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            flash('Username or email already exists', 'error')
        else:
            # Biometric registration handled from user dashboard after faculty creation
# Biometric registration will be handled from user dashboard
            
            # Create new non-teaching faculty user
            new_user = User()
            new_user.username = username
            new_user.email = email
            new_user.full_name = full_name
            new_user.department = department
            new_user.branch = branch
            new_user.password_hash = generate_password_hash(password)
            new_user.role = 'faculty'
            new_user.staff_type = staff_type
# Face encoding removed - using biometric authentication
            
            db.session.add(new_user)
            db.session.commit()
            
            # Send registration confirmation email
            try:
                send_registration_confirmation_email(email, full_name, staff_type, department)
                flash(f'Non-Teaching Faculty {full_name} registered successfully! Confirmation email sent. Username: {username}, Password: {password}', 'success')
            except Exception as e:
                logging.error(f"Failed to send registration email to {email}: {e}")
                flash(f'Non-Teaching Faculty {full_name} registered successfully! Username: {username}, Password: {password} (Email notification failed)', 'success')
            
            return redirect(url_for('admin_dashboard'))
    
    return render_template('register_non_teaching_faculty.html')

@app.route('/register_worker', methods=['GET', 'POST'])
@admin_required
def register_worker():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form.get('email', f'{username}@company.local')  # Default email if not provided
        full_name = request.form['full_name']
        department = request.form['department']
        branch = request.form.get('branch', '')
        password = request.form['password']
        # Face capture removed - using biometric registration
        staff_type = 'worker'
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        
        if existing_user:
            flash('Username already exists', 'error')
        else:
            # Biometric registration handled from user dashboard after faculty creation
# Biometric registration will be handled from user dashboard
            
            # Create new worker user
            new_user = User()
            new_user.username = username
            new_user.email = email
            new_user.full_name = full_name
            new_user.department = department
            new_user.branch = branch
            new_user.password_hash = generate_password_hash(password)
            new_user.role = 'faculty'
            new_user.staff_type = staff_type
# Face encoding removed - using biometric authentication
            
            db.session.add(new_user)
            db.session.commit()
            
            # Send registration confirmation email
            try:
                send_registration_confirmation_email(email, full_name, staff_type, department)
                flash(f'Worker {full_name} registered successfully! Confirmation email sent. Username: {username}, Password: {password}', 'success')
            except Exception as e:
                logging.error(f"Failed to send registration email to {email}: {e}")
                flash(f'Worker {full_name} registered successfully! Username: {username}, Password: {password} (Email notification failed)', 'success')
            
            return redirect(url_for('admin_dashboard'))
    
    return render_template('register_worker.html')

@app.route('/admin/approve_absentee/<int:approval_id>')
def approve_absentee_request(approval_id):
    """Handle absentee approval from email links - no login required for admin convenience"""
    action = request.args.get('action', 'approve')
    approved_by = 'admin'  # Default admin for email approvals
    
    is_approved = action == 'approve'
    success, message = approve_absentee(approval_id, approved_by, is_approved)
    
    # Create a simple HTML response for email link clicks
    status_color = 'success' if success else 'danger'
    status_text = 'SUCCESS' if success else 'ERROR'
    action_past = 'Approved' if action == 'approve' else 'Denied'
    
    html_response = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Absentee Approval - Smart Attendance System</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    </head>
    <body class="bg-light">
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card shadow">
                        <div class="card-header bg-{status_color} text-white text-center">
                            <h4><i class="fas fa-check-circle me-2"></i>{status_text}</h4>
                        </div>
                        <div class="card-body text-center">
                            <h5 class="text-{status_color}">Absentee Request {action_past}</h5>
                            <p class="text-muted">{message}</p>
                            <div class="row mt-4">
                                <div class="col-md-6">
                                    <p><strong>Approval ID:</strong> <span class="badge bg-secondary">#{approval_id}</span></p>
                                </div>
                                <div class="col-md-6">
                                    <p><strong>Action:</strong> <span class="badge bg-{status_color}">{action.upper()}</span></p>
                                </div>
                            </div>
                            <p><strong>Processed by:</strong> {approved_by}</p>
                            <hr>
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-2"></i>
                                The approval has been processed successfully. You can close this window or navigate back to the admin dashboard.
                            </div>
                            <a href="/admin/pending_approvals" class="btn btn-primary me-2">
                                <i class="fas fa-list me-2"></i>View Pending Approvals
                            </a>
                            <a href="/admin" class="btn btn-secondary">
                                <i class="fas fa-tachometer-alt me-2"></i>Admin Dashboard  
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_response

@app.route('/admin/quick_approvals')
@admin_required  
def quick_approvals():
    """Quick approval interface for admins to bulk approve/deny requests"""
    today = datetime.now(IST).date()
    pending_approvals = get_pending_approvals(today)
    return render_template('quick_approvals.html', approvals=pending_approvals, date=today)

@app.route('/location_test')
def location_test():
    """GPS location testing page for admin debugging"""
    return render_template('location_test.html')

@app.route('/admin/send_morning_alert')
@admin_required
def send_morning_alert():
    success = send_morning_absentee_alert()
    if success:
        flash('Morning absentee alert sent successfully', 'success')
    else:
        flash('Failed to send morning alert', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/send_final_report') 
@admin_required
def send_final_report():
    success = send_final_attendance_report()
    if success:
        flash('Final attendance report sent successfully', 'success')
    else:
        flash('Failed to send final report', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/pending_approvals')
@admin_required
def view_pending_approvals():
    today = datetime.now(IST).date()
    pending_approvals = get_pending_approvals(today)
    return render_template('pending_approvals.html', approvals=pending_approvals, date=today)

@app.route('/admin/send_monthly_report')
def send_monthly_report():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        from datetime import datetime, timedelta
        from calendar import monthrange
        import calendar
        
        # Get current month and year or from request parameters
        now = datetime.now(IST)
        current_month = int(request.args.get('month', now.month))
        current_year = int(request.args.get('year', now.year))
        
        # Get month name
        month_name = calendar.month_name[current_month]
        
        # Calculate month date range
        first_day = datetime(current_year, current_month, 1)
        last_day_num = monthrange(current_year, current_month)[1]
        last_day = datetime(current_year, current_month, last_day_num)
        
        # Get all faculty members
        all_faculty = User.query.filter_by(role='faculty').all()
        
        # Get all attendance for the month
        monthly_attendance = db.session.query(Attendance, User).join(User).filter(
            Attendance.date >= first_day.date(),
            Attendance.date <= last_day.date()
        ).all()
        
        # Create monthly report data
        monthly_data = {}
        total_working_days = 0
        
        # Count working days (assuming Monday-Saturday, excluding Sundays)
        current_date = first_day
        while current_date <= last_day:
            if current_date.weekday() != 6:  # Not Sunday
                total_working_days += 1
            current_date += timedelta(days=1)
        
        # Process attendance data
        for faculty in all_faculty:
            faculty_attendances = [att for att, user in monthly_attendance if user.id == faculty.id]
            present_days = len(faculty_attendances)
            attendance_percentage = (present_days / total_working_days * 100) if total_working_days > 0 else 0
            
            monthly_data[faculty.id] = {
                'faculty': faculty,
                'present_days': present_days,
                'absent_days': total_working_days - present_days,
                'attendance_percentage': round(attendance_percentage, 2),
                'attendances': faculty_attendances
            }
        
        # Send email with monthly report
        subject = f"Monthly Attendance Report - {month_name} {current_year}"
        
        # Create email body
        html_body = f"""
        <html>
        <body>
            <h2>Monthly Attendance Report - {month_name} {current_year}</h2>
            <p><strong>Report Generated:</strong> {now.strftime('%d-%m-%Y %I:%M %p IST')}</p>
            <p><strong>Total Working Days:</strong> {total_working_days}</p>
            <p><strong>Total Faculty:</strong> {len(all_faculty)}</p>
            
            <h3>Summary by Staff Type:</h3>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px;">Staff Type</th>
                    <th style="padding: 8px;">Total Staff</th>
                    <th style="padding: 8px;">Avg Attendance %</th>
                </tr>
        """
        
        # Calculate summary by staff type
        staff_types = ['teaching_faculty', 'non_teaching_faculty', 'worker']
        for staff_type in staff_types:
            type_faculty = [f for f in all_faculty if f.staff_type == staff_type]
            if type_faculty:
                avg_percentage = sum([monthly_data[f.id]['attendance_percentage'] for f in type_faculty]) / len(type_faculty)
                type_name = staff_type.replace('_', ' ').title()
                html_body += f"""
                    <tr>
                        <td style="padding: 8px;">{type_name}</td>
                        <td style="padding: 8px;">{len(type_faculty)}</td>
                        <td style="padding: 8px;">{avg_percentage:.1f}%</td>
                    </tr>
                """
        
        html_body += """
            </table>
            
            <h3>Detailed Monthly Attendance:</h3>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px;">Name</th>
                    <th style="padding: 8px;">Staff Type</th>
                    <th style="padding: 8px;">Department</th>
                    <th style="padding: 8px;">Present Days</th>
                    <th style="padding: 8px;">Absent Days</th>
                    <th style="padding: 8px;">Attendance %</th>
                </tr>
        """
        
        # Sort faculty by attendance percentage (lowest first)
        sorted_faculty = sorted(all_faculty, key=lambda f: monthly_data[f.id]['attendance_percentage'])
        
        for faculty in sorted_faculty:
            data = monthly_data[faculty.id]
            color = '#ffcccc' if data['attendance_percentage'] < 50 else ('#ffffcc' if data['attendance_percentage'] < 80 else '#ccffcc')
            staff_type_display = faculty.staff_type.replace('_', ' ').title()
            
            html_body += f"""
                <tr style="background-color: {color};">
                    <td style="padding: 8px;">{faculty.full_name or faculty.username}</td>
                    <td style="padding: 8px;">{staff_type_display}</td>
                    <td style="padding: 8px;">{faculty.department or 'N/A'}</td>
                    <td style="padding: 8px;">{data['present_days']}</td>
                    <td style="padding: 8px;">{data['absent_days']}</td>
                    <td style="padding: 8px;"><strong>{data['attendance_percentage']}%</strong></td>
                </tr>
            """
        
        html_body += """
            </table>
            <br>
            <p><em>Color coding: Red < 50%, Yellow 50-79%, Green ≥ 80%</em></p>
            <p>Generated by Smart Attendance System</p>
        </body>
        </html>
        """
        
        # Send email using email service
        from enhanced_email_service import send_email_with_attachments
        recipients = ['nlramcharanplacement@gmail.com', '2224m1a3133@vemu.org', 'hodcse@vemu.org']
        
        success = send_email_with_attachments(recipients, subject, html_body, [])
        
        if success:
            flash(f'Monthly report for {month_name} {current_year} sent successfully!', 'success')
        else:
            flash('Failed to send monthly report. Please check email configuration.', 'error')
            
    except Exception as e:
        flash(f'Error generating monthly report: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Face attendance marking removed - using biometric attendance
# Use /api/webauthn/attendance/begin and /api/webauthn/attendance/complete instead
# Face attendance code removed - using biometric attendance via WebAuthn API

@app.route('/admin/generate_qr')
def generate_qr():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        qr_codes = generate_monthly_qr_codes()
        flash(f'Generated {len(qr_codes)} QR codes for the month', 'success')
    except Exception as e:
        flash(f'Error generating QR codes: {str(e)}', 'error')
        logging.error(f"QR generation error: {e}")
    
    # Get today's QR code to display
    today_qr = get_today_qr_code()
    
    return render_template('generate_qr.html', today_qr=today_qr)

@app.route('/faculty/dashboard')
def faculty_dashboard():
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    # Check if user has already marked attendance today
    today_attendance = Attendance.query.filter_by(
        user_id=user.id,
        date=date.today()
    ).first()
    
    # Check if current time is within attendance window (9:00 AM - 4:00 PM IST)
    ist_now = datetime.now(IST)
    current_time = ist_now.time()
    
    # Check current session and allow attendance marking
    current_session = get_current_session()
    can_mark_attendance = current_session is not None and not today_attendance
    
    # Convert today_attendance scan_time to IST if it exists
    if today_attendance and today_attendance.scan_time:
        today_attendance.scan_time_ist = today_attendance.scan_time.replace(tzinfo=pytz.UTC).astimezone(IST)
    
    return render_template('faculty_dashboard.html', 
                         user=user,
                         today_attendance=today_attendance,
                         can_mark_attendance=can_mark_attendance,
                         current_time=current_time,
                         current_session=current_session)

@app.route('/faculty/scan_qr')
def scan_qr():
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect(url_for('login'))
    
    # Check if current time is within attendance window (IST)
    ist_now = datetime.now(IST)
    current_time = ist_now.time()
    
    current_session = get_current_session()
    if current_session is None:
        flash('Attendance can only be marked during: Morning (9:00 AM - 2:00 PM) or Evening (4:00 PM - 5:30 PM) IST', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    # Check if already marked attendance today
    today_attendance = Attendance.query.filter_by(
        user_id=session['user_id'],
        date=date.today()
    ).first()
    
    if today_attendance:
        flash('You have already marked attendance for today', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    return render_template('scan_qr.html')

@app.route('/api/verify_qr', methods=['POST'])
def verify_qr():
    if 'user_id' not in session or session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    data = request.get_json()
    scanned_code = data.get('code')
    user_lat = data.get('latitude')
    user_lon = data.get('longitude')
    
    if not scanned_code:
        return jsonify({'success': False, 'message': 'No QR code provided'})
    

    
    # Check if current time is within attendance window (IST)
    current_session = get_current_session()
    if current_session is None:
        return jsonify({'success': False, 'message': 'Attendance can only be marked during: Morning (9:00 AM - 2:00 PM) or Evening (4:00 PM - 5:30 PM) IST'})
    
    # Verify QR code
    today_qr = get_today_qr_code()
    if not today_qr or today_qr.code != scanned_code:
        return jsonify({'success': False, 'message': 'Invalid QR code'})
    
    # Check if already marked attendance
    existing_attendance = Attendance.query.filter_by(
        user_id=session['user_id'],
        date=date.today()
    ).first()
    
    if existing_attendance:
        return jsonify({'success': False, 'message': 'Already marked attendance today'})
    
    # Mark attendance with session info
    attendance = Attendance()
    attendance.user_id = session['user_id']
    attendance.date = date.today()
    attendance.session = current_session
    attendance.status = 'present'
    
    db.session.add(attendance)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Attendance marked successfully!'})



@app.route('/admin/send_email')
def send_email():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        result = send_attendance_email()
        if result:
            flash('Attendance email sent successfully', 'success')
        else:
            flash('Failed to send attendance email', 'error')
    except Exception as e:
        flash(f'Error sending email: {str(e)}', 'error')
        logging.error(f"Email sending error: {e}")
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/download_qr/<date_str>')
def download_qr(date_str):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    try:
        from datetime import datetime
        qr_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        qr_code = QRCode.query.filter_by(date=qr_date).first()
        
        if not qr_code:
            flash('QR code not found for this date', 'error')
            return redirect(url_for('generate_qr'))
        
        # Create QR code image
        qr_img = create_qr_code_image(qr_code.code)
        
        # Save to BytesIO
        from io import BytesIO
        img_io = BytesIO()
        qr_img.save(img_io, 'PNG')
        img_io.seek(0)
        
        from flask import send_file
        return send_file(
            img_io,
            mimetype='image/png',
            as_attachment=True,
            download_name=f'qr_code_{date_str}.png'
        )
        
    except Exception as e:
        flash(f'Error downloading QR code: {str(e)}', 'error')
        logging.error(f"QR download error: {e}")
        return redirect(url_for('generate_qr'))

@app.route('/admin/download_app')
@admin_required
def download_app():
    """Download the complete application as a ZIP file"""
    try:
        import zipfile
        import tempfile
        from datetime import datetime
        
        # Create temporary ZIP file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        # Files to include in the download
        files_to_include = [
            'app.py', 'main.py', 'routes.py', 'models.py',
            'email_service.py', 'qr_service.py', 'scheduler.py',
            'setup.py', 'README.md'
        ]
        
        # Template and static files
        template_files = []
        static_files = []
        
        # Get template files
        import os
        if os.path.exists('templates'):
            for file in os.listdir('templates'):
                if file.endswith('.html'):
                    template_files.append(os.path.join('templates', file))
        
        # Get static files
        if os.path.exists('static'):
            for root, dirs, files in os.walk('static'):
                for file in files:
                    static_files.append(os.path.join(root, file))
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add main application files
            for file in files_to_include:
                if os.path.exists(file):
                    zipf.write(file, file)
            
            # Add template files
            for file in template_files:
                if os.path.exists(file):
                    zipf.write(file, file)
            
            # Add static files
            for file in static_files:
                if os.path.exists(file):
                    zipf.write(file, file)
            
            # Create a sample .env file
            env_sample = """# Smart Attendance System Configuration
# Replace with your actual values

SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SESSION_SECRET=your_secret_key_here
DATABASE_URL=sqlite:///attendance.db
"""
            zipf.writestr('.env.sample', env_sample)
            
            # Create installation instructions
            install_txt = """Smart Attendance System - Installation Instructions

1. Extract this ZIP file to a folder
2. Install Python 3.8 or higher
3. Run: python setup.py (this will install all required packages)
4. Copy .env.sample to .env and edit with your credentials
5. Run: python main.py
6. Access at http://localhost:5000
7. Login with admin/admin123

For Gmail setup:
- Enable 2-Factor Authentication
- Generate App Password for Mail
- Use app password in .env file

Email recipients can be changed in email_service.py
Attendance window can be modified in routes.py and scheduler.py
"""
            zipf.writestr('INSTALL.txt', install_txt)
        
        temp_zip.close()
        
        # Generate filename with current date
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f'smart_attendance_system_{date_str}.zip'
        
        return send_file(
            temp_zip.name,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        flash(f'Error creating download: {str(e)}', 'error')
        logging.error(f"App download error: {e}")
        return redirect(url_for('admin_dashboard'))

# =======================
# WebAuthn API Endpoints
# =======================

from webauthn_service import webauthn_service

@app.route('/api/webauthn/register/begin', methods=['POST'])
def webauthn_register_begin():
    """Begin biometric registration for current user"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        user_id = session['user_id']
        
        # Ensure user is registering for themselves (not for others during admin registration)
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        options = webauthn_service.begin_registration(user_id)
        
        return jsonify(options)
        
    except Exception as e:
        logging.error(f"WebAuthn register begin error: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/webauthn/register/begin/<int:target_user_id>', methods=['POST'])
def webauthn_register_begin_for_user(target_user_id):
    """Begin biometric registration for a specific user (admin use during registration)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        # Check if current user is admin
        current_user = User.query.get(session['user_id'])
        if not current_user or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Check if target user exists
        target_user = User.query.get(target_user_id)
        if not target_user:
            return jsonify({'error': 'Target user not found'}), 404
        
        options = webauthn_service.begin_registration(target_user_id)
        
        return jsonify(options)
        
    except Exception as e:
        logging.error(f"WebAuthn register begin for user error: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/webauthn/register/complete/<int:target_user_id>', methods=['POST'])
def webauthn_register_complete_for_user(target_user_id):
    """Complete biometric registration for a specific user (admin use during registration)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        # Check if current user is admin
        current_user = User.query.get(session['user_id'])
        if not current_user or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Check if target user exists
        target_user = User.query.get(target_user_id)
        if not target_user:
            return jsonify({'error': 'Target user not found'}), 404
        
        credential_data = request.json
        if not credential_data:
            return jsonify({'error': 'No credential data provided'}), 400
        
        op_id = credential_data.get('opId')
        if not op_id:
            return jsonify({'error': 'Operation ID required'}), 400
            
        success = webauthn_service.complete_registration(target_user_id, credential_data, op_id)
        
        if success:
            return jsonify({'success': True, 'message': f'Biometric registration successful for {target_user.username}'})
        else:
            return jsonify({'error': 'Registration failed'}), 400
        
    except Exception as e:
        logging.error(f"WebAuthn register complete for user error: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/webauthn/register/complete', methods=['POST'])
def webauthn_register_complete():
    """Complete biometric registration for current user"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        user_id = session['user_id']
        credential_data = request.json
        if not credential_data:
            return jsonify({'error': 'No credential data provided'}), 400
        
        op_id = credential_data.get('opId')
        if not op_id:
            return jsonify({'error': 'Operation ID required'}), 400
            
        success = webauthn_service.complete_registration(user_id, credential_data, op_id)
        
        if success:
            return jsonify({'success': True, 'message': 'Biometric registration successful'})
        else:
            return jsonify({'error': 'Registration failed'}), 400
        
    except Exception as e:
        logging.error(f"WebAuthn register complete error: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/api/webauthn/authenticate/begin', methods=['POST'])
def webauthn_authenticate_begin():
    """Begin biometric authentication"""
    try:
        data = request.json or {}
        username = data.get('username')
        
        # Validate that there are some biometric credentials in the system
        credentials_count = BiometricCredential.query.filter_by(is_active=True).count()
        if credentials_count == 0:
            return jsonify({'error': 'No biometric credentials found in the system. Please register your fingerprint first.'}), 400
        
        options = webauthn_service.begin_authentication(username)
        logging.info(f"WebAuthn authentication options generated successfully")
        
        return jsonify(options)
        
    except Exception as e:
        logging.error(f"WebAuthn authenticate begin error: {e}")
        return jsonify({'error': f'Failed to get authentication options: {str(e)}'}), 400

@app.route('/api/webauthn/authenticate/complete', methods=['POST'])
def webauthn_authenticate_complete():
    """Complete biometric authentication and login user"""
    try:
        credential_data = request.json
        if not credential_data:
            return jsonify({'error': 'No credential data provided'}), 400
        
        # Validate required fields
        required_fields = ['id', 'rawId', 'response', 'type', 'opId']
        for field in required_fields:
            if field not in credential_data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        op_id = credential_data.get('opId')
        verified, user = webauthn_service.complete_authentication(credential_data, op_id)
        
        if verified and user:
            # Login the user
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session.permanent = True  # Make session permanent
            
            # Determine redirect based on role
            redirect_url = url_for('admin_dashboard') if user.role == 'admin' else url_for('faculty_dashboard')
            
            logging.info(f"Biometric login successful for {user.username}, redirecting to {redirect_url}")
            
            return jsonify({
                'success': True, 
                'message': f'Biometric login successful! Welcome {user.full_name or user.username}',
                'redirect': redirect_url
            })
        else:
            return jsonify({'error': 'Biometric authentication failed. Please try again or use password login.'}), 401
        
    except Exception as e:
        logging.error(f"WebAuthn authenticate complete error: {e}")
        error_message = str(e)
        if "No challenge found" in error_message:
            error_message = "Authentication session expired. Please try again."
        elif "Credential not found" in error_message:
            error_message = "Fingerprint not recognized. Please register your fingerprint first."
        return jsonify({'error': error_message}), 400

@app.route('/api/webauthn/attendance/begin', methods=['POST'])
def webauthn_attendance_begin():
    """Begin biometric authentication for attendance marking"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        user_id = session['user_id']
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # CRITICAL: Prevent duplicate requests with immediate database lock
        attendance_operation_key = f"attendance_operation_{user_id}"
        if attendance_operation_key in session:
            logging.warning(f"Duplicate attendance request blocked for user {user.username}")
            return jsonify({'error': 'Attendance authentication already in progress. Please wait and try again.'}), 429
        
        # Immediately set the operation flag and commit to session to prevent race conditions
        session[attendance_operation_key] = True
        session.permanent = True  # Ensure session is persistent
        session.modified = True
        
        # Force session save immediately (removed problematic call)
        
        # Check if user has biometric credentials
        credentials = BiometricCredential.query.filter_by(
            user_id=user_id, 
            is_active=True
        ).count()
        
        if credentials == 0:
            return jsonify({'error': 'No biometric credentials found. Please register your fingerprint first.'}), 400
        
        # Check if within attendance time window - DISABLED FOR TESTING
        from datetime import datetime
        import pytz
        IST = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(IST)
        current_session = get_current_session()
        
        # Time restrictions disabled for testing - attendance can be marked anytime
        if not current_session:
            current_session = 'morning'  # Force morning session for testing
        
        # Check if attendance already marked for current session
        today = now_ist.date()
        existing_attendance = Attendance.query.filter_by(
            user_id=user_id,
            date=today,
            session=current_session
        ).first()
        
        if existing_attendance:
            return jsonify({'error': f'Attendance already marked for {current_session} session today'}), 400
        
        options = webauthn_service.begin_authentication(user.username)
        logging.info(f"Biometric attendance authentication options generated for {user.username}")
        
        # Mark attendance operation as active to prevent duplicates
        session[attendance_operation_key] = True
        
        return jsonify(options)
        
    except Exception as e:
        logging.error(f"WebAuthn attendance begin error: {e}")
        return jsonify({'error': f'Failed to prepare attendance authentication: {str(e)}'}), 400

@app.route('/api/webauthn/attendance/complete', methods=['POST'])
def webauthn_attendance_complete():
    """Complete biometric authentication and mark attendance"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        user_id = session['user_id']
        attendance_operation_key = f"attendance_operation_{user_id}"
        
        data = request.json
        if not data:
            # Clear operation flag on error
            session.pop(attendance_operation_key, None)
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['id', 'rawId', 'response', 'type', 'opId']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        credential_data = {k: v for k, v in data.items() if k not in ['photo', 'opId']}
        photo_data = data.get('photo')
        op_id = data.get('opId')
        
        if not photo_data:
            return jsonify({'error': 'Photo data required for attendance verification'}), 400
        
        # Additional security checks before marking attendance
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check location verification (for testing, allow it to be bypassed with a warning)
        if 'location_verified' not in session:
            logging.warning(f"Location verification bypassed for testing - user {user.username}")
            # Set location as verified to allow testing
            session['location_verified'] = True
        
        try:
            success, session_name = webauthn_service.mark_attendance_with_biometric(
                user_id, credential_data, photo_data, op_id
            )
            
            if success:
                # Clear operation flag on success
                session.pop(attendance_operation_key, None)
                logging.info(f"Biometric attendance successfully marked for {user.username} - {session_name} session")
                return jsonify({
                    'success': True, 
                    'message': f'Attendance marked successfully! {session_name.title()} session attendance recorded with biometric verification.',
                    'session': session_name
                })
            else:
                # Clear operation flag on failure
                session.pop(attendance_operation_key, None)
                return jsonify({'error': 'Failed to mark attendance'}), 400
        
        except Exception as attendance_error:
            logging.error(f"Attendance marking failed for {user.username}: {attendance_error}")
            raise
        
    except Exception as e:
        # Clear operation flag on any error
        if 'user_id' in session:
            user_id = session['user_id']
            attendance_operation_key = f"attendance_operation_{user_id}"
            session.pop(attendance_operation_key, None)
        
        logging.error(f"WebAuthn attendance complete error: {e}")
        error_message = str(e)
        
        # Provide more user-friendly error messages
        if "Attendance can only be marked during" in error_message:
            error_message = "Attendance window has closed. Please mark attendance during allowed hours."
        elif "already marked" in error_message:
            error_message = "Attendance already marked for this session today."
        elif "Biometric verification failed" in error_message:
            error_message = "Fingerprint verification failed. Please try again."
        elif "No challenge found" in error_message:
            error_message = "Authentication session expired. Please try again."
        
        return jsonify({'error': error_message}), 400

@app.route('/api/webauthn/attendance/mark', methods=['POST'])
def webauthn_attendance_mark_atomic():
    """Single atomic endpoint for biometric attendance marking"""
    try:
        from datetime import datetime
        import pytz
        
        logging.info(f"Biometric attendance request received: {request.method}")
        
        if 'user_id' not in session:
            logging.error("User not logged in for attendance marking")
            return jsonify({'error': 'User not logged in'}), 401
        
        user_id = session['user_id']
        user = User.query.get(user_id)
        if not user:
            logging.error(f"User {user_id} not found in database")
            return jsonify({'error': 'User not found'}), 404
        
        logging.info(f"Processing attendance request for user {user.username}")
        
        # Define operation key at function scope for all code paths
        attendance_operation_key = f"attendance_operation_{user_id}"
        
        # Check if user has biometric credentials FIRST
        credentials = BiometricCredential.query.filter_by(
            user_id=user_id, 
            is_active=True
        ).count()
        
        if credentials == 0:
            logging.error(f"No biometric credentials found for user {user.username}")
            return jsonify({'error': 'No biometric credentials found. Please register your fingerprint first.'}), 400
        
        # Get request data - handle both empty body and full data
        data = request.json if request.json else {}
        logging.info(f"Request data keys: {list(data.keys())}")
        
        # STEP 1: If no assertion data, return authentication options (first call)
        if 'assertion' not in data:
            logging.info(f"Generating authentication options for {user.username}")
            
            try:
                options = webauthn_service.begin_authentication(user.username)
                logging.info(f"Authentication options generated successfully for {user.username}")
                return jsonify(options)
            except Exception as e:
                logging.error(f"Failed to generate auth options: {e}")
                return jsonify({'error': f'Failed to prepare authentication: {str(e)}'}), 400
        
        # Complete biometric verification and mark attendance atomically
        assertion_data = data.get('assertion')
        photo_data = data.get('photo')
        
        if not assertion_data or not photo_data:
            return jsonify({'error': 'Both biometric assertion and photo required'}), 400
        
        # Check time window and existing attendance
        IST = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(IST)
        current_session = get_current_session()
        
        # Time restrictions disabled for testing
        if not current_session:
            current_session = 'morning'
        
        today = now_ist.date()
        existing_attendance = Attendance.query.filter_by(
            user_id=user_id,
            date=today,
            session=current_session
        ).first()
        
        if existing_attendance:
            return jsonify({'error': f'Attendance already marked for {current_session} session today'}), 400
        
        # ATOMIC OPERATION: Verify biometric and mark attendance
        try:
            # Verify biometric authentication
            op_id = assertion_data.get('opId')
            credential_data = {k: v for k, v in assertion_data.items() if k != 'opId'}
            
            verified, auth_user = webauthn_service.complete_authentication(credential_data, op_id)
            
            if not verified or not auth_user or auth_user.id != user_id:
                raise ValueError("Biometric verification failed")
            
            # STEP 1: Create attendance record FIRST (most important data)
            attendance = Attendance()
            attendance.user_id = user_id
            attendance.date = today
            attendance.session = current_session
            attendance.status = 'present'
            attendance.biometric_confidence = 100.0
            
            db.session.add(attendance)
            db.session.flush()  # Get attendance ID but don't commit yet
            attendance_id = attendance.id
            
            # STEP 2: Save photo (optional - if this fails, attendance still recorded)
            photo_filename = None
            try:
                photo_filename = f"attendance_{user_id}_{today}_{current_session}_{now_ist.strftime('%H%M%S')}.jpg"
                photo_path = os.path.join('static', 'attendance_photos', photo_filename)
                
                # Create directory if needed
                os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                
                # Save photo data
                if photo_data.startswith('data:image'):
                    photo_data = photo_data.split(',')[1]
                
                import base64
                with open(photo_path, 'wb') as f:
                    f.write(base64.b64decode(photo_data))
                
                # Create photo record
                attendance_photo = AttendancePhoto()
                attendance_photo.attendance_id = attendance_id
                attendance_photo.photo_filename = photo_filename
                attendance_photo.verification_method = 'biometric'
                
                db.session.add(attendance_photo)
                
            except Exception as photo_error:
                logging.warning(f"Photo save failed but attendance will still be recorded: {photo_error}")
            
            # STEP 3: Commit everything (attendance guaranteed, photo optional)
            db.session.commit()
            
            logging.info(f"Biometric attendance successfully marked for {user.username} - {current_session} session")
            return jsonify({
                'success': True,
                'message': f'Attendance marked successfully! {current_session.title()} session attendance recorded with biometric verification.',
                'session': current_session,
                'photo_saved': photo_filename is not None
            })
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Atomic attendance marking failed: {e}")
            raise
        
    except Exception as e:
        # Clear operation flag on any error
        if 'user_id' in session:
            user_id = session['user_id']
            attendance_operation_key = f"attendance_operation_{user_id}"
            session.pop(attendance_operation_key, None)
        
        logging.error(f"WebAuthn atomic attendance error: {e}")
        error_message = str(e)
        
        # User-friendly error messages
        if "already marked" in error_message:
            error_message = "Attendance already marked for this session today."
        elif "Biometric verification failed" in error_message:
            error_message = "Fingerprint verification failed. Please try again."
        elif "No challenge found" in error_message:
            error_message = "Authentication session expired. Please try again."
        
        return jsonify({'error': error_message}), 400

@app.route('/api/webauthn/status', methods=['GET'])
def webauthn_status():
    """Check biometric registration status for current user"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401
        
        user_id = session['user_id']
        credentials = BiometricCredential.query.filter_by(
            user_id=user_id,
            is_active=True
        ).count()
        
        return jsonify({
            'registered': credentials > 0,
            'hasCredentials': credentials > 0,  # For backward compatibility
            'count': credentials
        })
        
    except Exception as e:
        logging.error(f"WebAuthn status error: {e}")
        return jsonify({'error': str(e)}), 400

# User Management Routes
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    """Delete a specific user (admin only)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Access denied'}), 401
        
        current_user = User.query.get(session['user_id'])
        if not current_user or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        success, message = delete_user_safely(user_id, current_user.username)
        
        if success:
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        logging.error(f"Admin delete user error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/delete_all_faculty', methods=['POST'])
def admin_delete_all_faculty():
    """Delete all faculty users (admin only)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Access denied'}), 401
        
        current_user = User.query.get(session['user_id'])
        if not current_user or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Require confirmation token
        confirmation = request.json.get('confirmation') if request.json else None
        if confirmation != 'DELETE_ALL_FACULTY':
            return jsonify({'error': 'Invalid confirmation token'}), 400
        
        success, message, count = delete_all_faculty(current_user.username)
        
        if success:
            return jsonify({'success': True, 'message': message, 'deleted_count': count})
        else:
            return jsonify({'error': message, 'deleted_count': count}), 400
            
    except Exception as e:
        logging.error(f"Admin delete all faculty error: {e}")
        return jsonify({'error': str(e)}), 500

# Session maintenance routes (authenticated)
@app.route('/admin/clear_biometric_sessions', methods=['POST'])
def admin_clear_biometric_sessions():
    """Clear stuck biometric operation sessions (Admin only)"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Access denied'}), 401
        
        current_user = User.query.get(session['user_id'])
        if not current_user or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        cleared_count = 0
        
        # This is a server-side operation that clears session flags
        # In practice, users can refresh their browser to clear client-side sessions
        logging.info(f"Admin {current_user.username} cleared biometric sessions")
        
        return jsonify({
            'success': True, 
            'message': 'Session flags cleared. Faculty members should refresh their browsers to clear any stuck biometric operations.',
            'cleared_count': cleared_count
        })
    except Exception as e:
        logging.error(f"Admin clear sessions error: {e}")
        return jsonify({'error': str(e)}), 500




