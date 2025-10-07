import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, date
import pytz
from app import db
import os
import tempfile
import logging
from models import User, Attendance, EmailLog, AbsenteeApproval
from absentee_service import get_morning_absentees, create_absentee_approval_request
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

# Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "marcus189076@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "ggeg knjd qtku ssrb")

ADMIN_EMAILS = [
    "nlramcharanplacement@gmail.com",
    "2224m1a3133@vemu.org",
    "hodcse@vemu.org"
]

def send_morning_absentee_alert():
    """Send morning absentee alert at 2:00 PM for admin approval"""
    try:
        today = datetime.now(IST).date()
        absentees = get_morning_absentees(today)
        
        if not absentees:
            logging.info("No morning absentees found")
            return True
        
        # Create absentee approval requests
        for absentee in absentees:
            create_absentee_approval_request(absentee.id, today, 'morning')
        
        # Create HTML email with approval buttons
        subject = f"Morning Absentee Alert - {today.strftime('%B %d, %Y')} - ACTION REQUIRED"
        
        html_body = f"""
        <html>
        <head>
            <style>
                .absent-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                .absent-table th, .absent-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                .absent-table th {{ background-color: #f2f2f2; font-weight: bold; }}
                .approve-btn {{ background-color: #28a745; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-right: 5px; }}
                .deny-btn {{ background-color: #dc3545; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; }}
                .staff-badge {{ padding: 4px 8px; border-radius: 12px; color: white; font-size: 12px; }}
                .teaching {{ background-color: #007bff; }}
                .non-teaching {{ background-color: #28a745; }}
                .worker {{ background-color: #ffc107; color: #000; }}
            </style>
        </head>
        <body>
            <h2>🚨 Morning Session Absentee Alert</h2>
            <p><strong>Date:</strong> {today.strftime('%B %d, %Y')}</p>
            <p><strong>Session:</strong> Morning (9:00 AM - 2:00 PM)</p>
            <p><strong>Time Generated:</strong> {datetime.now(IST).strftime('%I:%M %p IST')}</p>
            
            <h3>❌ Faculty Members Absent from Morning Session</h3>
            <p><strong>Total Absentees:</strong> {len(absentees)}</p>
            
            <table class="absent-table">
                <tr>
                    <th>S.No</th>
                    <th>Name</th>
                    <th>Staff Type</th>
                    <th>Department</th>
                    <th>Username</th>
                    <th>Action Required</th>
                </tr>
        """
        
        # Get the actual Replit URL or use localhost for development
        base_url = os.getenv("REPLIT_URL")
        if not base_url:
            # Try to construct from environment variables
            replit_slug = os.getenv("REPL_SLUG")
            replit_owner = os.getenv("REPL_OWNER") 
            if replit_slug and replit_owner:
                base_url = f"https://{replit_slug}.{replit_owner}.replit.app"
            else:
                base_url = "https://your-replit-app.replit.app"  # Replace with your actual URL
        
        for i, faculty in enumerate(absentees, 1):
            staff_type_display = faculty.staff_type.replace('_', ' ').title()
            badge_class = {
                'teaching_faculty': 'teaching',
                'non_teaching_faculty': 'non-teaching', 
                'worker': 'worker'
            }.get(faculty.staff_type, 'teaching')
            
            approval_request = AbsenteeApproval.query.filter_by(
                user_id=faculty.id,
                date=today,
                session='morning'
            ).first()
            
            if approval_request:
                approve_url = f"{base_url}/admin/approve_absentee/{approval_request.id}?action=approve"
                deny_url = f"{base_url}/admin/approve_absentee/{approval_request.id}?action=deny"
                
                html_body += f"""
                    <tr>
                        <td>{i}</td>
                        <td><strong>{faculty.full_name or faculty.username}</strong></td>
                        <td><span class="staff-badge {badge_class}">{staff_type_display}</span></td>
                        <td>{faculty.department or 'N/A'}</td>
                        <td>{faculty.username}</td>
                        <td>
                            <a href="{approve_url}" class="approve-btn">✅ APPROVE</a>
                            <a href="{deny_url}" class="deny-btn">❌ DENY</a>
                        </td>
                    </tr>
                """
        
        html_body += """
            </table>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4>📋 Instructions:</h4>
                <ul>
                    <li><strong>APPROVE:</strong> Click if the faculty member had valid permission to be absent</li>
                    <li><strong>DENY:</strong> Click if the absence was unauthorized</li>
                    <li>After you complete the approvals, a final attendance report will be sent</li>
                    <li>Please respond within 2 hours for timely processing</li>
                </ul>
            </div>
            
            <p style="color: #666; font-size: 12px;">
                <em>This is an automated alert from Smart Attendance System. 
                Please review and approve/deny each absence to ensure accurate records.</em>
            </p>
        </body>
        </html>
        """
        
        # Send email
        success = send_email(ADMIN_EMAILS, subject, html_body)
        
        # Log email
        if success:
            log_email(today, ADMIN_EMAILS, subject, 'sent')
            logging.info(f"Morning absentee alert sent successfully for {len(absentees)} absentees")
        else:
            log_email(today, ADMIN_EMAILS, subject, 'failed')
            logging.error("Failed to send morning absentee alert")
        
        return success
        
    except Exception as e:
        logging.error(f"Error sending morning absentee alert: {e}")
        return False

def send_final_attendance_report():
    """Send final attendance report after admin approvals"""
    try:
        today = datetime.now(IST).date()
        
        # Get all attendance data
        present_faculty = db.session.query(User).join(Attendance).filter(
            Attendance.date == today
        ).distinct().all()
        
        # Get all faculty
        all_faculty = User.query.filter_by(role='faculty').all()
        
        # Get approved absentees
        approved_absentees = db.session.query(AbsenteeApproval, User).join(User).filter(
            AbsenteeApproval.date == today,
            AbsenteeApproval.is_approved == True
        ).all()
        
        # Get denied/unauthorized absentees
        unauthorized_absentees = []
        for faculty in all_faculty:
            if faculty not in present_faculty:
                approval = AbsenteeApproval.query.filter_by(
                    user_id=faculty.id,
                    date=today
                ).filter(
                    (AbsenteeApproval.is_approved == False) | 
                    (AbsenteeApproval.is_approved.is_(None))
                ).first()
                if approval:
                    unauthorized_absentees.append(faculty)
        
        # Create comprehensive report
        subject = f"Final Daily Attendance Report - {today.strftime('%B %d, %Y')}"
        
        html_body = f"""
        <html>
        <head>
            <style>
                .report-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                .report-table th, .report-table td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
                .report-table th {{ background-color: #f2f2f2; font-weight: bold; }}
                .present {{ background-color: #d4edda; }}
                .approved-absent {{ background-color: #fff3cd; }}
                .unauthorized-absent {{ background-color: #f8d7da; }}
                .summary-card {{ background-color: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <h2>📊 Final Daily Attendance Report</h2>
            <p><strong>Date:</strong> {today.strftime('%B %d, %Y')}</p>
            <p><strong>Report Generated:</strong> {datetime.now(IST).strftime('%I:%M %p IST')}</p>
            
            <div class="summary-card">
                <h3>📈 Summary</h3>
                <ul>
                    <li><strong>Total Faculty:</strong> {len(all_faculty)}</li>
                    <li><strong>✅ Present:</strong> {len(present_faculty)}</li>  
                    <li><strong>✔️ Approved Absences:</strong> {len(approved_absentees)}</li>
                    <li><strong>❌ Unauthorized Absences:</strong> {len(unauthorized_absentees)}</li>
                    <li><strong>📊 Effective Attendance Rate:</strong> {((len(present_faculty) + len(approved_absentees)) / len(all_faculty) * 100):.1f}%</li>
                </ul>
            </div>
        """
        
        # Generate Excel and PDF attachments
        excel_file = generate_enhanced_excel_report(present_faculty, approved_absentees, unauthorized_absentees, today)
        pdf_file = generate_enhanced_pdf_report(present_faculty, approved_absentees, unauthorized_absentees, today)
        
        html_body += """
            <p>📎 <strong>Detailed reports are attached as Excel and PDF files.</strong></p>
            
            <p style="color: #666; font-size: 12px;">
                <em>This report includes admin-approved absences and highlights unauthorized absences for further action.</em>
            </p>
        </body>
        </html>
        """
        
        # Send email with attachments
        success = send_email_with_attachments(ADMIN_EMAILS, subject, html_body, [excel_file, pdf_file])
        
        # Log email
        if success:
            log_email(today, ADMIN_EMAILS, subject, 'sent')
            logging.info("Final attendance report sent successfully")
        else:
            log_email(today, ADMIN_EMAILS, subject, 'failed')
            logging.error("Failed to send final attendance report")
        
        return success
        
    except Exception as e:
        logging.error(f"Error sending final attendance report: {e}")
        return False

def send_email(recipients, subject, html_body):
    """Send HTML email"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_EMAIL
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return False

def send_email_with_attachments(recipients, subject, html_body, attachment_files):
    """Send email with file attachments"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        # Add attachments
        for file_path in attachment_files:
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                filename = os.path.basename(file_path)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}',
                )
                msg.attach(part)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
        
    except Exception as e:
        logging.error(f"Error sending email with attachments: {e}")
        return False

def generate_enhanced_excel_report(present_faculty, approved_absentees, unauthorized_absentees, report_date):
    """Generate enhanced Excel report with approval status"""
    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Attendance Report"
        
        # Title
        ws['A1'] = f"Enhanced Daily Attendance Report - {report_date.strftime('%B %d, %Y')}"
        ws['A1'].font = Font(size=16, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.merge_cells('A1:F1')
        
        # Headers
        headers = ['S.No', 'Faculty Name', 'Staff Type', 'Department', 'Status', 'Remarks']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
            cell.alignment = Alignment(horizontal='center')
        
        row = 4
        
        # Present faculty
        for i, faculty in enumerate(present_faculty, 1):
            ws.cell(row=row, column=1, value=i)
            ws.cell(row=row, column=2, value=faculty.full_name or faculty.username)
            ws.cell(row=row, column=3, value=faculty.staff_type.replace('_', ' ').title())
            ws.cell(row=row, column=4, value=faculty.department or 'N/A')
            ws.cell(row=row, column=5, value='Present')
            ws.cell(row=row, column=6, value='Attended')
            
            # Green background for present
            for col in range(1, 7):
                ws.cell(row=row, column=col).fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
            
            row += 1
        
        # Approved absentees
        for approval, faculty in approved_absentees:
            ws.cell(row=row, column=1, value=row-3)
            ws.cell(row=row, column=2, value=faculty.full_name or faculty.username)
            ws.cell(row=row, column=3, value=faculty.staff_type.replace('_', ' ').title())
            ws.cell(row=row, column=4, value=faculty.department or 'N/A')
            ws.cell(row=row, column=5, value='Approved Absence')
            ws.cell(row=row, column=6, value=f'Approved by {approval.approved_by}')
            
            # Yellow background for approved absences
            for col in range(1, 7):
                ws.cell(row=row, column=col).fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
            
            row += 1
        
        # Unauthorized absentees
        for faculty in unauthorized_absentees:
            ws.cell(row=row, column=1, value=row-3)
            ws.cell(row=row, column=2, value=faculty.full_name or faculty.username)
            ws.cell(row=row, column=3, value=faculty.staff_type.replace('_', ' ').title())
            ws.cell(row=row, column=4, value=faculty.department or 'N/A')
            ws.cell(row=row, column=5, value='Unauthorized Absence')
            ws.cell(row=row, column=6, value='Action required')
            
            # Red background for unauthorized absences
            for col in range(1, 7):
                ws.cell(row=row, column=col).fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
            
            row += 1
        
        # Save file
        filename = f"attendance_report_{report_date.strftime('%Y%m%d')}.xlsx"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        wb.save(file_path)
        
        return file_path
        
    except Exception as e:
        logging.error(f"Error generating Excel report: {e}")
        return None

def generate_enhanced_pdf_report(present_faculty, approved_absentees, unauthorized_absentees, report_date):
    """Generate enhanced PDF report"""
    try:
        filename = f"attendance_report_{report_date.strftime('%Y%m%d')}.pdf"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        
        doc = SimpleDocTemplate(file_path, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title = Paragraph(f"Enhanced Daily Attendance Report - {report_date.strftime('%B %d, %Y')}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Summary
        summary_data = [
            ['Total Faculty', str(len(present_faculty) + len(approved_absentees) + len(unauthorized_absentees))],
            ['Present', str(len(present_faculty))],
            ['Approved Absences', str(len(approved_absentees))],
            ['Unauthorized Absences', str(len(unauthorized_absentees))],
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        # Detailed data table
        data = [['S.No', 'Name', 'Staff Type', 'Department', 'Status']]
        
        # Present faculty
        for i, faculty in enumerate(present_faculty, 1):
            data.append([
                str(i),
                faculty.full_name or faculty.username,
                faculty.staff_type.replace('_', ' ').title(),
                faculty.department or 'N/A',
                'Present'
            ])
        
        # Build table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, len(present_faculty)), colors.lightgreen),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        doc.build(story)
        
        return file_path
        
    except Exception as e:
        logging.error(f"Error generating PDF report: {e}")
        return None

def log_email(date, recipients, subject, status):
    """Log email sending attempt"""
    try:
        email_log = EmailLog()
        email_log.date = date
        email_log.recipients = ', '.join(recipients)
        email_log.subject = subject
        email_log.status = status
        
        db.session.add(email_log)
        db.session.commit()
        
    except Exception as e:
        logging.error(f"Error logging email: {e}")