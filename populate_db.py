from website import create_app, db
from website.models import Category, Forum

app = create_app()

with app.app_context():
    # Drop all tables and recreate them
    db.drop_all()
    db.create_all()

    # Create sample categories
    health_category = Category(name='Health')
    education_category = Category(name='Education')

    db.session.add(health_category)
    db.session.add(education_category)

    # Create sample forums
    forum1 = Forum(title='Managing Intellectual Disabilities', description='How to manage intellectual disabilities.', category=health_category)
    forum2 = Forum(title='Educational Resources', description='Resources for intellectual disabilities.', category=education_category)

    db.session.add(forum1)
    db.session.add(forum2)

    # Commit the changes to the database
    db.session.commit()

    print("Sample categories and forums added.")
