from website import create_app, db
from website.models import Category

app = create_app()

with app.app_context():
    categories = Category.query.all()
    print(categories)
