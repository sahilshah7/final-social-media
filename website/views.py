from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_required, current_user
from .models import ForumPost, Comment, Like, User, Follower, Category, Forum, Notification, Upvote, Downvote
from .forms import PostForm, CommentForm, EditAccountForm, DeleteAccountForm, FollowForm, EditProfileForm
from . import db
import os
from werkzeug.utils import secure_filename
import logging
from flask_wtf import FlaskForm
import re

# Blueprint setup
views = Blueprint('views', __name__)
logging.basicConfig(level=logging.DEBUG)

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
    post = ForumPost.query.get_or_404(id)  # Using ForumPost instead of Post
    form = CommentForm()

    if form.validate_on_submit():
        # Save the new comment
        comment = Comment(content=form.comment.data, user_id=current_user.id, forum_post_id=post.id)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('views.forum_post', id=post.id))  # Redirect after POST

    comments = Comment.query.filter_by(forum_post_id=post.id).all()
    return render_template('forum_post.html', post=post, form=form, comments=comments)

# Example function to populate categories in the database
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
        # Unfollow the user
        db.session.delete(follow_record)
        db.session.commit()
        flash(f'You have unfollowed {user.first_name}.', 'success')
    else:
        # Follow the user
        new_follow = Follower(follower_id=current_user.id, followed_id=user.id)
        db.session.add(new_follow)
        db.session.commit()
        flash(f'You are now following {user.first_name}.', 'success')

    return redirect(url_for('views.public_account', user_id=user_id))


# Homepage route
@views.route('/')
def home():
    # Fetch suggested posts (e.g., based on some criteria like most recent or most liked)
    suggested_posts = ForumPost.query.order_by(ForumPost.date_created.desc()).limit(5).all()

    # Fetch suggested accounts (e.g., accounts that the user might be interested in following)
    suggested_accounts = User.query.limit(5).all()

    # Check if all suggested posts are viewed
    all_viewed = all(post.is_viewed_by_user for post in suggested_posts)

    # Render the homepage with suggested posts and accounts
    return render_template('home.html', suggested_posts=suggested_posts, suggested_accounts=suggested_accounts, all_viewed=all_viewed)

# Example route to trigger category population (Optional)
@views.route('/populate')
def populate():
    populate_categories()
    return "Categories populated!"

@views.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    post = ForumPost.query.get_or_404(post_id)
    
    # Fetch all comments related to this post
    comments = Comment.query.filter_by(forum_post_id=post_id).order_by(Comment.date_created.asc()).all()

    if request.method == 'POST':
        content = request.form.get('content')

        if not content:
            flash('Comment cannot be empty', 'danger')
        else:
            # Make sure user is logged in and comment is saved properly
            new_comment = Comment(content=content, user_id=current_user.id, forum_post_id=post.id)
            db.session.add(new_comment)
            db.session.commit()

            flash('Comment added successfully!', 'success')
            return redirect(url_for('views.post_detail', post_id=post.id))

    return render_template('post_detail.html', post=post, comments=comments)

# Forums route
@views.route('/forums')
def forums():
    categories = Category.query.all()  # Query all categories
    return render_template('forums.html', categories=categories)

# Forum detail route
@views.route('/forum/<int:forum_id>')
def forum_detail(forum_id):
    forum = Forum.query.get_or_404(forum_id)
    forum_posts = ForumPost.query.filter_by(forum_id=forum_id).all()
    return render_template('forum_detail.html', forum=forum, forum_posts=forum_posts)

# Create a new post in a forum
@views.route('/forum/<int:forum_id>/create_post', methods=['GET', 'POST'])
@login_required
def create_post(forum_id):
    form = PostForm()
    forum = Forum.query.get_or_404(forum_id)

    if form.validate_on_submit():
        new_post = ForumPost(
            title=form.title.data,
            content=form.content.data,
            forum_id=forum_id,
            user_id=current_user.id
        )
        db.session.add(new_post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('views.forum_detail', forum_id=forum_id))

    return render_template('create_post.html', form=form, forum=forum)

# Add a comment to a post
@views.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def comment_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    comment_content = request.form.get('content')

    if not comment_content:
        flash('Comment cannot be empty', 'danger')
        return redirect(url_for('views.post_detail', post_id=post_id))

    # Add the comment (code not shown)

    # Tag users if the comment contains '@username'
    mentions = re.findall(r'@(\w+)', comment_content)
    for username in mentions:
        user = User.query.filter_by(username=username).first()
        if user and user not in post.tagged_users:
            post.tagged_users.append(user)
            db.session.commit()

    flash('Comment added successfully!', 'success')
    return redirect(url_for('views.post_detail', post_id=post_id))

# Delete a post
@views.route('/delete-post/<int:id>', methods=['POST'])
@login_required
def delete_post(id):
    post = ForumPost.query.get_or_404(id)

    if post.user_id == current_user.id:
        db.session.delete(post)
        db.session.commit()
        return jsonify({}), 200
    else:
        return jsonify({'error': 'You do not have permission to delete this post'}), 403

# Account management route
@views.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    # Instantiate the forms
    edit_form = EditAccountForm()
    delete_form = DeleteAccountForm()

    # Handle form submissions for updating account details
    if edit_form.validate_on_submit():
        current_user.name = edit_form.name.data
        current_user.bio = edit_form.bio.data
        current_user.website = edit_form.website.data
        current_user.gender = edit_form.gender.data
        db.session.commit()
        flash('Account updated successfully!', 'success')
        return redirect(url_for('views.account'))

    # Pre-fill form data for GET requests
    if request.method == 'GET':
        edit_form.name.data = current_user.name
        edit_form.bio.data = current_user.bio
        edit_form.website.data = current_user.website
        edit_form.gender.data = current_user.gender

    # Handle delete account form submission
    if delete_form.validate_on_submit():
        db.session.delete(current_user)
        db.session.commit()
        flash('Account deleted successfully', 'success')
        return redirect(url_for('auth.login'))

    # Render the account template and pass the forms to it
    return render_template('account.html', 
                           user=current_user, 
                           edit_form=edit_form, 
                           delete_form=delete_form)

# Delete account route
@views.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    db.session.delete(user)
    db.session.commit()
    flash('Account deleted successfully', 'success')
    return redirect(url_for('auth.login'))

# Edit profile route
@views.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    edit_form = EditProfileForm()
    # Remove the picture_form references here
    
    if edit_form.validate_on_submit():
        current_user.first_name = edit_form.name.data
        current_user.website = edit_form.website.data
        current_user.bio = edit_form.bio.data
        current_user.gender = edit_form.gender.data
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('views.account'))

    if request.method == 'GET':
        edit_form.name.data = current_user.first_name
        edit_form.website.data = current_user.website
        edit_form.bio.data = current_user.bio
        edit_form.gender.data = current_user.gender

    return render_template('edit_profile.html', user=current_user, edit_form=edit_form)

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

# Like and upvote functionality
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

# Notifications
@views.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    return render_template('notifications.html', notifications=user_notifications)

# Mark notification as read
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

    # Initialize the follow/unfollow form
    form = FollowForm()

    # Check if the current user is authenticated
    if current_user.is_authenticated:
        # Check if the form is submitted (follow/unfollow action)
        if form.validate_on_submit():
            if form.follow.data:  # If the follow button is clicked
                if user not in current_user.following:  # Add the user to current user's following list if not already
                    follow = Follower(follower_id=current_user.id, followed_id=user.id)
                    db.session.add(follow)
                    db.session.commit()
                    flash(f'You are now following {user.first_name}', 'success')
            elif form.unfollow.data:  # If the unfollow button is clicked
                if user in current_user.following:  # Remove the user from current user's following list
                    follow = Follower.query.filter_by(follower_id=current_user.id, followed_id=user.id).first()
                    if follow:
                        db.session.delete(follow)
                        db.session.commit()
                        flash(f'You have unfollowed {user.first_name}', 'info')

    # Retrieve followers and following lists
    followers_list = Follower.query.filter_by(followed_id=user.id).all()  # List of users who follow this user
    following_list = Follower.query.filter_by(follower_id=user.id).all()  # List of users this user is following

    return render_template('public_account.html', user=user, form=form, followers=followers_list, following=following_list)
