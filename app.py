import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration for Render
database_url = os.environ.get("DATABASE_URL")

# If DATABASE_URL starts with postgres://, change to postgresql://
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///attendance.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models
    db.create_all()
    
    from models import User
    admin_count = User.query.filter_by(role='admin').count()
    if admin_count == 0:
        logging.warning("No admin users found - create admin account through secure onboarding process")

# Import routes
from routes import *

# COMMENT OUT SCHEDULER - It won't work on Render free tier
# try:
#     import scheduler
#     logging.info("Email scheduler imported and started")
# except Exception as e:
#     logging.error(f"Failed to start email scheduler: {e}")

# ADD THIS AT THE END OF app.py (instead of having main.py)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
