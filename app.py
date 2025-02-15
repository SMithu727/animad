from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
import os
from werkzeug.utils import secure_filename
import requests
from flask_login import login_user, logout_user, login_required, current_user
from forms import LoginForm, SignupForm, AdminAnimeForm, ProfileForm
from models import User, Anime, Episode
from extensions import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    # Select 5 random anime for the spotlight slider
    spotlights = Anime.query.order_by(db.func.random()).limit(5).all()
    # Select 8 random anime for the trending section
    trending = Anime.query.order_by(db.func.random()).limit(8).all()
    # Get latest episodes with pagination (40 per page)
    latest_page = request.args.get('latest_page', 1, type=int)
    latest_episodes = Episode.query.order_by(Episode.id.desc()).paginate(page=latest_page, per_page=20, error_out=False)
    
    # If this is an AJAX request, return only the shared content partial
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('_common_content.html', trending=trending, latest_episodes=latest_episodes)
    
    return render_template('index.html', spotlights=spotlights, trending=trending, latest_episodes=latest_episodes)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        # For production, compare hashed passwords!
        if user and user.password == form.password.data:
            login_user(user)
            flash("Logged in successfully!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash("Invalid email or password.", "danger")
    return render_template('login.html', form=form)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # Check if the email is already registered
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash("Email already registered. Please log in.", "danger")
        else:
            # Create new user (in production, hash the password!)
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('main.login'))
    return render_template('signup.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for('main.index'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        # Update username and email
        current_user.username = form.username.data
        current_user.email = form.email.data
        # Update password if provided (remember to hash in production)
        if form.password.data:
            current_user.password = form.password.data
        # Handle file upload if a new picture is provided
        if form.picture.data:
            filename = secure_filename(form.picture.data.filename)
            picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            form.picture.data.save(picture_path)
            current_user.profile_picture = filename
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('main.profile'))
    return render_template("profile.html", form=form)

@bp.route('/watch/<anime_title>')
def watch(anime_title):
    formatted_title = anime_title.replace("_", " ")
    anime = Anime.query.filter_by(title=formatted_title).first_or_404()
    # Get episode number from query parameters; default to 1
    ep_number = request.args.get('ep', 1, type=int)
    selected_episode = Episode.query.filter_by(anime_id=anime.id, episode_number=ep_number).first()

    spotlights = Anime.query.order_by(db.func.random()).limit(5).all()
    trending = Anime.query.order_by(db.func.random()).limit(8).all()
    latest_page = request.args.get('latest_page', 1, type=int)
    latest_episodes = Episode.query.order_by(Episode.id.desc()).paginate(page=latest_page, per_page=40, error_out=False)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('_common_content.html', trending=trending, latest_episodes=latest_episodes)
    
    return render_template("watch.html", anime=anime, spotlights=spotlights, trending=trending, 
                           selected_episode=selected_episode, latest_episodes=latest_episodes)

@bp.route('/add_anime', methods=['GET', 'POST'])
@login_required
def add_anime():
    # Only allow access if the user is an admin or a mod
    if current_user.role not in ['admin', 'mod']:
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('main.index'))
    
    form = AdminAnimeForm()
    
    if request.method == 'POST':
        # If the "Fetch from MAL" button was pressed:
        if "fetch" in request.form:
            if not form.mal_id.data:
                flash("Please enter a MAL ID to fetch data.", "danger")
                return render_template("add_anime.html", form=form)
            mal_id = form.mal_id.data
            api_url = f"https://api.jikan.moe/v4/anime/{mal_id}"
            response = requests.get(api_url)
            if response.status_code == 200:
                data = response.json().get("data", {})
                if not data:
                    flash("No data found for that MAL ID.", "danger")
                else:
                    form.title.data = data.get("title")
                    form.rating.data = data.get("rating")
                    form.quality.data = "HD"  # default value
                    form.episode_count.data = str(data.get("episodes")) if data.get("episodes") is not None else "0"
                    form.anime_type.data = data.get("type")
                    form.duration.data = data.get("duration")
                    form.description.data = data.get("synopsis")
                    form.japanese_title.data = data.get("title_japanese")
                    synonyms_list = data.get("title_synonyms") or []
                    form.synonyms.data = ", ".join(synonyms_list) if synonyms_list else ""
                    form.aired.data = data.get("aired", {}).get("string")
                    form.premiered.data = data.get("season") or ""
                    form.status.data = data.get("status")
                    form.mal_score.data = str(data.get("score")) if data.get("score") is not None else "0.0"
                    form.genres.data = ", ".join([genre.get("name") for genre in data.get("genres", [])])
                    form.studios.data = ", ".join([studio.get("name") for studio in data.get("studios", [])])
                    form.producers.data = ", ".join([producer.get("name") for producer in data.get("producers", [])])
                    # Use the large image URL from the poster images
                    poster_img = data.get("images", {}).get("jpg", {}).get("large_image_url")
                    form.poster_image.data = poster_img
                    # For the portrait image, use the trailer's maximum image URL if available, otherwise fallback to poster image
                    trailer_img = data.get("trailer", {}).get("images", {}).get("maximum_image_url")
                    form.portrait_image.data = trailer_img if trailer_img else poster_img
                    flash("Data fetched successfully! You can edit the fields before submitting.", "success")
            else:
                flash("Error fetching data from MAL API.", "danger")
            return render_template("add_anime.html", form=form)
        
        # If the "Add Anime" button was pressed:
        elif "submit" in request.form:
            if form.validate():
                try:
                    episode_count = int(form.episode_count.data)
                except ValueError:
                    episode_count = 0
                try:
                    mal_score = float(form.mal_score.data)
                except ValueError:
                    mal_score = 0.0
                    
                new_anime = Anime(
                    title=form.title.data,
                    rating=form.rating.data,
                    quality=form.quality.data,
                    episode_count=episode_count,
                    type=form.anime_type.data,
                    duration=form.duration.data,
                    description=form.description.data,
                    japanese_title=form.japanese_title.data,
                    synonyms=form.synonyms.data,
                    aired=form.aired.data,
                    premiered=form.premiered.data,
                    status=form.status.data,
                    mal_score=mal_score,
                    genres=form.genres.data,
                    studios=form.studios.data,
                    producers=form.producers.data,
                    poster_image=form.poster_image.data,
                    portrait_image=form.portrait_image.data
                )
                db.session.add(new_anime)
                db.session.commit()
                flash("Anime added successfully!", "success")
                return redirect(url_for("main.add_anime"))
            else:
                flash("Please fix the errors in the form.", "danger")
    return render_template("add_anime.html", form=form)
