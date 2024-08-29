from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_migrate import Migrate
from os import path, makedirs
from sqlalchemy import MetaData
import os
from dotenv import load_dotenv

# Naming conventions for constraints to ensure consistent schema generation
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
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()

# Load environment variables from .env file
load_dotenv()

def create_app():
    # Initialize Flask app
    app = Flask(__name__)

    # Configurations
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path.join(app.instance_path, "database.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Turn off SQLAlchemy modification tracking
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or 'your_default_secret_key'
    app.config['WTF_CSRF_ENABLED'] = True  # Enable CSRF protection

    # Ensure the instance folder exists for SQLite database and other data
    try:
        makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    # Set login view for Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    # Import models here to avoid circular imports
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

    # Initialize the database (create tables if they don't exist)
    with app.app_context():
        db.create_all()  # Creates the database tables

    return app