from . import db
from flask_login import UserMixin
from datetime import datetime

# Notification model
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=True)

    def __repr__(self):
        return f'<Notification {self.id} - {self.notification_type}>'

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=True)  # Ensure nullable=True if you don't want this to be mandatory
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    profile_picture = db.Column(db.String(150), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    website = db.Column(db.String(100), nullable=True)
    show_suggestions = db.Column(db.Boolean, default=False)

    # Relationship to authored posts
    posts = db.relationship('ForumPost', backref='author', lazy=True)  # User posts will be accessible via 'author' in ForumPost
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    received_notifications = db.relationship('Notification',
                                             foreign_keys=[Notification.user_id],
                                             backref='recipient', lazy='dynamic',
                                             cascade='all, delete-orphan')
    sent_notifications = db.relationship('Notification',
                                         foreign_keys=[Notification.from_user_id],
                                         backref='sender', lazy='dynamic',
                                         cascade='all, delete-orphan')

    # Many-to-many relationship for saved posts
    saved_posts = db.relationship('ForumPost', secondary='saved_posts', backref='savers')

    # Followers and Following relationship
    followers = db.relationship('Follower', foreign_keys='Follower.followed_id',
                                backref='followed', lazy='dynamic')
    following = db.relationship('Follower', foreign_keys='Follower.follower_id',
                                backref='follower', lazy='dynamic')

# Association table for saved posts
saved_posts = db.Table('saved_posts',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('forum_post.id'))
)

# Category model
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    forums = db.relationship('Forum', backref='category', lazy=True)

# Forum model
class Forum(db.Model):
    __tablename__ = 'forum'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    posts = db.relationship('ForumPost', backref='forum', lazy=True)

# ForumPost model
class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    forum_id = db.Column(db.Integer, db.ForeignKey('forum.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())  # Ensure this field exists
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    is_viewed_by_user = db.Column(db.Boolean, default=False)

    # Relationship to comments
    comments = db.relationship('Comment', backref='post', lazy=True)

    def __repr__(self):
        return f"ForumPost('{self.title}', '{self.date_created}')"

    def upvote_count(self):
        return self.upvotes

    def downvote_count(self):
        return self.downvotes

    def total_votes(self):
        return self.upvotes - self.downvotes

# Upvote model
class Upvote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# Downvote model
class Downvote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# Comment model
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    forum_post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())

# Like model
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Follower model
class Follower(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    follower_user = db.relationship('User', foreign_keys=[follower_id], backref='following_user')
    followed_user = db.relationship('User', foreign_keys=[followed_id], backref='followed_user')