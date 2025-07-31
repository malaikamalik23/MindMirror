from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

class SignupForm(FlaskForm):
    username = StringField('Username', 
        validators=[DataRequired(), Length(min=2, max=20)])
    
    email = StringField('Email', 
        validators=[DataRequired(), Email()])
    
    password = PasswordField('Password', 
        validators=[DataRequired(), Length(min=6)])
    
    confirm_password = PasswordField('Confirm Password', 
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', 
        validators=[DataRequired(), Email()])
    
    password = PasswordField('Password', 
        validators=[DataRequired()])
    
    remember = BooleanField('Remember Me')
    
    submit = SubmitField('Login')

class DailyReflectionForm(FlaskForm):
    smile_today = TextAreaField("😊 What made you smile today?", validators=[DataRequired()])
    drained_today = TextAreaField("😞 What drained you today?", validators=[DataRequired()])
    grateful_today = TextAreaField("🙏 One thing you’re grateful for?", validators=[DataRequired()])
    submit = SubmitField("Save Reflection")
