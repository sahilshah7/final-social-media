from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField, TextAreaField
from wtforms.validators import InputRequired, Length, Email, EqualTo
from flask_wtf.file import FileField, FileAllowed
from wtforms.validators import DataRequired, Optional, URL

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=150)])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=25)])
    first_name = StringField('First Name', validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Submit')

class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    comment = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Post Comment')

class EditAccountForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=2, max=50)])
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(min=6, max=150)])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=150)])
    gender = StringField('Gender', validators=[Optional(), Length(max=50)])
    website = StringField('Website', validators=[Optional(), URL(), Length(max=100)])  # Added URL validation
    submit = SubmitField('Save Changes')


class DeleteAccountForm(FlaskForm):
    submit = SubmitField('Delete Account')

class ProfilePictureForm(FlaskForm):
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Update Picture')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email(), Length(max=150)])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=150)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class FollowForm(FlaskForm):
    pass  # This form doesn't need any fields, just CSRF protection

class EditProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    website = StringField('Website', validators=[URL(), Length(max=100)])
    bio = TextAreaField('Bio', validators=[Length(max=150)])
    gender = SelectField('Gender', choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    profile_picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    
    # Add the show_suggestions field as a BooleanField
    show_suggestions = BooleanField('Show account suggestions')
    
    submit = SubmitField('Save Changes')
    
class UpdateProfilePictureForm(FlaskForm):
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Update Picture')

class DeleteAccountForm(FlaskForm):
    submit = SubmitField('Delete Account')
