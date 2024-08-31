from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from .models import ForumPost, Comment, Like, User, Follower, Category, Forum, Notification, Upvote, Downvote, HighFive
from .forms import PostForm, CommentForm, EditAccountForm, DeleteAccountForm, FollowForm, EditProfileForm, HighFiveForm
from . import db
import os
from werkzeug.utils import secure_filename
import logging
from flask_wtf import FlaskForm
import re
from datetime import datetime, time
import pytz

# Blueprint setup
views = Blueprint('views', __name__)
logging.basicConfig(level=logging.DEBUG)

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

from datetime import datetime, time
import pytz

def is_within_online_window():
    """Check if the current time is within the allowed online window."""
    # Define timezone
    pst = pytz.timezone('America/Los_Angeles')
    
    # Get current time in the specified timezone
    now = datetime.now(pst).time()
    print(f"Current time: {now}")  # Debugging statement
    
    # Define start and end time for the online window
    start_time = time(10, 0)  # 10 AM
    end_time = time(23, 59)    # 11:59 PM (24-hour format)
    
    # Debugging statements
    print(f"Start time: {start_time}")
    print(f"End time: {end_time}")

    # Check if the current time is within the allowed time window
    is_within_window = start_time <= now <= end_time
    print(f"Is within window: {is_within_window}")  # Debugging statement
    return is_within_window

@views.route('/')
def home():
    """Render the home page if within the allowed time window."""
    access_allowed = is_within_online_window()
    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    # Retrieve the 5 most recent posts
    suggested_posts = ForumPost.query.order_by(ForumPost.date_created.desc()).limit(5).all()
    # Retrieve the first 5 users (or adjust as needed)
    suggested_accounts = User.query.limit(5).all()
    # Check if all suggested posts have been viewed by the user
    all_viewed = all(post.is_viewed_by_user for post in suggested_posts)
    
    # Render the home page with the posts, accounts, and viewed status
    return render_template(
        'home.html', 
        suggested_posts=suggested_posts, 
        suggested_accounts=suggested_accounts, 
        all_viewed=all_viewed
    )

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


@views.route('/save_post/<int:post_id>', methods=['POST'])
@login_required
def save_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    if current_user in post.savers:
        current_user.saved_posts.remove(post)
        db.session.commit()
        flash('Post unsaved.', 'info')
    else:
        current_user.saved_posts.append(post)
        db.session.commit()
        flash('Post saved!', 'success')
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
            image_filename = secure_filename(form.image.data.filename)
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_filename)
            form.image.data.save(image_path)

        new_post = ForumPost(
            title="Untitled",  # Default title, since the title field is removed
            content="",  # Empty content since content field is removed
            forum_id=forum_id,
            user_id=current_user.id,
            image=image_filename  # Save image filename to the post
        )
        db.session.add(new_post)
        db.session.commit()

        # Notify followers about the new post
        followers = current_user.followers
        for follower in followers:
            create_notification(
                'post', 
                follower.follower_user, 
                current_user, 
                f'{current_user.username} uploaded a new image.', 
                new_post
            )

        flash('Your image has been uploaded!', 'success')
        return redirect(url_for('views.forum_detail', forum_id=forum_id))

    return render_template('create_post.html', form=form, forum=forum)

@views.route('/forums')
def forums():
    # Check if access is allowed based on the time window
    access_allowed = is_within_online_window()
    
    # Debug statement for checking access status
    print(f"Access allowed: {access_allowed}")

    if not access_allowed:
        return redirect(url_for('views.access_restricted'))

    categories = Category.query.all()
    return render_template('forums.html', categories=categories)

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

    if post.user_id == current_user.id:
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully', 'success')
        return redirect(url_for('views.forums'))
    else:
        flash('You do not have permission to delete this post', 'danger')
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

        # Commit changes to the database
        db.session.commit()

        # Flash success message and redirect to the profile page
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('views.account'))

    # Pre-fill form with current user data when GET request
    if request.method == 'GET':
        edit_form.first_name.data = current_user.first_name
        edit_form.name.data = current_user.name
        edit_form.email.data = current_user.email
        edit_form.bio.data = current_user.bio
        edit_form.gender.data = current_user.gender
        edit_form.website.data = current_user.website

    return render_template('edit_profile.html', edit_form=edit_form)

def create_notification(notification_type, to_user, from_user, message, post=None):
    notification = Notification(
        notification_type=notification_type,
        user_id=to_user.id,
        from_user_id=from_user.id,
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

@views.route('/give_highfive/<int:post_id>', methods=['POST'])  # New route for giving a high five
@login_required
def give_highfive(post_id):
    post = ForumPost.query.get_or_404(post_id)
    existing_highfive = HighFive.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if not existing_highfive:
        new_highfive = HighFive(user_id=current_user.id, post_id=post_id)
        db.session.add(new_highfive)
        db.session.commit()

        if current_user.id != post.user_id:
            create_notification(
                notification_type='highfive',
                to_user=post.author,
                from_user=current_user,
                message=f'{current_user.first_name} gave your post a high five!',
                post=post
            )
    else:
        flash('You have already given this post a high five.', 'info')

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