import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Zoom API credentials
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_OAUTH_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_API_URL = "https://api.zoom.us/v2/users/me/meetings"

# Flask app configurations
SECRET_KEY = os.getenv('SECRET_KEY', 'generated_secret_key')
SECURITY_PASSWORD_SALT = os.getenv('SECURITY_PASSWORD_SALT', 'generated_password_salt')

# Mail configurations (if using Flask-Mail)
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')