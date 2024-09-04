from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from .forms import LoginForm, RegistrationForm, RequestResetForm, ResetPasswordForm
from . import db, mail
from flask_mail import Message
from .tokens import generate_confirmation_token, confirm_token

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        print("Form was submitted!")  # Debugging line
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect(url_for('views.home'))
        else:
            flash('Invalid email or password', 'error')
    else:
        print("Form did not validate")  # Debugging line
        print("Email valid:", form.email.validate(form))  # Test email validation
        print("Password valid:", form.password.validate(form))  # Test password validation
        print(form.errors)  # Print form errors to debug

    return render_template('login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

from flask import render_template, redirect, url_for, flash
from . import db
from .models import User
from .forms import RegistrationForm
from flask_login import login_user
from werkzeug.security import generate_password_hash

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    form = RegistrationForm()

    if form.validate_on_submit():
        email = form.email.data
        username = form.username.data
        first_name = form.first_name.data
        name = form.name.data  # Ensure this field exists and is required
        last_name = form.last_name.data
        password = form.password.data
        birthday=form.birthday.data

        # Check if the email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already in use', 'error')
            return redirect(url_for('auth.sign_up'))

        # Check if the username already exists
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username is already taken', 'error')
            return redirect(url_for('auth.sign_up'))

        # Create a new user instance
        new_user = User(
            email=email,
            username=username,
            first_name=first_name,
            name=name,  # The name field is used here
            last_name=last_name,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )

        # Add the user to the database
        db.session.add(new_user)
        db.session.commit()

        # Log in the newly created user
        login_user(new_user)

        flash('Your account has been created! You are now logged in.', 'success')
        return redirect(url_for('views.home'))

    # Render the sign-up page with the form
    return render_template('sign_up.html', form=form)

@auth.route('/reset_password_request', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash('No account found with that email.', 'error')
    return render_template('reset_request.html', form=form)

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    email = confirm_token(token)
    if not email:
        flash('The reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
            db.session.commit()
            flash('Your password has been updated!', 'success')
            return redirect(url_for('auth.login'))
    return render_template('reset_token.html', form=form)

def send_reset_email(user):
    token = generate_confirmation_token(user.email)
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('auth.reset_token', token=token, _external=True)}

If you did not make this request, simply ignore this email and no changes will be made.
'''
    mail.send(msg)
