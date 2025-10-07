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
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    raise ValueError("SESSION_SECRET environment variable must be set for production use")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# Configure the PostgreSQL database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
    "pool_size": 20,  # Optimized for 4000+ users
    "max_overflow": 50,  # Additional connections during peak
    "pool_timeout": 30,  # Connection timeout
    "pool_reset_on_return": "commit",  # Reset connections properly
}

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    import models
    db.create_all()
    
    # Import models to ensure tables are created - admin must be created manually in production
    from models import User
    
    # Check if any admin exists - log warning if none found
    admin_count = User.query.filter_by(role='admin').count()
    if admin_count == 0:
        logging.warning("No admin users found - create admin account through secure onboarding process")

# Import routes
from routes import *

# Start email scheduler
try:
    import scheduler
    logging.info("Email scheduler imported and started")
except Exception as e:
    logging.error(f"Failed to start email scheduler: {e}")
