from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms import TextAreaField, SubmitField, SelectField, IntegerField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, NumberRange

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

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email',
        validators=[DataRequired(), Email()])

    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password',
        validators=[DataRequired(), Length(min=6)])

    confirm_password = PasswordField('Confirm New Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])

    submit = SubmitField('Reset Password')

class DailyReflectionForm(FlaskForm):
    smile_today = TextAreaField("😊 What made you smile today?", validators=[DataRequired()])
    drained_today = TextAreaField("😞 What drained you today?", validators=[DataRequired()])
    grateful_today = TextAreaField("🙏 One thing you’re grateful for?", validators=[DataRequired()])
    submit = SubmitField("Save Reflection")

MOOD_CHOICES = [("😊 Happy", "😊 Happy"), ("😢 Sad", "😢 Sad"), ("😠 Angry", "😠 Angry"),
                ("😰 Anxious", "😰 Anxious"), ("😌 Calm", "😌 Calm")]

class SafetyPlanForm(FlaskForm):
    _box = dict(validators=[Optional(), Length(max=2000)])
    warning_signs = TextAreaField("⚠️ My warning signs: thoughts, feelings or situations that mean I'm heading into a crisis", **_box)
    coping_strategies = TextAreaField("🧘 Things I can do on my own to calm down", **_box)
    distractions = TextAreaField("🚶 People and places that help take my mind off things", **_box)
    people_to_contact = TextAreaField("📞 People I can ask for help (names and numbers)", **_box)
    professionals = TextAreaField("🩺 Professionals I can contact (therapist, doctor, clinic)", **_box)
    safe_environment = TextAreaField("🏠 How I can make my surroundings safer", **_box)
    reasons_to_live = TextAreaField("💗 What matters most to me and is worth staying for", **_box)
    helpline_name = StringField("My local crisis line (name)", validators=[Optional(), Length(max=120)])
    helpline_number = StringField("Its phone number", validators=[Optional(), Length(max=40)])
    submit = SubmitField("💾 Save My Plan")

class CopingLogForm(FlaskForm):
    activity = StringField("What did you try?", validators=[DataRequired(), Length(max=200)])
    mood_before = SelectField("How were you feeling before?", choices=MOOD_CHOICES)
    helped_rating = SelectField("How much did it help?", coerce=int,
                                choices=[(5, "5 – A lot"), (4, "4"), (3, "3 – Somewhat"), (2, "2"), (1, "1 – Not at all")])
    submit = SubmitField("💾 Log It")

class KindNoteForm(FlaskForm):
    content = TextAreaField("Leave a kind note for a stranger", validators=[DataRequired(), Length(min=5, max=300)])
    submit = SubmitField("💌 Send Anonymously")

class FutureLetterForm(FlaskForm):
    content = TextAreaField("Dear future me…", validators=[DataRequired(), Length(max=5000)])
    deliver_on = DateField("Open this letter on", validators=[DataRequired()])
    submit = SubmitField("✉️ Seal the Letter")
