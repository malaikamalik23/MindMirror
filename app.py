from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, JournalEntry, DailyReflection, MoodLog
from forms import SignupForm, LoginForm, DailyReflectionForm
from dotenv import load_dotenv
from flask_migrate import Migrate
from transformers import AutoTokenizer, AutoModel
from datetime import datetime
import matplotlib.pyplot as plt
import io
import os
import base64

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
model = AutoModel.from_pretrained("bert-base-uncased")

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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("No account found with that email.", "danger")
            return redirect(url_for('forgot_password'))

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('forgot_password'))

        user.set_password(new_password)
        db.session.commit()
        flash("Password updated. Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/journal', methods=['GET', 'POST'])
@login_required
def journal():
    if request.method == 'POST':
        content = request.form['content']
        mood = request.form['mood']
        try:
            input_ids = tokenizer.encode(content + tokenizer.eos_token, return_tensors="pt")
            chat_history_ids = model.generate(
                input_ids,
                max_length=1000,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=True,
                top_k=50,
                top_p=0.95
            )
            ai_response = tokenizer.decode(chat_history_ids[:, input_ids.shape[-1]:][0], skip_special_tokens=True)
        except Exception:
            ai_response = "AI reflection unavailable."

        entry = JournalEntry(content=content, mood=mood, user_id=current_user.id, response=ai_response)
        db.session.add(entry)
        db.session.commit()
        flash("Journal entry saved!", "success")
        return redirect(url_for('journal'))

    page = request.args.get('page', 1, type=int)
    filter_mood = request.args.get('filter_mood')
    per_page = 5
    if filter_mood:
        entries = JournalEntry.query.filter_by(user_id=current_user.id, mood=filter_mood).order_by(JournalEntry.timestamp.desc()).paginate(page=page, per_page=per_page)
    else:
        entries = JournalEntry.query.filter_by(user_id=current_user.id).order_by(JournalEntry.timestamp.desc()).paginate(page=page, per_page=per_page)

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

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user_input = request.json.get("message", "").lower().strip()

        if not user_input:
            return jsonify({'reply': "Please say something so I can help!"})

        support_responses = {
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

        if user_input in support_responses:
            return jsonify({'reply': support_responses[user_input]})
        else:
            return jsonify({'reply': "❌ This message is not in the dataset. Please try again or rephrase."})

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

@app.route('/mood-tracker', methods=['GET', 'POST'])
@login_required
def mood_tracker():
    if request.method == 'POST':
        mood = request.form.get('mood')
        emotions = request.form.getlist('emotions')
        emotions_str = ', '.join(emotions)
        log = MoodLog(mood=mood, emotions=emotions_str, user_id=current_user.id)
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
    return render_template('new_session.html')  # Make sure new_session.html exists

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

