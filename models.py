from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):  # ✅ Inherit from UserMixin
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    image_file = db.Column(db.String(150), nullable=False, default='default.jpg')

    # Relationships
    entries = db.relationship("JournalEntry", backref="author", lazy=True)
    reflections = db.relationship("DailyReflection", backref="author", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}, {self.email}, {self.image_file}>"

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    mood = db.Column(db.String(50), nullable=False)  # ✅ Mood tracking
    response = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"<JournalEntry {self.id} by User {self.user_id}>"

class DailyReflection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    smile_today = db.Column(db.Text, nullable=True)
    drained_today = db.Column(db.Text, nullable=True)
    grateful_today = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class MoodLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mood = db.Column(db.String(50), nullable=False)  # e.g., 'happy', 'anxious'
    emotions = db.Column(db.String(200))  # comma-separated
    notes = db.Column(db.Text)  # Optional notes
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='mood_logs')

# ── Vault ──────────────────────────────────────────────
class VaultEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    encrypted_content = db.Column(db.Text, nullable=False)
    write_and_burn = db.Column(db.Boolean, default=False)
    viewed = db.Column(db.Boolean, default=False)
    auto_delete = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── Letters to Future Me ───────────────────────────────
class FutureLetter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    deliver_at = db.Column(db.DateTime, nullable=False)
    delivered = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── Anonymous Support Pool ─────────────────────────────
class SupportMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── What Helped Me ─────────────────────────────────────
class CopingLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity = db.Column(db.String(200), nullable=False)
    helped_rating = db.Column(db.Integer)  # 1 to 5
    mood_before = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ── Emergency Safety Plan ──────────────────────────────
class SafetyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    warning_signs = db.Column(db.Text)       # thoughts, moods, situations that signal a crisis
    coping_strategies = db.Column(db.Text)   # things I can do on my own to feel calmer
    distractions = db.Column(db.Text)        # people and places that take my mind off things
    people_to_contact = db.Column(db.Text)   # people I can ask for help (names + numbers)
    professionals = db.Column(db.Text)       # therapist, doctor, local crisis line
    safe_environment = db.Column(db.Text)    # how to make my surroundings safer
    reasons_to_live = db.Column(db.Text)     # what matters most to me
    helpline_name = db.Column(db.String(120))
    helpline_number = db.Column(db.String(40))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)