from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail, Message
from flask_migrate import Migrate
from os import path, makedirs
from sqlalchemy import MetaData
import os
from dotenv import load_dotenv
import logging
import pytz
from datetime import datetime, time

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Naming conventions for consistent schema generation
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Set metadata with naming conventions
metadata = MetaData(naming_convention=convention)

# Initialize extensions
db = SQLAlchemy(metadata=metadata)
csrf = CSRFProtect()
mail = Mail()  # Initialize Flask-Mail instance once
migrate = Migrate()
login_manager = LoginManager()

def create_app():
    # Initialize Flask app
    app = Flask(__name__)

    # Set app instance path to ensure the database folder is created inside the instance folder
    app.instance_path = path.join(path.abspath(os.getcwd()), 'instance')
    os.makedirs(app.instance_path, exist_ok=True)

    # Configurations
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path.join(app.instance_path, "database.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_default_secret_key')
    app.config['SECURITY_PASSWORD_SALT'] = os.getenv('SECURITY_PASSWORD_SALT', 'your_secret_salt')
    app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF protection
    
    # Configure UPLOAD_FOLDER for profile picture uploads
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'profile_pics')

    # Ensure the upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            logging.info('Upload folder created successfully.')
        except OSError as e:
            logging.error(f"Error creating upload folder: {e}")

    # Configure Flask-Mail for Gmail
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

    # Ensure all required environment variables are loaded
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        logging.error("Mail username or password is not set. Please check your .env file.")
        raise RuntimeError("Missing mail configuration")

    # Set app to debug mode if environment is development
    if os.getenv('FLASK_ENV') == 'development':
        app.debug = True
        logging.info("Running in development mode")

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    # Set login view for Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Import models to avoid circular imports
    from .models import User, ForumPost, Comment, Like, Follower, Notification

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/auth')

    return app

# Create the Flask app instance
app = create_app()

def initialize_database():
    """Ensure all tables are created and populate categories."""
    with app.app_context():
        db.create_all()  # Ensure all tables are created in the database
        from .views import populate_categories
        populate_categories()  # Populate categories if they do not exist

if __name__ == "__main__":
    initialize_database()  # Ensure database and categories are initialized
    from .views import schedule_weekly_meetings
    schedule_weekly_meetings(app)  # Schedule weekly meetings with app instance
    # Run the Flask app on port 5001 to avoid conflicts
    app.run(debug=True, port=5001)  # Use a different port