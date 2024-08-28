from website import create_app, db
from website.models import Category, Forum

app = create_app()

with app.app_context():
    try:
        # Check if categories already exist
        if Category.query.count() == 0:
            # Create some categories
            health_category = Category(name='Health')
            education_category = Category(name='Education')

            db.session.add(health_category)
            db.session.add(education_category)

            # Create some forums within those categories
            forum1 = Forum(title='Managing Intellectual Disabilities', description='How to manage intellectual disabilities.', category=health_category)
            forum2 = Forum(title='Educational Resources', description='Resources for intellectual disabilities.', category=education_category)

            db.session.add(forum1)
            db.session.add(forum2)

            # Commit the changes
            db.session.commit()

            print("Database populated with sample data.")
        else:
            print("Categories already exist. No need to populate data.")
    except Exception as e:
        db.session.rollback()  # Rollback the transaction in case of error
        print(f"An error occurred: {e}")
