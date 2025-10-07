from app import db
from datetime import datetime
from sqlalchemy.sql import func
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='faculty')  # 'admin' or 'faculty'
    full_name = db.Column(db.String(100), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    branch = db.Column(db.String(100), nullable=True)  # Added branch field for better organization
    staff_type = db.Column(db.String(50), nullable=False, default='teaching_faculty')  # teaching_faculty, non_teaching_faculty, worker
    # Photos captured during biometric attendance for verification
    created_at = db.Column(db.DateTime, default=func.now())
    
    def __repr__(self):
        return f'<User {self.username}>'

class QRCode(db.Model):
    __tablename__ = 'qr_code'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(255), unique=True, nullable=False)
    date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=func.now())
    
    def __repr__(self):
        return f'<QRCode {self.code} for {self.date}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scan_time = db.Column(db.DateTime, default=func.now())
    date = db.Column(db.Date, nullable=False)
    session = db.Column(db.String(20), nullable=False, default='morning')  # 'morning' or 'evening'
    status = db.Column(db.String(20), default='present')  # 'present' or 'absent'
    biometric_confidence = db.Column(db.Float, nullable=True)  # Biometric authentication confidence score
    
    # Relationships
    user = db.relationship('User', backref='attendances')
    
    def __repr__(self):
        return f'<Attendance {self.user.username} on {self.date} ({self.session})>'

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    recipients = db.Column(db.Text, nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    sent_at = db.Column(db.DateTime, default=func.now())
    status = db.Column(db.String(20), default='sent')  # 'sent' or 'failed'
    
    def __repr__(self):
        return f'<EmailLog {self.subject} on {self.date}>'

class AbsenteeApproval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    session = db.Column(db.String(20), nullable=False)  # 'morning' or 'evening'
    is_approved = db.Column(db.Boolean, nullable=True)  # None=pending, True=approved, False=denied
    approved_by = db.Column(db.String(100), nullable=True)  # Admin who approved/denied
    reason = db.Column(db.Text, nullable=True)  # Reason for absence
    created_at = db.Column(db.DateTime, default=func.now())
    approved_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='absentee_approvals')
    
    def __repr__(self):
        return f'<AbsenteeApproval {self.user.username} on {self.date} ({self.session})>'

class BiometricCredential(db.Model):
    """Store WebAuthn biometric credentials for users"""
    __tablename__ = 'biometric_credential'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    credential_id = db.Column(db.Text, nullable=False, unique=True)  # WebAuthn credential ID
    public_key = db.Column(db.Text, nullable=False)  # Public key for verification
    sign_count = db.Column(db.Integer, default=0)  # Counter for replay attack prevention
    device_type = db.Column(db.String(50), nullable=True)  # 'platform' or 'cross-platform'
    aaguid = db.Column(db.String(36), nullable=True)  # Authenticator AAGUID
    created_at = db.Column(db.DateTime, default=func.now())
    last_used = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('biometric_credentials', lazy='dynamic'))
    
    def __repr__(self):
        return f'<BiometricCredential {self.user.username} - {self.device_type}>'

class AttendancePhoto(db.Model):
    """Store photos captured during attendance marking"""
    __tablename__ = 'attendance_photo'
    
    id = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(db.Integer, db.ForeignKey('attendance.id'), nullable=False)
    photo_filename = db.Column(db.String(255), nullable=False)
    verification_method = db.Column(db.String(50), nullable=False)  # 'biometric', 'qr'
    created_at = db.Column(db.DateTime, default=func.now())
    
    # Relationships
    attendance = db.relationship('Attendance', backref=db.backref('photos', lazy='dynamic'))
    
    def __repr__(self):
        return f'<AttendancePhoto {self.photo_filename} - {self.verification_method}>'

class WebAuthnOperation(db.Model):
    """Server-side storage for WebAuthn operations to avoid session cookie race conditions"""
    __tablename__ = 'webauthn_operation'
    
    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.String(36), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    challenge = db.Column(db.Text, nullable=False)
    issued_at = db.Column(db.DateTime, default=func.now(), nullable=False)
    
    user = db.relationship('User', backref=db.backref('webauthn_operations', lazy='dynamic'))
    
    def __repr__(self):
        return f'<WebAuthnOperation {self.op_id}>'
