from . import db
from flask_login import UserMixin
from datetime import datetime

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # recipient
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # sender
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=True)
    
    def __repr__(self):
        return f'<Notification {self.id} - {self.notification_type}>'
    
def create_notification(user_id, from_user_id, message, post_id=None):
    notification = Notification(
        user_id=user_id,
        from_user_id=from_user_id,
        message=message,
        post_id=post_id
    )
    db.session.add(notification)
    db.session.commit()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    last_name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    profile_picture = db.Column(db.String(150), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)  # Make sure this is being updated when users log in
    bio = db.Column(db.Text, nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    website = db.Column(db.String(100), nullable=True)
    show_suggestions = db.Column(db.Boolean, default=False)
    birthday = db.Column(db.Date, nullable=True)  # New field for birthday
    
    posts = db.relationship('ForumPost', backref='author', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy=True, cascade='all, delete-orphan')
    highfives = db.relationship('HighFive', backref='user', lazy=True, cascade='all, delete-orphan')

    received_notifications = db.relationship('Notification', foreign_keys=[Notification.user_id], backref='recipient', lazy='dynamic', cascade='all, delete-orphan')
    sent_notifications = db.relationship('Notification', foreign_keys=[Notification.from_user_id], backref='sender', lazy='dynamic', cascade='all, delete-orphan')

    saved_posts = db.relationship('ForumPost', secondary='saved_posts', backref='savers')

    followers = db.relationship('Follower', foreign_keys='Follower.followed_id', backref='followed', lazy='dynamic', cascade='all, delete-orphan')
    following = db.relationship('Follower', foreign_keys='Follower.follower_id', backref='follower', lazy='dynamic', cascade='all, delete-orphan')

saved_posts = db.Table('saved_posts',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('post_id', db.Integer, db.ForeignKey('forum_post.id'))
)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    forums = db.relationship('Forum', backref='category', lazy=True, cascade='all, delete-orphan')

class Forum(db.Model):
    __tablename__ = 'forum'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    posts = db.relationship('ForumPost', backref='forum', lazy=True, cascade='all, delete-orphan')

class ForumPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=True)
    content = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(120), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    forum_id = db.Column(db.Integer, db.ForeignKey('forum.id'), nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # Make sure this is present
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    is_viewed_by_user = db.Column(db.Boolean, default=False)

    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    highfives = db.relationship('HighFive', backref='post', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"ForumPost('{self.title}', '{self.date_created}')"

class Upvote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Downvote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    forum_post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HighFive(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Follower(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    follower_user = db.relationship('User', foreign_keys=[follower_id], backref='following_user')
    followed_user = db.relationship('User', foreign_keys=[followed_id], backref='followed_user')