from website import create_app, db
from website.views import populate_categories, schedule_weekly_meetings
from apscheduler.schedulers.background import BackgroundScheduler

app = create_app()

def initialize_database():
    with app.app_context():
        db.create_all()
        populate_categories()

if __name__ == "__main__":
    initialize_database()
    
    # Start the scheduler
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    # Schedule the weekly meetings
    with app.app_context():
        schedule_weekly_meetings(app)
    
    app.run(debug=True, port=5001)