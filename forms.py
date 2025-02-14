# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, TextAreaField, FloatField
from wtforms.validators import DataRequired, Email, EqualTo, Optional
from flask_wtf.file import FileField, FileAllowed

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SignupForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Sign Up')

class ProfileForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    # Password is optional—only update if provided
    password = PasswordField("Password", validators=[Optional()])
    # Allow only images
    picture = FileField("Profile Picture", validators=[Optional(), FileAllowed(['jpg', 'png', 'jpeg'], "Images only!")])
    submit = SubmitField("Update Profile")
class AdminAnimeForm(FlaskForm):
    mal_id = IntegerField("MAL ID", validators=[Optional()])
    
    # Anime fields (using StringField for numeric values so they display properly)
    title = StringField("Title", validators=[Optional()])
    rating = StringField("Rating", validators=[Optional()])
    quality = StringField("Quality", validators=[Optional()])
    episode_count = StringField("Episode Count", validators=[Optional()])  # as string for display
    anime_type = StringField("Type", validators=[Optional()])
    duration = StringField("Duration", validators=[Optional()])
    
    description = TextAreaField("Description", validators=[Optional()])
    japanese_title = StringField("Japanese Title", validators=[Optional()])
    synonyms = StringField("Synonyms", validators=[Optional()])
    
    aired = StringField("Aired", validators=[Optional()])
    premiered = StringField("Premiered", validators=[Optional()])
    status = StringField("Status", validators=[Optional()])
    mal_score = StringField("MAL Score", validators=[Optional()])  # as string for display
    
    genres = StringField("Genres", validators=[Optional()])
    studios = StringField("Studios", validators=[Optional()])
    producers = StringField("Producers", validators=[Optional()])
    
    poster_image = StringField("Poster Image URL", validators=[Optional()])
    portrait_image = StringField("Portrait Image URL", validators=[Optional()])
    
    fetch = SubmitField("Fetch from MAL")
    submit = SubmitField("Add Anime")
