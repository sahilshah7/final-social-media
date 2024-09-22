from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session
from flask_login import login_required, current_user
from .models import ForumPost, Comment, Like, User, Follower, Category, Forum, Notification, Upvote, Downvote, HighFive
from .forms import PostForm, CommentForm, EditAccountForm, DeleteAccountForm, FollowForm, EditProfileForm, HighFiveForm
from . import db, mail  # Import mail from your app
import os  # Import os module
from werkzeug.utils import secure_filename
import logging
from flask_wtf import FlaskForm
import re
from datetime import datetime, time, timedelta
import pytz
from pytz import timezone
from transformers import pipeline
import stat
import requests
from config import ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, ZOOM_OAUTH_TOKEN_URL, ZOOM_API_URL
from base64 import b64encode
import json
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Message
from website import mail  # Import app and mail
from transformers import AutoModelForCausalLM, AutoTokenizer, BlenderbotTokenizer, BlenderbotForConditionalGeneration
import torch
from flask import render_template, request, jsonify, redirect, url_for
from transformers import BlenderbotTokenizer, BlenderbotForConditionalGeneration
from better_profanity import profanity
from PIL import Image, ImageDraw
import uuid

scheduler = BackgroundScheduler()
scheduler.start()

# Blueprint setup
views = Blueprint('views', __name__)
logging.basicConfig(level=logging.DEBUG)
meeting_bp = Blueprint('meeting_bp', __name__)  # Define meeting_bp for meeting-related routes
generator = pipeline('text-generation', model='EleutherAI/gpt-neo-2.7B')
scheduler_bp = Blueprint('scheduler_bp', __name__)

ZOOM_CLIENT_ID = '7vHLopUdQSaZ7BQpPfO5gQ'
ZOOM_CLIENT_SECRET = 'RfWYB1ZMSA7Kk6BXSe8SiZPxqc5I7hWg'
ZOOM_ACCOUNT_ID = 'ZObsKZODREywXjz3MLPixQ'  # Server-to-Server OAuth apps require the account ID
ZOOM_AUTH_URL = "https://zoom.us/oauth/token"
ZOOM_API_URL = "https://api.zoom.us/v2/users/me/meetings"

model_id = "facebook/blenderbot-400M-distill"
tokenizer = BlenderbotTokenizer.from_pretrained(model_id)
model = BlenderbotForConditionalGeneration.from_pretrained(model_id)

# Load profanity filter
profanity.load_censor_words()

DAILY_LIMIT = 60

# Route to manually reset the timer
@views.route('/reset_timer')
@login_required
def reset_timer():
    """Manually reset the user's timer and redirect them back to the home page."""
    
    # Reset session's timer information
    session['start_time'] = datetime.now(pytz.timezone('America/Los_Angeles'))  # Reset start time
    session['time_spent'] = 0  # Reset time spent to zero
    
    # Set a session flag to notify the frontend to reset the visual timer
    session['timer_reset'] = True  # This will be picked up by the frontend script

    flash("Your timer has been reset to 60 minutes.", "success")

    # Redirect to home page
    return redirect(url_for('views.home'))


# Function to check the time limit for a session
def check_time_limit():
    timezone = pytz.timezone('America/Los_Angeles')
    current_time = datetime.now(timezone)

    # Define the reset time as 11:59 PM today
    reset_time = current_time.replace(hour=23, minute=59, second=59, microsecond=0)
    print(f"[DEBUG] Current time: {current_time}, Reset time: {reset_time}")

    # Reset the timer for a new day
    if 'last_visit' not in session or session['last_visit'].date() != current_time.date():
        session['start_time'] = current_time  # Set start time for a new day
        session['time_spent'] = 0  # Reset time spent for the day
        session['last_visit'] = current_time  # Update last visit
        session['timer_reset'] = True  # Notify frontend that the timer was reset

        print(f"[DEBUG] Timer reset for the new day at {current_time}. Session start time: {session['start_time']}")
    else:
        # Calculate time spent in the session
        if 'start_time' in session:
            start_time = session['start_time'].replace(tzinfo=timezone)
        else:
            start_time = current_time

        time_spent_this_session = (current_time - start_time).total_seconds() / 60  # in minutes

        # Ensure that the total time spent does not exceed 60 minutes
        if 'time_spent' in session:
            session['time_spent'] = min(session['time_spent'] + time_spent_this_session, 60)
        else:
            session['time_spent'] = time_spent_this_session

        print(f"[DEBUG] Total time spent today: {session['time_spent']} minutes")

        if session['time_spent'] >= 60:
            print(f"[DEBUG] Time limit exceeded: {session['time_spent']} minutes spent today.")
            return False  # Time limit exceeded

        session['start_time'] = current_time  # Update start time

    session['last_visit'] = current_time  # Update last visit
    remaining_time = 60 - session['time_spent']
    print(f"[DEBUG] Remaining time: {remaining_time} minutes")
    return max(remaining_time, 0)


# Route to get the remaining time
@views.route('/get_remaining_time', methods=['GET'])
@login_required
def get_remaining_time():
    remaining_time = check_time_limit()
    if remaining_time is False:
        remaining_time = 0  # No time left
    return jsonify({"remaining_time": remaining_time})


@views.route('/chat', methods=['GET', 'POST'])
def chat():
    """Handle chat functionality with a 60-minute daily time limit."""

    """Home route to display suggested posts, accounts, and handle Zoom meeting redirection."""

    # Check if the user has exceeded the 60-minute daily time limit
    remaining_time = check_time_limit()

    if remaining_time is False:  # If time limit is exceeded, redirect
        return redirect(url_for('views.access_restricted'))
    
    if request.method == 'POST':
        try:
            user_message = request.json.get('message').strip().lower()
            if not user_message:
                return jsonify({'error': 'No message provided'}), 400

            # Tokenize the input message
            inputs = tokenizer(user_message, return_tensors="pt")

            # Generate response using BlenderBot
            reply_ids = model.generate(**inputs)
            response_text = tokenizer.decode(reply_ids[0], skip_special_tokens=True)

            # Filter inappropriate content using better_profanity
            filtered_response = profanity.censor(response_text)

            return jsonify({'response': filtered_response})
        except Exception as e:
            print(f"Error: {e}")
            return jsonify({'error': f'Failed to generate a response: {str(e)}'}), 500

    return render_template('chat.html', remaining_time=remaining_time)

def send_zoom_reminder(app, zoom_meeting_url, meeting_time):
    print("Sending reminder emails...")  # Check if this prints out
    with app.app_context():
        users = User.query.all()
        for user in users:
            if user.email:
                try:
                    msg = Message(subject="Zoom Meeting Reminder",
                                  sender=current_app.config['MAIL_USERNAME'],
                                  recipients=[user.email])
                    msg.body = f'''Hello {user.first_name},

This is a reminder for the upcoming Zoom meeting.

Meeting Time: {meeting_time} (PST)
Zoom Meeting Link: {zoom_meeting_url}

We hope to see you there!

Best regards,
Your Website Team
'''
                    mail.send(msg)
                    print(f"Reminder email sent successfully to {user.email}")
                except Exception as e:
                    print(f"Failed to send email to {user.email}: {str(e)}")

# Function to schedule Zoom reminder 45 minutes before the meeting
def send_zoom_reminder(app, zoom_meeting_url, meeting_time):
    print("Sending reminder emails...")  # Check if this prints out
    with app.app_context():
        users = User.query.all()
        for user in users:
            if user.email:
                try:
                    msg = Message(subject="Zoom Meeting Reminder",
                                  sender=current_app.config['MAIL_USERNAME'],
                                  recipients=[user.email])
                    msg.body = f'''Hello {user.first_name},

This is a reminder for the upcoming Zoom meeting.

Meeting Time: {meeting_time} (PST)
Zoom Meeting Link: {zoom_meeting_url}

We hope to see you there!

Best regards,
SpotLight
'''
                    mail.send(msg)
                    print(f"Reminder email sent successfully to {user.email}")
                except Exception as e:
                    print(f"Failed to send email to {user.email}: {str(e)}")

@views.route('/test_email')
def test_email():
    try:
        send_zoom_reminder(current_app, "https://zoom.us/test", "19:00:00")
        return "Test email sent successfully!"
    except Exception as e:
        return f"Error sending test email: {str(e)}"
    
# Function to get Zoom access token
def get_access_token():
    url = ZOOM_AUTH_URL
    auth_header = b64encode(f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}".encode()).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }
    
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Failed to get access token: {response.text}")

# Function to schedule a Zoom meeting
def schedule_zoom_meeting(access_token, topic, start_time, duration_minutes):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    meeting_data = {
        "topic": topic,
        "type": 2,  
        "start_time": start_time,
        "duration": duration_minutes,
        "timezone": "UTC",
        "settings": {
            "join_before_host": True,
            "auto_recording": "cloud"
        }
    }

    response = requests.post(ZOOM_API_URL, headers=headers, json=meeting_data)

    if response.status_code == 201:
        print(f"Meeting scheduled successfully: {response.json().get('join_url')}")
        return response.json().get('join_url')  
    else:
        print(f"Error scheduling meeting: {response.text}")
        return None

# Check if the current time is within the Zoom meeting window
def is_within_zoom_window():
    pst = pytz.timezone('America/Los_Angeles')
    now = datetime.now(pst).time()
    start_time = time(21, 0)  # 7:00 PM PST
    end_time = time(21, 40)   # 7:40 PM PST
    return start_time <= now <= end_time

# Function to schedule a weekly meeting reminder at 6:15 PM PST
def schedule_weekly_meetings(app):
    scheduler = BackgroundScheduler()
    
    # Set the time of the meeting (7:00 PM PST every Wednesday)
    meeting_time = "19:00:00"  # 7:00 PM
    zoom_meeting_url = "https://us05web.zoom.us/j/84949756210?pwd=tzy7NsHU16v7YRMORGkMLTAUzdxlLg.1#success"
    
    # Schedule the reminder 45 minutes before the weekly meeting
    scheduler.add_job(
        func=lambda: send_zoom_reminder(app, zoom_meeting_url, meeting_time),
        trigger='cron',
        day_of_week='wed',  # Every Wednesday
        hour=18,  # 6:15 PM PST (45 minutes before the meeting)
        minute=32,
        timezone=pytz.timezone('America/Los_Angeles')  # PST timezone
    )
    
    scheduler.start()
    print("Weekly meeting reminders scheduled.")

@views.route('/')
def home():
    """Home route to display suggested posts, accounts, and handle Zoom meeting redirection."""

    # Check if the user has exceeded the 60-minute daily time limit
    remaining_time = check_time_limit()  # Returns remaining time in minutes or None

    # Redirect if the time limit is exceeded
    if remaining_time is None:
        return redirect(url_for('views.access_restricted'))  # Redirect to restricted page

    # Pagination setup: Get page number from query string, default to 1 if not present
    page = request.args.get('page', 1, type=int)
    per_page = 8  # Number of suggested posts to display per page

    # Fetch suggested posts and accounts with error handling
    try:
        # Fetch the suggested posts with pagination
        suggested_posts = ForumPost.query.order_by(ForumPost.date_created.desc()).paginate(page=page, per_page=per_page)

        # Fetch suggested accounts, limit to the 5 most recently logged in users
        suggested_accounts = User.query.order_by(User.last_login.desc()).limit(5).all()

        # Logging fetched data for debugging
        logging.info(f"Page {page}: Fetched {len(suggested_posts.items)} suggested posts.")
        logging.info(f"Fetched {len(suggested_accounts)} suggested accounts.")

    except Exception as e:
        # Log the error and set fallback values
        logging.error(f"Error fetching suggested posts or accounts: {str(e)}")
        suggested_posts = None
        suggested_accounts = []  # Use an empty list if fetching accounts fails

    # Check if within the Zoom meeting window and redirect if meeting is active
    if is_within_zoom_window():
        flash("Meeting is live, redirecting to Zoom...", "info")
        try:
            access_token = get_access_token()
            zoom_meeting_url = schedule_zoom_meeting(
                access_token, 
                topic="Scheduled Meeting", 
                start_time="2024-09-05T16:00:00Z", 
                duration=40
            )
            if zoom_meeting_url:
                return redirect(zoom_meeting_url)
            else:
                flash("Error scheduling the Zoom meeting. Please check the logs for details.", "danger")
        except Exception as e:
            flash(f"Zoom scheduling error: {str(e)}", "danger")
            logging.error(f"Exception during Zoom meeting scheduling: {str(e)}")

    # Render the home page, passing the suggested posts and accounts to the template
    return render_template(
        'home.html', 
        suggested_posts=suggested_posts,  # Pass the Pagination object to the template
        suggested_accounts=suggested_accounts, 
        remaining_time=remaining_time  # Pass the list of suggested accounts
    )

# Meeting room route
@meeting_bp.route('/meeting_room')
def meeting_room():
    return render_template('meeting_room.html')

def extract_mentions(content):
    """Extracts mentioned usernames from the content and returns the corresponding User objects."""
    mentions = re.findall(r'@(\w+)', content)
    users = User.query.filter(User.username.in_(mentions)).all()
    return users

@views.route('/test-time')
def test_time():
    """Test route to display current time and access status."""
    access_allowed = is_within_online_window()
    now = datetime.now(pytz.timezone('America/Los_Angeles')).time()
    return f"Current time: {now}, Access allowed: {access_allowed}"

def is_within_online_window():
    """Check if the current time is within the allowed online window."""
    # Define timezone
    pst = pytz.timezone('America/Los_Angeles')
    
    # Get current time in the specified timezone
    now = datetime.now(pst).time()
    print(f"Current time: {now}")  # Debugging statement
    
    # Define start and end time for the online window
    start_time = time(10, 0)  # 10 AM
    end_time = time(23, 0)    # 8 PM (24-hour format)
    
    # Debugging statements
    print(f"Start time: {start_time}")
    print(f"End time: {end_time}")

    # Check if the current time is within the allowed time window
    is_within_window = start_time <= now <= end_time
    print(f"Is within window: {is_within_window}")  # Debugging statement
    return is_within_window

@views.route('/access-restricted')
def access_restricted():
    """Render the access restricted page."""
    return render_template('access_restricted.html')

@views.route('/restricted-page')
def restricted_page():
    """Render a restricted page if within the allowed time window."""
    access_allowed = is_within_online_window()
    if not access_allowed:
        return render_template('access_restricted.html')
    return render_template('restricted_page.html')

@views.route('/outside-online-window')
def outside_online_window():
    """Render a page when access is outside the allowed time window."""
    return render_template('outside_online_window.html')

@views.route('/share_post/<int:post_id>', methods=['POST'])
@login_required
def share_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    # Implement your share logic here

    create_notification(
        notification_type='share_post',
        recipient=post.author,
        sender=current_user,
        message=f'{current_user.username} shared your post.',
        post=post
    )

    flash('Post shared!', 'success')
    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/save_post/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if current_user in post.savers:
        current_user.saved_posts.remove(post)
        flash('Post unsaved.', 'info')
    else:
        current_user.saved_posts.append(post)
        create_notification(
            notification_type='save_post',
            recipient=post.author,
            sender=current_user,
            message=f'{current_user.username} saved your post.',
            post=post
        )
        flash('Post saved!', 'success')
    db.session.commit()
    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/forum_post/<int:id>', methods=['GET', 'POST'])
def forum_post(id):
    
    post = ForumPost.query.get_or_404(id)
    form = CommentForm()
    highfive_form = HighFiveForm()  # Form for giving high fives

    if form.validate_on_submit():
        comment = Comment(content=form.comment.data, user_id=current_user.id, forum_post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('views.forum_post', id=post.id))

    comments = Comment.query.filter_by(forum_post_id=post.id).all()
    highfives = HighFive.query.filter_by(post_id=post.id).count()  # Count of high fives
    return render_template('forum_post.html', post=post, form=form, comments=comments, highfive_form=highfive_form, highfives=highfives)

def populate_categories():
    if Category.query.count() == 0:
        categories = [Category(name='Technology'), Category(name='Science'), Category(name='Sports')]
        db.session.add_all(categories)
        db.session.commit()

@views.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    user = User.query.get_or_404(user_id)

    # Prevent users from following themselves
    if current_user == user:
        flash('You cannot follow yourself!', 'danger')
        return redirect(url_for('views.public_account', user_id=user_id))

    follow_record = Follower.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()

    if follow_record:
        db.session.delete(follow_record)
        db.session.commit()
        flash(f'You have unfollowed {user.first_name}.', 'success')
    else:
        new_follow = Follower(follower_id=current_user.id, followed_id=user.id)
        db.session.add(new_follow)
        db.session.commit()
        flash(f'You are now following {user.first_name}.', 'success')

        # Create a notification for the followed user
        create_notification(
            notification_type='follow',
            recipient=user,
            sender=current_user,
            message=f'{current_user.username} started following you.'
        )

    return redirect(url_for('views.public_account', user_id=user_id))

@views.route('/populate')
def populate():
    populate_categories()
    return "Categories populated!"

@views.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = ForumPost.query.get_or_404(post_id)
    comments = Comment.query.filter_by(forum_post_id=post_id).order_by(Comment.date_created.asc()).all()
    highfive_form = HighFiveForm()  # Form for giving high fives

    if request.method == 'POST':
        if 'content' in request.form:
            content = request.form.get('content')
            if not content:
                flash('Comment cannot be empty', 'danger')
            else:
                if current_user.is_authenticated:
                    new_comment = Comment(content=content, user_id=current_user.id, forum_post_id=post.id)
                    db.session.add(new_comment)
                    db.session.commit()

                    mentioned_users = extract_mentions(content)
                    for user in mentioned_users:
                        create_notification('mention', user, current_user, f'{current_user.username} mentioned you in a comment.', post)

                    followers = current_user.followers
                    for follower in followers:
                        create_notification('comment', follower.follower_user, current_user, f'{current_user.username} commented on a post.', post)

                    flash('Comment added successfully!', 'success')
                else:
                    flash('You must be logged in to comment.', 'danger')
                return redirect(url_for('views.post_detail', post_id=post.id))

        elif highfive_form.validate_on_submit():
            if current_user.is_authenticated:
                existing_highfive = HighFive.query.filter_by(user_id=current_user.id, post_id=post.id).first()
                if existing_highfive:
                    flash('You already gave a high five to this post.', 'info')
                else:
                    new_highfive = HighFive(user_id=current_user.id, post_id=post.id)
                    db.session.add(new_highfive)
                    db.session.commit()
                    flash('High five given successfully!', 'success')
            else:
                flash('You must be logged in to give a high five.', 'danger')
            return redirect(url_for('views.post_detail', post_id=post.id))

    highfives = HighFive.query.filter_by(post_id=post.id).count()  # Count of high fives
    return render_template('post_detail.html', post=post, comments=comments, highfive_form=highfive_form, highfives=highfives)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@views.route('/create_post/<int:forum_id>', methods=['GET', 'POST'])
@login_required
def create_post(forum_id):
    form = PostForm()
    forum = Forum.query.get_or_404(forum_id)

    if form.validate_on_submit():
        image_filename = None
        if form.image.data:
            image = form.image.data

            # Debug: Check the filename and extension
            print(f"Uploaded image filename: {image.filename}")
            if image.filename == '':
                flash('No image selected', 'danger')
                return redirect(request.url)

            if allowed_file(image.filename):
                image_filename = secure_filename(image.filename)
                image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)

                # Ensure the directory exists
                if not os.path.exists(current_app.config['UPLOAD_FOLDER']):
                    try:
                        os.makedirs(current_app.config['UPLOAD_FOLDER'], mode=0o755)
                    except OSError as e:
                        flash(f'Error creating upload directory: {e}', 'danger')
                        return redirect(url_for('views.create_post', forum_id=forum_id))

                try:
                    # Use os.path.isfile to ensure it's a file and not a folder
                    assert not os.path.isdir(image_path), f"Path '{image_path}' is a directory, not a file."
                    print(f"Saving image to: {image_path}")
                    
                    # Save the image file
                    image.save(image_path)
                except AssertionError as e:
                    flash(f"Invalid file path: {e}", 'danger')
                    return redirect(url_for('views.create_post', forum_id=forum_id))
                except PermissionError as e:
                    flash(f'Permission error: {e}', 'danger')
                    return redirect(url_for('views.create_post', forum_id=forum_id))
                except Exception as e:
                    flash(f'Error saving image: {e}', 'danger')
                    return redirect(url_for('views.create_post', forum_id=forum_id))
            else:
                flash('Invalid file type. Please upload a png, jpg, jpeg, or gif image.', 'danger')
                return redirect(url_for('views.create_post', forum_id=forum_id))

        # Create a new forum post with form data
        new_post = ForumPost(
            title=form.title.data or "Untitled",  # Default title value
            content=form.content.data or "",      # Default content value
            forum_id=forum_id,
            user_id=current_user.id,
            image=image_filename
        )
        db.session.add(new_post)
        db.session.commit()

        flash('Your post has been created!', 'success')
        return redirect(url_for('views.forum_detail', forum_id=forum_id))

    return render_template('create_post.html', form=form, forum=forum)

@views.route('/forums/<int:forum_id>')
@login_required
def forums(forum_id):
    # Existing access check
    access_allowed = is_within_online_window()
    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    # Fetch user notifications
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()

    # Fetch the forum by ID
    forum = Forum.query.get_or_404(forum_id)

    # Fetch forum posts with pagination (optional)
    page = request.args.get('page', 1, type=int)
    forum_posts = ForumPost.query.filter_by(forum_id=forum_id).order_by(ForumPost.date_created.desc()).paginate(page=page, per_page=10)

    return render_template('forum_detail.html', 
                           notifications=user_notifications, 
                           forum=forum, 
                           forum_posts=forum_posts)

@views.route('/forum/<int:forum_id>', methods=['GET'])
@login_required  # Ensure only logged-in users can access the forum
def forum_detail(forum_id):

    # Check if the user has exceeded the 60-minute daily time limit
    remaining_time = check_time_limit()

    if remaining_time is False:  # If time limit is exceeded, redirect
        return redirect(url_for('views.access_restricted'))
    
    # Get the page number from the query string, default to 1
    page = request.args.get('page', 1, type=int)

    # Fetch forum details and posts for the given forum ID
    forum = Forum.query.get_or_404(forum_id)
    forum_posts = ForumPost.query.filter_by(forum_id=forum_id).order_by(ForumPost.date_created.desc()).paginate(page=page, per_page=5)

    # Fetch notifications for the logged-in user
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()

    # Render the forum detail template with posts and notifications
    return render_template('forum_detail.html', forum=forum, forum_posts=forum_posts, notifications=notifications, remaining_time=remaining_time)

@views.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    comment_content = request.form.get('content')

    if not comment_content:
        flash('Comment cannot be empty', 'danger')
        return redirect(url_for('views.post_detail', post_id=post_id))

    new_comment = Comment(content=comment_content, user_id=current_user.id, forum_post_id=post.id)
    db.session.add(new_comment)
    db.session.commit()

    mentions = extract_mentions(comment_content)
    for user in mentions:
        create_notification('mention', user, current_user, f'{current_user.username} mentioned you in a comment.', post)

    flash('Comment added successfully!', 'success')
    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = ForumPost.query.get_or_404(post_id)

    # Check if the current user is the owner of the post
    if post.user_id != current_user.id:
        flash('You do not have permission to delete this post', 'danger')
        return redirect(url_for('views.post_detail', post_id=post_id))
    
    try:
        # Delete the post and commit the change
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully', 'success')
        # Redirect to the forum the post was in
        return redirect(url_for('views.forum_detail', forum_id=post.forum_id))
    
    except Exception as e:
        # Handle any errors that might occur during the deletion process
        db.session.rollback()
        flash(f'Error deleting post: {str(e)}', 'danger')
        return redirect(url_for('views.post_detail', post_id=post_id))
     
@views.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    """Render the account page with a 60-minute daily time limit."""

    # Check if the user has exceeded the 60-minute daily time limit
    remaining_time = check_time_limit()

    if remaining_time is False:  # Redirect if the time limit is exceeded
        return redirect(url_for('views.access_restricted'))
    
    edit_form = EditAccountForm()
    delete_form = DeleteAccountForm()

    # Handle account update
    if edit_form.validate_on_submit():
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':  # Ensure a file is selected
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['IMAGE_FOLDER'], filename)

                try:
                    file.save(file_path)
                    current_user.profile_picture = filename
                except Exception as e:
                    flash('Error uploading profile picture.', 'danger')
                    logging.error(f"Error saving profile picture: {e}")
        
        # Update account details
        current_user.name = edit_form.name.data
        current_user.bio = edit_form.bio.data
        current_user.website = edit_form.website.data
        current_user.gender = edit_form.gender.data
        db.session.commit()
        flash('Account updated successfully!', 'success')
        return redirect(url_for('views.account'))

    # Handle account deletion
    if delete_form.validate_on_submit():
        db.session.delete(current_user)
        db.session.commit()
        flash('Account deleted successfully', 'success')
        return redirect(url_for('auth.login'))

    # Fetch followers and following
    followers_list = current_user.followers.all()
    following_list = current_user.following.all()
    followers_count = len(followers_list)
    following_count = len(following_list)

    if request.method == 'GET':
        edit_form.name.data = current_user.name
        edit_form.bio.data = current_user.bio
        edit_form.website.data = current_user.website
        edit_form.gender.data = current_user.gender

    return render_template(
        'account.html',
        edit_form=edit_form,
        delete_form=delete_form,
        followers_list=followers_list,
        following_list=following_list,
        followers_count=followers_count,
        following_count=following_count,
        remaining_time=remaining_time  # Pass remaining time to template
    )

@views.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)

    if comment.user_id == current_user.id:
        db.session.delete(comment)
        db.session.commit()
        flash('Comment deleted successfully', 'success')
        return redirect(url_for('views.post_detail', post_id=comment.forum_post_id))
    else:
        flash('You do not have permission to delete this comment', 'danger')
        return redirect(url_for('views.post_detail', post_id=comment.forum_post_id))
    
@views.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    db.session.delete(user)
    db.session.commit()
    flash('Account deleted successfully', 'success')
    return redirect(url_for('auth.login'))

@views.route('/edit_profile/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_profile(user_id):
    # Ensure only sahilshah07@gmail.com can edit profiles
    if current_user.email != 'sahilshah07@gmail.com':
        flash('You are not authorized to edit this profile.', 'danger')
        return redirect(url_for('views.account'))

    # Query the user whose profile is being edited
    user_to_edit = User.query.get_or_404(user_id)

    # Initialize form
    edit_form = EditAccountForm()

    if edit_form.validate_on_submit():
        try:
            # Debug: Confirm form submission
            print("Form submitted successfully.")
            print(f"Updating profile for user: {user_to_edit.first_name}")

            # Update the user with the form data
            user_to_edit.first_name = edit_form.first_name.data
            user_to_edit.name = edit_form.name.data
            user_to_edit.email = edit_form.email.data
            user_to_edit.bio = edit_form.bio.data
            user_to_edit.gender = edit_form.gender.data
            user_to_edit.website = edit_form.website.data
            user_to_edit.birthday = edit_form.birthday.data

            # Handle profile picture upload if selected
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename != '':
                    # Generate a unique filename using uuid to avoid overwriting
                    unique_filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
                    file_path = os.path.join(current_app.config['IMAGE_FOLDER'], unique_filename)

                    # Save the file
                    file.save(file_path)

                    # Update the user's profile picture
                    user_to_edit.profile_picture = unique_filename

                    # Debug: Confirm file saved
                    print(f"Profile picture saved as {unique_filename}")

            # Commit changes to the database
            db.session.commit()
            flash('The profile has been updated successfully!', 'success')
            return redirect(url_for('views.public_account', user_id=user_to_edit.id))

        except Exception as e:
            # Log and show any error that occurred
            print(f"Error while updating profile: {e}")
            flash('An error occurred while saving your profile. Please try again.', 'danger')

    # Pre-fill form with user data on GET request
    if request.method == 'GET':
        edit_form.first_name.data = user_to_edit.first_name
        edit_form.name.data = user_to_edit.name
        edit_form.email.data = user_to_edit.email
        edit_form.bio.data = user_to_edit.bio
        edit_form.gender.data = user_to_edit.gender
        edit_form.website.data = user_to_edit.website
        edit_form.birthday.data = user_to_edit.birthday

    return render_template('edit_profile.html', edit_form=edit_form, user=user_to_edit)

def create_notification(notification_type, recipient, sender, message, post=None):
    # Create a new notification instance
    notification = Notification(
        notification_type=notification_type,
        user_id=recipient.id,  # The recipient (user who receives the notification)
        from_user_id=sender.id,  # The sender (user who triggered the notification)
        message=message,  # The notification message
        post_id=post.id if post else None  # Optionally attach a post to the notification
    )

    try:
        # Add the notification to the database session
        db.session.add(notification)
        # Commit the transaction to save the notification
        db.session.commit()
    except Exception as e:
        # Log the error and handle potential issues (e.g., rollback the session)
        current_app.logger.error(f"Error creating notification: {e}")
        db.session.rollback()
        raise e  # Optionally, re-raise the error for further handling

@views.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()

    if like:
        db.session.delete(like)
        post.likes -= 1
    else:
        new_like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(new_like)
        post.likes += 1

        if current_user.id != post.user_id:
            create_notification(
                notification_type='like',
                to_user=post.author,
                from_user=current_user,
                message=f'{current_user.first_name} liked your post.',
                post=post
            )

    db.session.commit()
    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/upvote/<int:post_id>', methods=['POST'])
@login_required
def upvote(post_id):
    post = ForumPost.query.get_or_404(post_id)
    existing_upvote = Upvote.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    existing_downvote = Downvote.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if existing_upvote:
        db.session.delete(existing_upvote)
    else:
        if existing_downvote:
            db.session.delete(existing_downvote)
        new_upvote = Upvote(user_id=current_user.id, post_id=post_id)
        db.session.add(new_upvote)

    db.session.commit()
    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/downvote/<int:post_id>', methods=['POST'])
@login_required
def downvote(post_id):
    post = ForumPost.query.get_or_404(post_id)
    existing_downvote = Downvote.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    existing_upvote = Upvote.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if existing_downvote:
        db.session.delete(existing_downvote)
    else:
        if existing_upvote:
            db.session.delete(existing_upvote)
        new_downvote = Downvote(user_id=current_user.id, post_id=post_id)
        db.session.add(new_downvote)

    db.session.commit()
    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/notifications')
@login_required
def notifications():
    # Check if access is allowed based on the time window
    access_allowed = is_within_online_window()

    # Debug statement for checking access status
    current_app.logger.debug(f"Access allowed: {access_allowed}")

    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    # Get the page number from the query string
    page = request.args.get('page', 1, type=int)

    # Paginate the notifications (5 notifications per page)
    user_notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.timestamp.desc())\
        .paginate(page=page, per_page=5)

    return render_template('forum_detail.html', notifications=user_notifications)

@views.route('/notifications/mark-as-read/<int:notification_id>')
@login_required
def mark_as_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.user_id != current_user.id:
        flash('You are not authorized to access this notification', 'danger')
        return redirect(url_for('views.notifications'))

    notification.is_read = True
    db.session.commit()
    return redirect(url_for('views.notifications'))

@views.route('/account/<int:user_id>', methods=['GET', 'POST'])
def public_account(user_id):
    user = User.query.get_or_404(user_id)
    form = FollowForm()

    if current_user.is_authenticated:
        if form.validate_on_submit():
            if form.follow.data:
                if user not in current_user.following:
                    follow = Follower(follower_id=current_user.id, followed_id=user.id)
                    db.session.add(follow)
                    db.session.commit()
                    flash(f'You are now following {user.first_name}', 'success')
            elif form.unfollow.data:
                if user in current_user.following:
                    follow = Follower.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()
                    if follow:
                        db.session.delete(follow)
                        db.session.commit()
                        flash(f'You have unfollowed {user.first_name}', 'info')

    followers_list = Follower.query.filter_by(followed_id=user.id).all()
    following_list = Follower.query.filter_by(follower_id=user.id).all()

    return render_template('public_account.html', user=user, form=form, followers=followers_list, following=following_list)

@views.route('/give_highfive/<int:post_id>', methods=['POST'])
@login_required
def give_highfive(post_id):
    post = ForumPost.query.get_or_404(post_id)

    # Check if the user has already given a high five to this post
    if HighFive.query.filter_by(user_id=current_user.id, post_id=post_id).first():
        flash('You have already given a high five to this post.', 'info')
    else:
        # Create and add a new HighFive entry to the database
        highfive = HighFive(user_id=current_user.id, post_id=post_id)
        db.session.add(highfive)
        db.session.commit()
        
        # Create a notification for the post author (use post.author or the correct field for the user)
        create_notification(
            notification_type='highfive_post',
            recipient=post.author,  # This should be the correct field for the post author
            sender=current_user,
            message=f'{current_user.username} gave your post a high five!',
            post=post
        )

        flash('You gave a high five!', 'success')

    return redirect(url_for('views.post_detail', post_id=post_id))

@views.route('/test_db')
def test_db():
    try:
        new_user = User(
            username="testuser", 
            first_name="Test", 
            name="Test Name",
            last_name="User", 
            email="testuser@example.com", 
            password="testpass"
        )
        db.session.add(new_user)
        db.session.commit()
        return "Database connection is working. User added successfully!"
    except Exception as e:
        return f"An error occurred: {e}"