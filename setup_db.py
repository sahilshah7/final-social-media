# setup_db.py
from website import create_app, db  # Replace 'your_flask_app' with the actual name of your Flask app module
from website.models import User, Notification, Category, Forum, ForumPost, Upvote, Downvote, Comment, Like, Follower  # Import all your models

app = create_app()

with app.app_context():
    # Create all tables
    db.create_all()

    # Optional: Add initial data if needed
    if User.query.count() == 0:
        # Example: Create an initial admin user
        admin_user = User(
            username="admin",
            first_name="Admin",
            last_name="User",
            email="admin@example.com",
            password="adminpassword",  # Normally you should hash the password
            bio="Admin user",
            gender="Other"
        )
        db.session.add(admin_user)
        db.session.commit()

    print("Database setup complete.")