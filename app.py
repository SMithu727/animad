import html
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, abort
from functools import wraps
import os
from werkzeug.utils import secure_filename
import requests
from flask_login import login_user, logout_user, login_required, current_user
from forms import LoginForm, SignupForm, AdminAnimeForm, ProfileForm, CommentForm
from models import User, Anime, Episode, Comment, CommentVote, WatchHistory
from extensions import db, cache
from google.cloud import translate_v2 as translate
from google.oauth2 import service_account
from dateparser import parse  # For date translation
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta

# Initialize the Flask Blueprint
bp = Blueprint('main', __name__)

# Load the JSON key file for Google Cloud Translation API
credentials = service_account.Credentials.from_service_account_file(
    "C:/Users/xgaem/Downloads/Animad - Copy/credentials/innate-sunset-451719-c5-08a2d0e73f47.json"
)

# Initialize Google Cloud Translation client
translate_client = translate.Client(credentials=credentials)

# Translation dictionaries
STATUS_TRANSLATIONS = {
    "Finished Airing": "مكتمل",
    "Currently Airing": "يعرض الآن",
    "Not yet aired": "لم يعرض بعد",
    "Cancelled": "ملغي"
}

GENRE_TRANSLATIONS = {
    "Action": "أكشن",
    "Adventure": "مغامرات",
    "Avant Garde": "طليعية",
    "Award Winning": "حائز على جوائز",
    "Comedy": "كوميديا",
    "Drama": "دراما",
    "Fantasy": "فانتازيا",
    "Gourmet": "ذواقة",
    "Horror": "رعب",
    "Mystery": "غموض",
    "Romance": "رومانسية",
    "Sci-Fi": "خيال علمي",
    "Slice of Life": "شريحة من الحياة",
    "Sports": "رياضة",
    "Supernatural": "خوارق",
    "Suspense": "تشويق",
}

RATING_TRANSLATIONS = {
    "R - 17+ (violence & profanity)": "R - 17+ (عنف ولغة صريحة)",
    "PG-13 - Teens 13 or older": "PG-13 - المراهقون 13 فما فوق",
    "R+ - Mild Nudity": "R+ - عري جزئي",
    "G - All Ages": "G - جميع الأعمار"
}

TYPE_TRANSLATIONS = {
    "TV": "مسلسل تلفزيوني",
    "Movie": "فيلم",
    "OVA": "أوفا",
    "ONA": "أونا",
    "Special": "خاص"
}

PREMIERED_TRANSLATIONS = {
    "summer": "الصيف",
    "winter": "الشتاء",
    "fall": "الخريف",
    "spring": "الربيع"
}

# Helper functions
def translate_duration(duration):
    if "per ep" in duration:
        return duration.replace("min", "دقيقة").replace("per ep", "لكل حلقة")
    if "hr" in duration and "min" in duration:
        return duration.replace("hr", "ساعة").replace("min", "دقيقة")
    if "hr" in duration:
        return duration.replace("hr", "ساعة")
    return duration.replace("min", "دقيقة")

def translate_aired(aired):
    if not aired:
        return ""
    parts = aired.split(" to ")
    translated_parts = []
    for part in parts:
        if part == "?":
            translated_parts.append("؟")
            continue
        try:
            date_obj = parse(part)
            if date_obj:
                formatted_date = date_obj.strftime("%d %B %Y").lstrip("0")
                month_translations = {
                    'January': 'يناير', 'February': 'فبراير', 'March': 'مارس',
                    'April': 'أبريل', 'May': 'مايو', 'June': 'يونيو',
                    'July': 'يوليو', 'August': 'أغسطس', 'September': 'سبتمبر',
                    'October': 'أكتوبر', 'November': 'نوفمبر', 'December': 'ديسمبر'
                }
                for eng, ar in month_translations.items():
                    formatted_date = formatted_date.replace(eng, ar)
                translated_parts.append(formatted_date)
            else:
                translated_parts.append(part)
        except:
            translated_parts.append(part)
    return " إلى ".join(translated_parts)

def translate_text(text, source_lang='en', target_lang='ar'):
    if not text:
        return text
    try:
        result = translate_client.translate(text, target_language=target_lang)
        translated_text = result['translatedText']
        # Decode HTML entities in the translated text
        decoded_text = html.unescape(translated_text)
        return decoded_text
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Fallback to the original text

# Route to translate all anime
@bp.route('/translate_all_anime', methods=['GET', 'POST'])
@login_required
def translate_all_anime():
    # Check if user is admin
    if current_user.role != 'admin':
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('main.index'))

    # Handle GET request (confirmation page)
    if request.method == 'GET':
        return render_template('admin/confirm_translation.html')

    # Handle POST request (actual translation)
    all_anime = Anime.query.all()
    batch_size = 10
    total_anime = len(all_anime)
    translated_count = 0
    errors = []

    try:
        for i, anime in enumerate(all_anime):
            try:
                # Translate status
                if anime.status and not anime.status_ar:
                    anime.status_ar = STATUS_TRANSLATIONS.get(anime.status, translate_text(anime.status, target_lang='ar'))

                # Translate genres
                if anime.genres and not anime.genres_ar:
                    translated_genres = []
                    for genre in anime.genres.split(', '):
                        translated = GENRE_TRANSLATIONS.get(genre.strip(), genre.strip())
                        translated_genres.append(translated)
                    anime.genres_ar = ', '.join(translated_genres)

                # Translate rating
                if anime.rating and not anime.rating_ar:
                    anime.rating_ar = RATING_TRANSLATIONS.get(anime.rating, translate_text(anime.rating, target_lang='ar'))

                # Translate type
                if anime.type and not anime.type_ar:
                    anime.type_ar = TYPE_TRANSLATIONS.get(anime.type, translate_text(anime.type, target_lang='ar'))

                # Translate duration
                if anime.duration and not anime.duration_ar:
                    anime.duration_ar = translate_duration(anime.duration)

                # Translate aired dates
                if anime.aired and not anime.aired_ar:
                    anime.aired_ar = translate_aired(anime.aired)

                # Translate premiered (seasons)
                if anime.premiered and not anime.premiered_ar:
                    anime.premiered_ar = PREMIERED_TRANSLATIONS.get(anime.premiered, translate_text(anime.premiered, target_lang='ar'))

                # Translate description with API (chunked)
                if not anime.description_ar and anime.description:
                    chunks = [anime.description[i:i+450] for i in range(0, len(anime.description), 450)]
                    translated_chunks = []
                    for chunk in chunks:
                        translated = translate_text(chunk, target_lang='ar')
                        translated_chunks.append(translated)
                    anime.description_ar = ' '.join(translated_chunks)

                translated_count += 1

            except Exception as e:
                errors.append(f"Anime ID {anime.id}: {str(e)}")
                continue

            # Commit in batches
            if i % batch_size == 0:
                db.session.commit()

        # Final commit
        db.session.commit()

        # Prepare success message
        success_message = f"Translation completed! {translated_count}/{total_anime} anime translated successfully."
        if errors:
            success_message += f" {len(errors)} errors occurred."

        flash(success_message, "success" if not errors else "warning")

        # Log errors if any
        if errors:
            current_app.logger.error(f"Translation errors: {errors}")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Translation failed: {str(e)}")
        flash(f"Translation failed: {str(e)}", "danger")
        return redirect(url_for('main.admin_dashboard'))

    return redirect(url_for('main.admin_dashboard'))


# Other routes
@bp.route('/genre/<genre_name>')
def genre(genre_name):
    # Find the English genre name from Arabic translation
    reverse_genre_translations = {v: k for k, v in GENRE_TRANSLATIONS.items()}
    english_genre = reverse_genre_translations.get(genre_name, genre_name)
    
    # Get page number from query parameters
    page = request.args.get('page', 1, type=int)
    
    # Search for anime with this genre (case-insensitive)
    genre_filter = f"%{english_genre}%"
    anime_list = Anime.query.filter(Anime.genres.ilike(genre_filter)).paginate(page=page, per_page=20, error_out=False)
    
    # Get Arabic genre name
    arabic_genre = GENRE_TRANSLATIONS.get(english_genre, english_genre)
    
    return render_template('genre.html', 
                         anime_list=anime_list,
                         genre_name=arabic_genre,
                         GENRE_TRANSLATIONS=GENRE_TRANSLATIONS)
    
@bp.route('/')
def index():
    spotlights = Anime.query.order_by(db.func.random()).limit(5).all()
    trending = Anime.query.order_by(db.func.random()).limit(8).all()
    latest_page = request.args.get('latest_page', 1, type=int)
    latest_episodes = Episode.query.order_by(Episode.id.desc()).paginate(page=latest_page, per_page=20, error_out=False)

    # Add this AJAX check
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template(
            '_common_content.html',
            trending=trending,
            latest_episodes=latest_episodes,
            GENRE_TRANSLATIONS=GENRE_TRANSLATIONS
        )
    
    return render_template(
        'index.html',
        spotlights=spotlights,
        trending=trending,
        latest_episodes=latest_episodes,
        GENRE_TRANSLATIONS=GENRE_TRANSLATIONS
    )

@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.verify_password(form.password.data):  # Use verify_password
            if not user.is_active:
                flash("This account has been suspended", "danger")
                return redirect(url_for('main.login'))
            login_user(user)
            flash("تم تسجيل الدخول بنجاح!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash("البريد الإلكتروني أو كلمة المرور غير صحيحة.", "danger")
    return render_template('login.html', form=form)

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        # Check if the email is already registered
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash("البريد الإلكتروني مسجل مسبقاً. يرجى تسجيل الدخول.", "danger")
        else:
            # Create new user with hashed password
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data  # This will trigger the @password.setter
            )
            db.session.add(new_user)
            db.session.commit()
            flash("تم إنشاء الحساب بنجاح! يرجى تسجيل الدخول.", "success")
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
    
    # Get watch history and comments
    watch_history = WatchHistory.query.filter_by(user_id=current_user.id)\
                                      .order_by(WatchHistory.timestamp.desc())\
                                      .limit(10).all()
    user_comments = Comment.query.filter_by(user_id=current_user.id)\
                                 .order_by(Comment.created_at.desc())\
                                 .limit(10).all()

    if form.validate_on_submit():
        # Update username and email
        current_user.username = form.username.data
        current_user.email = form.email.data
        # Update password if provided (hashed automatically)
        if form.password.data:
            current_user.password = form.password.data  # This will trigger the @password.setter
        # Handle file upload if a new picture is provided
        if form.picture.data:
            filename = secure_filename(form.picture.data.filename)
            picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            form.picture.data.save(picture_path)
            current_user.profile_picture = filename
        db.session.commit()
        flash("تم تحديث الملف الشخصي بنجاح!", "success")
        return redirect(url_for('main.profile'))
    
    return render_template(
        "profile.html",
        form=form,
        watch_history=watch_history,
        user_comments=user_comments
    )

@bp.route('/watch/<anime_title>', methods=['GET', 'POST'])
def watch(anime_title):
    formatted_title = anime_title.replace("_", " ")
    anime = Anime.query.filter_by(title=formatted_title).first_or_404()
    ep_number = request.args.get('ep', 1, type=int)
    selected_episode = Episode.query.filter_by(anime_id=anime.id, episode_number=ep_number).first()
    
    # Record watch history if user is authenticated
    if current_user.is_authenticated:
        existing_entry = WatchHistory.query.filter_by(
            user_id=current_user.id,
            anime_id=anime.id,
            episode_number=ep_number
        ).first()

        if not existing_entry:
            watch_entry = WatchHistory(
                user_id=current_user.id,
                anime_id=anime.id,
                episode_number=ep_number
            )
            db.session.add(watch_entry)
        else:
            existing_entry.timestamp = db.func.now()
        
        db.session.commit()

    comment_form = CommentForm()
    
    if comment_form.validate_on_submit():
        if current_user.is_authenticated:
            parent_id = comment_form.parent_id.data if comment_form.parent_id.data else None
            new_comment = Comment(
                user_id=current_user.id,
                anime_id=anime.id,
                content=comment_form.content.data,
                parent_id=parent_id
            )
            db.session.add(new_comment)
            db.session.commit()
            flash("تم إضافة التعليق!", "success")
            return redirect(url_for('main.watch', anime_title=anime_title, ep=ep_number))
        else:
            flash("يجب تسجيل الدخول للتعليق.", "danger")
            return redirect(url_for('main.login'))
    
    # Get only top-level comments (those without a parent)
    comments = Comment.query.filter_by(anime_id=anime.id, parent_id=None)\
                              .order_by(Comment.created_at.desc()).all()

    spotlights = Anime.query.order_by(db.func.random()).limit(5).all()
    trending = Anime.query.order_by(db.func.random()).limit(8).all()
    latest_page = request.args.get('latest_page', 1, type=int)
    latest_episodes = Episode.query.order_by(Episode.id.desc()).paginate(page=latest_page, per_page=40, error_out=False)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template(
            '_common_content.html',
            trending=trending,
            latest_episodes=latest_episodes,
            GENRE_TRANSLATIONS=GENRE_TRANSLATIONS  # Pass GENRE_TRANSLATIONS here
        )
    
    return render_template(
        "watch.html",
        anime=anime,
        spotlights=spotlights,
        trending=trending,
        selected_episode=selected_episode,
        latest_episodes=latest_episodes,
        comment_form=comment_form,
        comments=comments,
        GENRE_TRANSLATIONS=GENRE_TRANSLATIONS  # Pass GENRE_TRANSLATIONS here
    )
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

@bp.route('/anime')
def all_anime():
    # Get all anime sorted by title (or use any other ordering/pagination as needed)
    anime_list = Anime.query.order_by(Anime.title).all()
    return render_template("anime_list.html", anime_list=anime_list)

@bp.route('/news')
def news():
    return render_template('news.html')

@bp.route('/search')
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])  # Return empty list if no query
    
    search_term = f"%{query}%"
    # Search in title, japanese_title, or synonyms
    results = Anime.query.filter(
        (Anime.title.ilike(search_term)) |
        (Anime.japanese_title.ilike(search_term)) |
        (Anime.synonyms.ilike(search_term))
    ).order_by(Anime.title).limit(10).all()  # Limit results to 10 for performance
    
    # Format results as a list of dictionaries
    results_data = [{
        "id": anime.id,
        "title": anime.title,
        "japanese_title": anime.japanese_title,
        "poster_image": anime.poster_image,
        "url": url_for('main.watch', anime_title=anime.title.replace(" ", "_"))
    } for anime in results]
    
    return jsonify(results_data)

# ---------------------- New Endpoints for Comment Voting ---------------------- #

@bp.route('/like_comment', methods=['POST'])
@login_required
def like_comment():
    data = request.get_json()
    comment_id = data.get('comment_id')
    if not comment_id:
        return jsonify({"error": "No comment id provided"}), 400
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    # Check if the user has already voted on this comment.
    vote = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    if vote:
        if vote.vote == 1:
            # Already liked, so do nothing.
            return jsonify({"likes": comment.likes, "dislikes": comment.dislikes}), 200
        else:
            # Change vote from dislike to like.
            vote.vote = 1
            comment.likes += 1
            comment.dislikes -= 1
    else:
        # New like vote.
        vote = CommentVote(user_id=current_user.id, comment_id=comment_id, vote=1)
        db.session.add(vote)
        comment.likes += 1

    db.session.commit()
    return jsonify({"likes": comment.likes, "dislikes": comment.dislikes}), 200

@bp.route('/dislike_comment', methods=['POST'])
@login_required
def dislike_comment():
    data = request.get_json()
    comment_id = data.get('comment_id')
    if not comment_id:
        return jsonify({"error": "No comment id provided"}), 400
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"error": "Comment not found"}), 404

    vote = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()
    if vote:
        if vote.vote == -1:
            return jsonify({"likes": comment.likes, "dislikes": comment.dislikes}), 200
        else:
            vote.vote = -1
            comment.dislikes += 1
            comment.likes -= 1
    else:
        vote = CommentVote(user_id=current_user.id, comment_id=comment_id, vote=-1)
        db.session.add(vote)
        comment.dislikes += 1

    db.session.commit()
    return jsonify({"likes": comment.likes, "dislikes": comment.dislikes}), 200

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Add this to app.py after creating the Flask app instance (in extensions.py or app.py)
@bp.app_template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ""
    return value.strftime(format)

@bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Basic stats
    stats = {
        'total_users': User.query.count(),
        'total_anime': Anime.query.count(),
        'total_episodes': Episode.query.count(),
        'total_comments': Comment.query.count(),
    }

    # Recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_anime = Anime.query.order_by(Anime.created_at.desc()).limit(5).all()

    # User Activity Chart Data (Last 6 months)
    months = []
    user_counts = []
    for i in range(5, -1, -1):
        month = datetime.now() - relativedelta(months=i)
        start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        
        count = User.query.filter(
            User.created_at >= start,
            User.created_at <= end
        ).count()
        
        months.append(start.strftime("%b %Y"))
        user_counts.append(count)

    # Content Distribution Data
    content_data = {
        'anime': stats['total_anime'],
        'episodes': stats['total_episodes'],
        'comments': stats['total_comments']
    }

    # Storage calculation (example: calculate uploads folder size)
    uploads_path = os.path.join(current_app.root_path, 'static/uploads')
    total_storage = round(sum(f.stat().st_size for f in Path(uploads_path).glob('**/*') if f.is_file()) / (1024**3), 2)  # in GB

    # Memory usage
    memory = psutil.virtual_memory()
    memory_usage = round(memory.percent, 1)

    # Uptime calculation (example)
    start_time = datetime.now() - timedelta(days=2, hours=5, minutes=30)
    uptime = datetime.now() - start_time
    uptime_str = str(uptime).split('.')[0]  # Remove microseconds

    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_users=recent_users,
                         recent_anime=recent_anime,
                         chart_labels=months,
                         user_data=user_counts,
                         content_data=content_data,
                         storage_usage=total_storage,
                         memory_usage=memory_usage,
                         uptime=uptime_str)

# Anime Management
@bp.route('/admin/animes')
@login_required
@admin_required
def manage_animes():
    page = request.args.get('page', 1, type=int)
    anime_list = Anime.query.order_by(Anime.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/animes.html', anime_list=anime_list)

@bp.route('/admin/delete_anime/<int:anime_id>', methods=['POST'])
@login_required
@admin_required
def delete_anime(anime_id):
    anime = Anime.query.get_or_404(anime_id)
    db.session.delete(anime)
    db.session.commit()
    flash('تم حذف الأنمي بنجاح', 'success')
    return redirect(url_for('main.manage_animes'))

# Episode Management
@bp.route('/admin/episodes')
@login_required
@admin_required
def manage_episodes():
    page = request.args.get('page', 1, type=int)
    episodes = Episode.query.order_by(Episode.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/episodes.html', episodes=episodes)

@bp.route('/admin/delete_episode/<int:episode_id>', methods=['POST'])
@login_required
@admin_required
def delete_episode(episode_id):
    episode = Episode.query.get_or_404(episode_id)
    db.session.delete(episode)
    db.session.commit()
    flash('تم حذف الحلقة بنجاح', 'success')
    return redirect(url_for('main.manage_episodes'))

# Comment Management
@bp.route('/admin/comments')
@login_required
@admin_required
def manage_comments():
    page = request.args.get('page', 1, type=int)
    comments = Comment.query.order_by(Comment.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/comments.html', comments=comments)

@bp.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
@admin_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('تم حذف التعليق بنجاح', 'success')
    return redirect(url_for('main.manage_comments'))

# User Management
@bp.route('/admin/users')
@login_required
@admin_required
def manage_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/users.html', users=users)

@bp.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    flash(f'تم {"تفعيل" if user.is_active else "تعطيل"} الحساب بنجاح', 'success')
    return redirect(url_for('main.manage_users'))

@bp.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('تم حذف المستخدم بنجاح', 'success')
    return redirect(url_for('main.manage_users'))