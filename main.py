from flask import Flask
from website import create_app, db
from website.views import populate_categories
from datetime import datetime, time
import pytz

# Create the Flask app instance
app = create_app()

def initialize_database():
    """Ensure all tables are created and populate categories."""
    with app.app_context():
        db.create_all()  # Ensure all tables are created in the database
        populate_categories()  # Populate categories if they do not exist

if __name__ == "__main__":
    initialize_database()
    # Run the app
    app.run(debug=True)