import html
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
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
    "Ecchi": "إيتشي",
    "Erotica": "إيروتيكا",
    "Hentai": "هنتاي"
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
@bp.route('/translate_all_anime', methods=['POST'])
@login_required
def translate_all_anime():
    if current_user.role != 'admin':
        flash("You do not have permission to access this page.", "danger")
        return redirect(url_for('main.index'))

    all_anime = Anime.query.all()
    batch_size = 10
    
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

        except Exception as e:
            print(f"Error translating anime ID {anime.id}: {str(e)}")
            continue

        if i % batch_size == 0:
            db.session.commit()

    db.session.commit()
    flash("Translation completed successfully!", "success")
    return redirect(url_for('main.index'))


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
    # Select 5 random anime for the spotlight slider
    spotlights = Anime.query.order_by(db.func.random()).limit(5).all()
    # Select 8 random anime for the trending section
    trending = Anime.query.order_by(db.func.random()).limit(8).all()
    # Get latest episodes with pagination (20 per page)
    latest_page = request.args.get('latest_page', 1, type=int)
    latest_episodes = Episode.query.order_by(Episode.id.desc()).paginate(page=latest_page, per_page=20, error_out=False)

    return render_template(
        'index.html',
        spotlights=spotlights,
        trending=trending,
        latest_episodes=latest_episodes,
        GENRE_TRANSLATIONS=GENRE_TRANSLATIONS  # Pass GENRE_TRANSLATIONS to the template
    )

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