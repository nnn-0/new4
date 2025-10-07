#!/usr/bin/env python3
"""
Smart Attendance System Setup Script
Run this script to set up the application on your local machine.
"""

import os
import subprocess
import sys

def install_requirements():
    """Install required Python packages"""
    packages = [
        'Flask==3.0.0',
        'Flask-SQLAlchemy==3.1.1', 
        'Werkzeug==3.0.1',
        'pytz==2023.3',
        'qrcode==7.4.2',
        'openpyxl==3.1.2',
        'reportlab==4.0.7',
        'gunicorn==21.2.0',
        'schedule==1.2.0',
        'Pillow==10.1.0',
        'email-validator==2.1.0'
    ]
    
    print("Installing required packages...")
    for package in packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ Installed {package}")
        except subprocess.CalledProcessError:
            print(f"✗ Failed to install {package}")
            return False
    return True

def create_env_file():
    """Create environment configuration file"""
    env_content = """# Smart Attendance System Environment Configuration

# Email Settings (Required for sending reports)
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password

# Application Settings
SESSION_SECRET=your_secret_key_here
DATABASE_URL=sqlite:///attendance.db

# Note: Replace the values above with your actual credentials
# For Gmail app password: Enable 2FA, then generate app password
"""
    
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✓ Created .env file - Please edit it with your credentials")
    else:
        print("✓ .env file already exists")

def create_startup_script():
    """Create startup script for easy launching"""
    if os.name == 'nt':  # Windows
        script_content = """@echo off
echo Starting Smart Attendance System...
python main.py
pause
"""
        with open('start.bat', 'w') as f:
            f.write(script_content)
        print("✓ Created start.bat for Windows")
    else:  # Unix/Linux/Mac
        script_content = """#!/bin/bash
echo "Starting Smart Attendance System..."
python3 main.py
"""
        with open('start.sh', 'w') as f:
            f.write(script_content)
        os.chmod('start.sh', 0o755)
        print("✓ Created start.sh for Unix/Linux/Mac")

def main():
    """Main setup function"""
    print("=" * 50)
    print("Smart Attendance System Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("✗ Python 3.8 or higher is required")
        return
    
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install packages
    if not install_requirements():
        print("✗ Package installation failed")
        return
    
    # Create configuration files
    create_env_file()
    create_startup_script()
    
    print("\n" + "=" * 50)
    print("Setup Complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Edit .env file with your email credentials")
    print("2. Run the application:")
    if os.name == 'nt':
        print("   - Windows: Double-click start.bat")
    else:
        print("   - Unix/Linux/Mac: ./start.sh")
    print("   - Or manually: python main.py")
    print("3. Access the system at http://localhost:5000")
    print("4. Login with admin/admin123")
    print("\nFor Gmail setup:")
    print("- Enable 2-Factor Authentication")
    print("- Generate App Password for Mail")
    print("- Use app password in .env file")

if __name__ == "__main__":
    main()