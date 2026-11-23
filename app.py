from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config  # config.py loads .env itself, before reading SECRET_KEY
from models import (db, User, JournalEntry, DailyReflection, MoodLog,
                    SafetyPlan, CopingLog, SupportMessage, FutureLetter)
from forms import (SignupForm, LoginForm, DailyReflectionForm, ForgotPasswordForm, ResetPasswordForm,
                   SafetyPlanForm, CopingLogForm, KindNoteForm, FutureLetterForm, MOOD_CHOICES)
from sqlalchemy import func
from datetime import date, timedelta
import random
from flask_migrate import Migrate
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # render charts off-screen; the default GUI backend crashes inside a web server
import matplotlib.pyplot as plt
import io
import os
import re
import base64

RESET_TOKEN_MAX_AGE = 60 * 60  # reset links expire after 1 hour

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html', title="About")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('signup'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html', form=form)

def _reset_serializer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='password-reset')

def make_reset_token(user):
    # Part of the current password hash goes into the token, so the link
    # stops working as soon as the password has been changed (single use).
    return _reset_serializer().dumps({'uid': user.id, 'ph': user.password_hash[-16:]})

def user_from_reset_token(token):
    try:
        data = _reset_serializer().loads(token, max_age=RESET_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get('uid'))
    if user is None or user.password_hash[-16:] != data.get('ph'):
        return None
    return user

def send_reset_link(user, link):
    # No mail server is configured yet. Until Flask-Mail (or similar) is set up,
    # the link is written to the server console so the developer can use it.
    # Replace this with a real email send before going live.
    app.logger.warning("Password reset link for %s: %s", user.email, link)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            link = url_for('reset_password', token=make_reset_token(user), _external=True)
            send_reset_link(user, link)
        # Same message whether or not the account exists, so this page
        # can't be used to find out who is registered.
        flash("If that email is registered, a reset link has been sent. It expires in 1 hour.", "info")
        return redirect(url_for('login'))

    return render_template('forgot_password.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = user_from_reset_token(token)
    if user is None:
        flash("That reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Password updated. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    new_letters = deliver_due_letters(current_user.id)
    return render_template('dashboard.html', new_letters=new_letters)

@app.route('/journal', methods=['GET', 'POST'])
@login_required
def journal():
    if request.method == 'POST':
        content = request.form['content']
        mood = request.form['mood']

        # No AI reflection now
        entry = JournalEntry(content=content, mood=mood, user_id=current_user.id, response=None)
        db.session.add(entry)
        db.session.commit()
        flash("Journal entry saved!", "success")
        return redirect(url_for('journal'))

    page = request.args.get('page', 1, type=int)
    filter_mood = request.args.get('filter_mood')
    per_page = 5
    if filter_mood:
        entries = JournalEntry.query.filter_by(user_id=current_user.id, mood=filter_mood).order_by(
            JournalEntry.timestamp.desc()
        ).paginate(page=page, per_page=per_page)
    else:
        entries = JournalEntry.query.filter_by(user_id=current_user.id).order_by(
            JournalEntry.timestamp.desc()
        ).paginate(page=page, per_page=per_page)

    return render_template('journal.html', entries=entries, filter_mood=filter_mood)

@app.route('/edit-entry/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)

    if entry.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for('journal'))

    if request.method == 'POST':
        entry.content = request.form['content']
        entry.mood = request.form['mood']
        db.session.commit()
        flash("Entry updated successfully.", "success")
        return redirect(url_for('journal'))

    return render_template('edit_entry.html', entry=entry)

# ── Chatbot ────────────────────────────────────────────
# Messages that may mean someone is thinking about suicide or self-harm.
# These always get crisis resources, whatever else the message says.
CRISIS_PATTERNS = [
    r"\bkill(ing)? myself\b", r"\bsuicid", r"\bend(ing)? (my|it) (life|all)\b",
    r"\bend it all\b", r"\b(want|wanna|going) to die\b", r"\bwish i (was|were) dead\b",
    r"\bbetter off dead\b", r"\bdon'?t want to (live|be alive|be here|exist)\b",
    r"\bno reason to live\b", r"\bself[- ]?harm", r"\b(hurt|hurting|cut|cutting) myself\b",
    r"\bwant to disappear\b", r"\bjust want it (all )?to stop\b",
    r"\bcan'?t (do|take) (this|it) anymore\b", r"\bgive up on (life|living)\b",
]

CRISIS_RESOURCES = (
    "I'm really glad you told me. You deserve support from a real person right now. "
    "If you are in danger or might act on these thoughts, please call your local emergency number. "
    "You can find a free, confidential crisis line in your country at findahelpline.com "
    "(in the US, call or text 988). If you can, reach out to someone you trust and let them know how you're feeling. "
    "I'm a simple support bot and can't replace that, but I'm here to keep talking."
)

SUPPORT_RESPONSES = {
        "i'm not okay": "It’s okay to not be okay. You’re not alone—I’m here with you.",
        "i feel so alone": "You’re not alone in this moment. I’m here for you.",
        "i can’t do this anymore": "That sounds really heavy. Let’s take it one breath at a time together.",
        "i feel broken": "You’re not broken. You’re a human being going through a really hard time.",
        "i hate myself": "You deserve compassion—even from yourself. I’m here.",
        "i feel like giving up": "You’ve made it this far. Let’s talk about what’s making you feel this way.",
        "i don’t want to be here": "That sounds painful. You matter. I’m here with you.",
        "no one cares about me": "I care about you. You’re not invisible to me.",
        "i feel anxious": "Let’s breathe together. You’re not alone.",
        "i feel like i’m drowning": "When it’s all too much, just focus on this moment. We’ll get through it.",
        "i can’t breathe": "You’re safe. Breathe in for 4 seconds, hold, and exhale. I’m with you.",
        "everything hurts": "I'm so sorry you're in pain. Want to talk more about it?",
        "i feel worthless": "You matter more than you think. Let’s talk.",
        "i just want it to stop": "That sounds really hard. I’m here for you.",
        "i’m scared": "Want to talk about what’s worrying you? I’m here.",
        "i don’t feel anything": "Feeling numb is okay. You're not broken.",
        "i’m tired": "You’re doing your best. Let’s pause and breathe.",
        "i feel like a failure": "You're not a failure. You're struggling, and that’s okay.",
        "i feel like crying": "It’s okay to cry. I’m here with you.",
        "i’m angry": "You have every right to feel angry. Want to talk about it?",
        "i feel lost": "Let’s take one step at a time. You’re not alone.",
        "why am i like this": "You’re doing your best. You’re not alone in this.",
        "i messed everything up": "Mistakes don’t define you. You’re still worthy of love.",
        "i feel so much pressure": "That pressure must be exhausting. You’re allowed to slow down.",
        "i want to disappear": "Please stay. The world is better with you in it.",
        "i feel ashamed": "You deserve understanding, not judgment.",
        "nobody gets me": "I want to understand. Tell me more.",
        "i feel hopeless": "I know it’s hard. But I believe in you.",
        "i’m panicking": "Let’s slow your breath and find calm together.",
        "nothing matters anymore": "You matter—and I’m here for you."
}

FALLBACK_REPLY = (
    "I'm still learning, so I didn't quite understand that, but I'm listening. "
    "Can you tell me a little more about how you're feeling right now?"
)

def normalize_message(text):
    # Curly apostrophes (’) vs straight ones (') made many phrases impossible to match.
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .!?,")

_NORMALIZED_RESPONSES = {normalize_message(k): v for k, v in SUPPORT_RESPONSES.items()}
_CRISIS_RE = [re.compile(p) for p in CRISIS_PATTERNS]

def chatbot_reply(message):
    text = normalize_message(message)
    if not text:
        return {'reply': "Please say something so I can help!", 'crisis': False}

    if any(p.search(text) for p in _CRISIS_RE):
        supportive = _NORMALIZED_RESPONSES.get(text)
        reply = f"{supportive} {CRISIS_RESOURCES}" if supportive else CRISIS_RESOURCES
        return {'reply': reply, 'crisis': True}

    if text in _NORMALIZED_RESPONSES:
        return {'reply': _NORMALIZED_RESPONSES[text], 'crisis': False}

    # Longer messages that contain a known phrase ("honestly i feel so alone lately")
    for phrase, reply in _NORMALIZED_RESPONSES.items():
        if phrase in text:
            return {'reply': reply, 'crisis': False}

    return {'reply': FALLBACK_REPLY, 'crisis': False}

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        return jsonify(chatbot_reply(str(data.get("message", ""))))

    return render_template('chat.html')

@app.route('/affirmations')
def affirmations():
    return render_template('affirmations.html')

@app.route('/daily-reflection', methods=['GET', 'POST'])
@login_required
def daily_reflection():
    form = DailyReflectionForm()
    if form.validate_on_submit():
        reflection = DailyReflection(
            smile_today=form.smile_today.data,
            drained_today=form.drained_today.data,
            grateful_today=form.grateful_today.data,
            user_id=current_user.id
        )
        db.session.add(reflection)
        db.session.commit()
        flash("Reflection saved!", "success")
        return redirect(url_for('daily_reflection'))

    page = request.args.get('page', 1, type=int)
    reflections = DailyReflection.query.filter_by(user_id=current_user.id).order_by(
        DailyReflection.timestamp.desc()).paginate(page=page, per_page=4)
    return render_template("daily_reflection.html", form=form, reflections=reflections)

@app.route('/delete-reflection/<int:reflection_id>', methods=['POST'])
@login_required
def delete_reflection(reflection_id):
    reflection = DailyReflection.query.get_or_404(reflection_id)
    if reflection.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('daily_reflection'))

    db.session.delete(reflection)
    db.session.commit()
    flash("Reflection deleted.", "success")
    return redirect(url_for('daily_reflection'))

@app.route('/edit-reflection/<int:reflection_id>', methods=['GET', 'POST'])
@login_required
def edit_reflection(reflection_id):
    reflection = DailyReflection.query.get_or_404(reflection_id)

    if reflection.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for('daily_reflection'))

    form = DailyReflectionForm(obj=reflection)

    if form.validate_on_submit():
        reflection.smile_today = form.smile_today.data
        reflection.drained_today = form.drained_today.data
        reflection.grateful_today = form.grateful_today.data
        db.session.commit()
        flash("Reflection updated successfully.", "success")
        return redirect(url_for('daily_reflection'))

    # Editing happens in a modal on the reflections page. Previously nothing was
    # returned here, which crashed; now an invalid edit goes back with a message.
    if request.method == 'POST':
        flash("Couldn't update the reflection. Please fill in all three answers.", "danger")
    return redirect(url_for('daily_reflection'))

@app.route('/mood-tracker', methods=['GET', 'POST'])
@login_required
def mood_tracker():
    if request.method == 'POST':
        mood = request.form.get('mood')
        emotions = request.form.getlist('emotions')
        emotions_str = ', '.join(emotions)
        notes = (request.form.get('notes') or '').strip() or None
        log = MoodLog(mood=mood, emotions=emotions_str, notes=notes, user_id=current_user.id)
        db.session.add(log)
        db.session.commit()
        flash("Mood logged!", "success")
        return redirect(url_for('mood_tracker'))

    logs = MoodLog.query.filter_by(user_id=current_user.id).order_by(MoodLog.timestamp.desc()).all()
    emotion_counts = {}
    for log in logs:
        if log.emotions:
            for emotion in log.emotions.split(", "):
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

    chart_url = None
    if emotion_counts:
        fig, ax = plt.subplots()
        ax.pie(emotion_counts.values(), labels=emotion_counts.keys(), autopct='%1.1f%%')
        ax.set_title("Emotion Overview")
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        chart_url = base64.b64encode(img.getvalue()).decode()
        plt.close(fig)

    return render_template('mood_tracker.html', logs=logs, chart_url=chart_url)

@app.route('/delete_mood/<int:log_id>', methods=['POST'])
@login_required
def delete_mood(log_id):
    log = MoodLog.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for('mood_tracker'))
    db.session.delete(log)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for('mood_tracker'))

@app.route('/delete-entry/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for('journal'))
    db.session.delete(entry)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for('journal'))

@app.route('/new-session')
@login_required
def new_session():
    # A fresh-start check-in: a short breathing exercise, then pick what to do next.
    return render_template('new_session.html', title="New Session")

# ── Emergency Safety Plan ──────────────────────────────
@app.route('/safety-plan', methods=['GET', 'POST'])
def safety_plan():
    # Open to everyone: someone in crisis shouldn't have to log in to see helplines.
    plan = None
    form = None
    if current_user.is_authenticated:
        plan = SafetyPlan.query.filter_by(user_id=current_user.id).first()
        form = SafetyPlanForm(obj=plan)
        if form.validate_on_submit():
            if plan is None:
                plan = SafetyPlan(user_id=current_user.id)
                db.session.add(plan)
            form.populate_obj(plan)
            db.session.commit()
            flash("Your safety plan is saved. You can print it or keep this page bookmarked.", "success")
            return redirect(url_for('safety_plan'))
    editing = request.args.get('edit') == '1' or (current_user.is_authenticated and plan is None)
    return render_template('safety_plan.html', title="Safety Plan", plan=plan, form=form, editing=editing)

# ── What Helped Me / Coping Ecosystem ──────────────────
COPING_IDEAS = {
    "😢 Sad": ["Text or call someone you trust", "Listen to a comforting song", "Write down three small good things", "Take a warm shower"],
    "😰 Anxious": ["Box breathing for 2 minutes", "5-4-3-2-1 grounding: name things you can see, hear, feel", "Go for a short walk", "Splash cold water on your face"],
    "😠 Angry": ["Move your body: a brisk walk or stretching", "Write it out, then tear it up", "Squeeze an ice cube or a stress ball", "Step away for 10 minutes before replying"],
    "😊 Happy": ["Note what made today good in your journal", "Share the moment with a friend", "Save a photo of today"],
    "😌 Calm": ["Gentle yoga or stretching", "Read a few pages of a book", "Make a cup of tea and sit by a window"],
}

def coping_stats(user_id):
    """Average 'how much it helped' per activity, overall and per mood."""
    logs = CopingLog.query.filter_by(user_id=user_id).all()
    overall, by_mood = {}, {}
    for log in logs:
        key = log.activity.strip()
        name = key.lower()
        for bucket in (overall, by_mood.setdefault(log.mood_before, {})):
            entry = bucket.setdefault(name, {'activity': key, 'total': 0, 'count': 0})
            entry['total'] += log.helped_rating or 0
            entry['count'] += 1

    def ranked(bucket):
        rows = [dict(e, avg=round(e['total'] / e['count'], 1)) for e in bucket.values()]
        return sorted(rows, key=lambda r: (-r['avg'], -r['count']))

    return ranked(overall), {mood: ranked(b) for mood, b in by_mood.items()}

@app.route('/what-helped', methods=['GET', 'POST'])
@login_required
def what_helped():
    form = CopingLogForm()
    if form.validate_on_submit():
        db.session.add(CopingLog(user_id=current_user.id, activity=form.activity.data.strip(),
                                 mood_before=form.mood_before.data, helped_rating=form.helped_rating.data))
        db.session.commit()
        flash("Logged. Future you will thank you for remembering what works.", "success")
        return redirect(url_for('what_helped', mood=form.mood_before.data))

    moods = [m for m, _ in MOOD_CHOICES]
    selected_mood = request.args.get('mood') if request.args.get('mood') in moods else moods[0]
    overall, by_mood = coping_stats(current_user.id)
    # Suggest what has helped this user before in this mood (rated 3+), then fill with general ideas.
    mine = [r for r in by_mood.get(selected_mood, []) if r['avg'] >= 3][:3]
    known = {r['activity'].lower() for r in mine}
    ideas = [i for i in COPING_IDEAS.get(selected_mood, []) if i.lower() not in known]
    recent = CopingLog.query.filter_by(user_id=current_user.id).order_by(CopingLog.created_at.desc()).limit(10).all()
    return render_template('what_helped.html', title="What Helped Me", form=form, moods=moods,
                           selected_mood=selected_mood, mine=mine, ideas=ideas,
                           overall=overall[:6], recent=recent)

@app.route('/what-helped/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_coping_log(log_id):
    log = CopingLog.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for('what_helped'))
    db.session.delete(log)
    db.session.commit()
    flash("Deleted.", "success")
    return redirect(url_for('what_helped'))

# ── Anonymous Support Pool ("Kind Notes") ──────────────
STARTER_NOTES = [
    "Whoever is reading this: you have survived every hard day so far. That counts for a lot.",
    "It's okay to rest. You don't have to earn it.",
    "Someone out there is glad you exist, even if they haven't said it today.",
    "Small steps are still steps. Be proud of the one you took today.",
    "Your feelings are valid, and they won't last forever. Better days do come.",
]
# Notes are anonymous, so they must not carry contact details or links, and
# obviously hurtful notes are held back instead of being shown to someone vulnerable.
_NOTE_BLOCK_RE = re.compile(
    r"https?://|www\.|\S+@\S+\.\S+|\+?\d[\d\s().-]{7,}\d"
    r"|\b(kill yourself|kys|die|worthless|loser|idiot|stupid|ugly|hate you)\b", re.I)

def note_is_safe(text):
    return not _NOTE_BLOCK_RE.search(text)

@app.route('/kind-notes', methods=['GET', 'POST'])
@login_required
def kind_notes():
    if SupportMessage.query.count() == 0:
        db.session.add_all(SupportMessage(content=t, approved=True) for t in STARTER_NOTES)
        db.session.commit()

    form = KindNoteForm()
    if form.validate_on_submit():
        text = form.content.data.strip()
        # No user id is stored with the note: there is no way to trace it back.
        db.session.add(SupportMessage(content=text, approved=note_is_safe(text)))
        db.session.commit()
        if note_is_safe(text):
            flash("Thank you. Your note is now in the pool for someone who needs it. 💗", "success")
        else:
            flash("Thanks! Your note is waiting for review because it contains a link, contact details "
                  "or words that might hurt someone.", "info")
        return redirect(url_for('kind_notes'))

    approved = SupportMessage.query.filter_by(approved=True)
    note = approved.offset(random.randrange(approved.count())).first() if approved.count() else None
    return render_template('kind_notes.html', title="Kind Notes", form=form, note=note)

# ── Letters to Future Me ───────────────────────────────
def deliver_due_letters(user_id):
    """Mark letters whose date has arrived as delivered. Returns how many just arrived.
    Letters are delivered inside the app; email delivery can be added once mail is set up."""
    due = FutureLetter.query.filter(FutureLetter.user_id == user_id, FutureLetter.delivered.is_(False),
                                    FutureLetter.deliver_at <= datetime.utcnow()).all()
    for letter in due:
        letter.delivered = True
    if due:
        db.session.commit()
    return len(due)

@app.route('/letters', methods=['GET', 'POST'])
@login_required
def letters():
    form = FutureLetterForm()
    if request.method == 'GET' and not form.deliver_on.data:
        form.deliver_on.data = date.today() + timedelta(days=30)
    if form.validate_on_submit():
        if form.deliver_on.data <= date.today():
            form.deliver_on.errors.append("Pick a date after today.")
        else:
            deliver_at = datetime.combine(form.deliver_on.data, datetime.min.time())
            db.session.add(FutureLetter(user_id=current_user.id, content=form.content.data, deliver_at=deliver_at))
            db.session.commit()
            flash(f"Sealed! It will open on {form.deliver_on.data.strftime('%d %b %Y')}.", "success")
            return redirect(url_for('letters'))

    arrived = deliver_due_letters(current_user.id)
    if arrived:
        flash(f"📬 {arrived} letter{'s' if arrived > 1 else ''} from past you just arrived!", "success")
    opened = FutureLetter.query.filter_by(user_id=current_user.id, delivered=True).order_by(FutureLetter.deliver_at.desc()).all()
    sealed = FutureLetter.query.filter_by(user_id=current_user.id, delivered=False).order_by(FutureLetter.deliver_at).all()
    return render_template('letters.html', title="Letters to Future Me", form=form, opened=opened, sealed=sealed,
                           min_date=(date.today() + timedelta(days=1)).isoformat())

@app.route('/letters/<int:letter_id>/delete', methods=['POST'])
@login_required
def delete_letter(letter_id):
    letter = FutureLetter.query.get_or_404(letter_id)
    if letter.user_id != current_user.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for('letters'))
    db.session.delete(letter)
    db.session.commit()
    flash("Letter deleted.", "success")
    return redirect(url_for('letters'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

