from website import create_app, db
from website.views import populate_categories

# Create the Flask app instance
app = create_app()

# Populate database and run the Flask app
if __name__ == "__main__":
    # Use the application context to access the database and perform necessary operations
    with app.app_context():
        db.create_all()  # Ensure all tables are created in the database
        populate_categories()  # Populate categories if they do not exist

    # Run the app in debug mode for development
    app.run(debug=True)
