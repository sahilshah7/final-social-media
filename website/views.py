from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
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

from flask import render_template, request, jsonify, redirect, url_for
from transformers import BlenderbotTokenizer, BlenderbotForConditionalGeneration
from better_profanity import profanity

# Load the BlenderBot model and tokenizer
model_id = "facebook/blenderbot-400M-distill"
tokenizer = BlenderbotTokenizer.from_pretrained(model_id)
model = BlenderbotForConditionalGeneration.from_pretrained(model_id)

# Load profanity filter
profanity.load_censor_words()

@views.route('/chat', methods=['GET', 'POST'])
def chat():
    if not is_within_online_window():
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

    return render_template('chat.html')

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

# Home route to check for Zoom window and redirect if needed
@views.route('/')
def home():
    """Home route to display suggested posts, accounts, and handle Zoom meeting redirection."""
    
    # Check if access is within the allowed online window (10 AM - 8 PM PST)
    if not is_within_online_window():
        return redirect(url_for('views.access_restricted'))

    # Fetch suggested posts and accounts
    try:
        # Ensure `date_created` field exists in the `ForumPost` model
        suggested_posts = ForumPost.query.order_by(ForumPost.date_created.desc()).limit(5).all()

        # Ensure `last_login` field is being updated in the `User` model
        suggested_accounts = User.query.order_by(User.last_login.desc()).limit(5).all()

        # Log fetched data for debugging
        print(f"Number of suggested posts: {len(suggested_posts)}")
        for post in suggested_posts:
            print(f"Post ID: {post.id}, Post Title: {post.title}, Created At: {post.date_created}")

        print(f"Number of suggested accounts: {len(suggested_accounts)}")
        for account in suggested_accounts:
            print(f"User ID: {account.id}, User Email: {account.email}, Last Login: {account.last_login}")

    except Exception as e:
        print(f"Error fetching suggested posts or accounts: {str(e)}")
        suggested_posts, suggested_accounts = [], []  # Fallback to empty lists if there's an error

    # Check if within Zoom meeting window
    if is_within_zoom_window():
        flash("Meeting is live, redirecting to Zoom...", "info")
        try:
            access_token = get_access_token()
            zoom_meeting_url = schedule_zoom_meeting(access_token, "Meeting Topic", "2024-09-05T16:00:00Z", 40)
            if zoom_meeting_url:
                return redirect(zoom_meeting_url)
            else:
                flash("Error scheduling the Zoom meeting. Check logs for details.", "danger")
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            print(f"Exception occurred: {str(e)}")  # Log the exception

    # Render the home page with suggested posts and accounts
    return render_template('home.html', suggested_posts=suggested_posts, suggested_accounts=suggested_accounts)

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
    end_time = time(20, 0)    # 8 PM (24-hour format)
    
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

@views.route('/create_post/<int:forum_id>', methods=['GET', 'POST'])
@login_required
def create_post(forum_id):
    form = PostForm()
    forum = Forum.query.get_or_404(forum_id)

    if form.validate_on_submit():
        image_filename = None
        if form.image.data:
            image = form.image.data
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)

            # Ensure the directory exists
            upload_folder = os.path.dirname(image_path)
            if not os.path.exists(upload_folder):
                try:
                    os.makedirs(upload_folder, mode=0o755)
                except OSError as e:
                    flash(f'Error creating directory: {e}', 'danger')
                    return redirect(url_for('views.create_post', forum_id=forum_id))

            try:
                # Save the image file
                image.save(image_path)
            except PermissionError as e:
                flash(f'Permission error: {e}', 'danger')
                return redirect(url_for('views.create_post', forum_id=forum_id))
            except Exception as e:
                flash(f'Error saving image: {e}', 'danger')
                return redirect(url_for('views.create_post', forum_id=forum_id))

        new_post = ForumPost(
            title="Untitled",  # Default value for title
            content="",        # Default value for content
            forum_id=forum_id,
            user_id=current_user.id,
            image=image_filename
        )
        db.session.add(new_post)
        db.session.commit()

        flash('Your image has been uploaded!', 'success')
        return redirect(url_for('views.forum_detail', forum_id=forum_id))

    return render_template('create_post.html', form=form, forum=forum)

@views.route('/forums')
def forums():
    # Check if access is allowed based on the time window
    access_allowed = is_within_online_window()

    # Debug statement for checking access status
    views.logger.debug(f"Access allowed: {access_allowed}")

    # Redirect to access restricted page if access is not allowed
    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    # Redirect to a specific forum detail page by default (e.g., "Managing Intellectual Disabilities")
    forum_id = 1  # Replace with the appropriate forum ID
    return redirect(url_for('views.forum_detail', forum_id=forum_id))

@views.route('/forum/<int:forum_id>')
def forum_detail(forum_id):
    forum = Forum.query.get_or_404(forum_id)
    forum_posts = ForumPost.query.filter_by(forum_id=forum_id).all()
    return render_template('forum_detail.html', forum=forum, forum_posts=forum_posts)

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
    """Render the account page if within the allowed time window."""
    access_allowed = is_within_online_window()
    
    # Debug statement for checking access status
    print(f"Access allowed: {access_allowed}")

    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    edit_form = EditAccountForm()
    delete_form = DeleteAccountForm()
    
    # Handle account update
    if edit_form.validate_on_submit():
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

    # Pre-fill the form with current user data for GET request
    if request.method == 'GET':
        edit_form.name.data = current_user.name
        edit_form.bio.data = current_user.bio
        edit_form.website.data = current_user.website
        edit_form.gender.data = current_user.gender

    return render_template(
        'account.html',
        user=current_user,
        edit_form=edit_form,
        delete_form=delete_form
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

@views.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    edit_form = EditAccountForm()

    if edit_form.validate_on_submit():
        # Update user profile with form data
        current_user.first_name = edit_form.first_name.data
        current_user.name = edit_form.name.data
        current_user.email = edit_form.email.data
        current_user.bio = edit_form.bio.data
        current_user.gender = edit_form.gender.data
        current_user.website = edit_form.website.data
        current_user.birthday = edit_form.birthday.data  # Handle the birthday field

        # Commit changes to the database
        db.session.commit()

        # Flash success message and redirect to the profile page
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('views.account'))
    else:
        # If form is not validated, print errors for debugging
        for field, errors in edit_form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(edit_form, field).label.text}: {error}", 'danger')

    # Pre-fill form with current user data when GET request
    if request.method == 'GET':
        edit_form.first_name.data = current_user.first_name
        edit_form.name.data = current_user.name
        edit_form.email.data = current_user.email
        edit_form.bio.data = current_user.bio
        edit_form.gender.data = current_user.gender
        edit_form.website.data = current_user.website
        edit_form.birthday.data = current_user.birthday  # Pre-fill the birthday field

    return render_template('edit_profile.html', edit_form=edit_form)

def create_notification(notification_type, recipient, sender, message, post=None):
    notification = Notification(
        notification_type=notification_type,
        user_id=recipient.id,
        from_user_id=sender.id,
        message=message,
        post_id=post.id if post else None
    )
    db.session.add(notification)
    db.session.commit()

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
    print(f"Access allowed: {access_allowed}")

    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    return render_template('notifications.html', notifications=user_notifications)

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
        
        # Create a notification for the post author (now accessible via post.user)
        create_notification(
            notification_type='highfive_post',
            recipient=post.user,  # This will now work
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