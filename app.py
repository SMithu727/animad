# app.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, abort, session
from functools import wraps
import os
from werkzeug.utils import secure_filename
import requests
from flask_login import login_user, logout_user, login_required, current_user
from forms import LoginForm, SignupForm, AdminAnimeForm, ProfileForm, CommentForm, ResetPasswordRequestForm, ResetPasswordForm
from models import User, Anime, Episode, Comment, CommentVote, WatchHistory
from extensions import db, cache, csrf
from google.cloud import translate_v2 as translate
from google.oauth2 import service_account
from dateparser import parse  # For date translation
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
from flask_mail import Mail, Message
from flask_wtf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer
import secrets
import base64
import logging
import html

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Initialize the Flask Blueprint
bp = Blueprint('main', __name__)

# Initialize the Mail object
mail = Mail()

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

# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Generate email tokens
def generate_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-confirm-salt')

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-confirm-salt', max_age=expiration)
    except:
        return False
    return email

# Send verification email using an HTML template
def send_verification_email(user):
    token = generate_token(user.email)
    msg = Message("تأكيد البريد الإلكتروني - آنيماد", recipients=[user.email])
    msg.html = render_template('email/verify_email.html', token=token)
    msg.body = f"To verify your email, visit: {url_for('main.verify_email', token=token, _external=True)}\n\nIf you didn't request this, ignore this email."
    mail.send(msg)

# Send reset password email using an HTML template
def send_reset_password_email(user):
    token = user.generate_reset_token()
    msg = Message('إعادة تعيين كلمة المرور - آنيماد', recipients=[user.email])
    msg.html = render_template('email/reset_password.html', token=token)
    msg.body = f"To reset your password, visit: {url_for('main.reset_password', token=token, _external=True)}\n\nIf you didn't request this, ignore this email."
    mail.send(msg)

# Routes
@bp.route('/verify/<token>')
def verify_email(token):
    if current_user.is_authenticated and current_user.email_verified:
        return redirect(url_for('main.index'))
    
    email = confirm_token(token)
    if not email:
        flash('رابط التفعيل غير صالح أو منتهي الصلاحية', 'danger')
        return redirect(url_for('main.profile'))

    user = User.query.filter_by(email=email).first_or_404()
    if user.email_verified:
        flash('البريد الإلكتروني مفعّل بالفعل', 'info')
    else:
        user.email_verified = True
        db.session.commit()
        flash('تم تفعيل البريد الإلكتروني بنجاح!', 'success')
    
    return redirect(url_for('main.profile'))

@bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = ResetPasswordRequestForm()
    
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            # Use the helper function to send an HTML email
            send_reset_password_email(user)
            flash('Check your email for reset instructions', 'info')
            return redirect(url_for('main.login'))
        else:
            flash('Email not found', 'danger')
    
    return render_template('reset_password_request.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('main.reset_password_request'))
    
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        password = form.password.data
        user.password = password
        user.password_reset_token = None
        user.token_expiration = None
        db.session.commit()
        flash('Password updated successfully!', 'success')
        return redirect(url_for('main.login'))
    
    return render_template('reset_password.html', form=form, token=token)

@bp.route('/resend-verification', methods=['GET'])
@login_required
def resend_verification():
    if current_user.email_verified:
        flash('البريد الإلكتروني مفعّل بالفعل', 'info')
        return redirect(url_for('main.profile'))

    token = generate_token(current_user.email)
    msg = Message('تفعيل البريد الإلكتروني - آنيماد', recipients=[current_user.email])
    msg.html = render_template('email/verify_email.html', token=token)
    msg.body = f"لتفعيل بريدك الإلكتروني، قم بزيارة الرابط التالي:\n{url_for('main.verify_email', token=token, _external=True)}\n\nإذا لم تطلب هذا، يمكنك تجاهل هذه الرسالة."
    mail.send(msg)

    flash('تم إرسال رابط التفعيل إلى بريدك الإلكتروني', 'success')
    return redirect(url_for('main.profile'))

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

# Replace AniList routes with MAL integration

def refresh_mal_token(user):
    token_url = 'https://myanimelist.net/v1/oauth2/token'
    auth_header = base64.b64encode(
        f"{current_app.config['MAL_CLIENT_ID']}:{current_app.config['MAL_CLIENT_SECRET']}".encode()
    ).decode()
    
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': user.mal_refresh_token
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        user.mal_access_token = token_data['access_token']
        user.mal_refresh_token = token_data['refresh_token']
        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Token refresh failed: {str(e)}")
        return False

def generate_pkce():
    code_verifier = secrets.token_urlsafe(64)[:128]  # 43-128 chars
    code_challenge = code_verifier  # 'plain' method
    return code_verifier, code_challenge

@bp.route('/link_mal')
@login_required
def link_mal():
    # Generate PKCE values
    code_verifier, code_challenge = generate_pkce()
    
    # Store code_verifier and state in session
    session['mal_code_verifier'] = code_verifier
    session['mal_auth_state'] = secrets.token_urlsafe(16)
    session.modified = True  # Ensure session is saved
    
    # Build authorization URL
    mal_auth_url = (
    "https://myanimelist.net/v1/oauth2/authorize"
    f"?response_type=code"
    f"&client_id={current_app.config['MAL_CLIENT_ID']}"
    f"&state={session['mal_auth_state']}"
    f"&redirect_uri={current_app.config['MAL_REDIRECT_URI']}"
    f"&code_challenge={code_challenge}"
    "&code_challenge_method=plain"
    "&scope=read write"  # Request both read and write permissions
    )
    return redirect(mal_auth_url)

@bp.route('/unlink_mal')
@login_required
def unlink_mal():
    # Clear MAL-related fields from the user
    current_user.mal_access_token = None
    current_user.mal_refresh_token = None
    current_user.mal_user_id = None
    current_user.mal_username = None
    db.session.commit()
    
    flash('تم إلغاء ربط حساب MAL بنجاح', 'success')
    return redirect(url_for('main.profile'))

@bp.route('/mal_callback')
def mal_callback():
    # Verify state parameter
    state = request.args.get('state')
    if state != session.get('mal_auth_state'):
        flash('Authorization failed: State mismatch', 'danger')
        return redirect(url_for('main.profile'))
    
    code = request.args.get('code')
    if not code:
        flash('Authorization failed', 'danger')
        return redirect(url_for('main.profile'))
    
    # Retrieve stored code_verifier
    code_verifier = session.pop('mal_code_verifier', None)
    if not code_verifier:
        flash('Authorization session expired', 'danger')
        return redirect(url_for('main.profile'))
    
    # Exchange code for tokens
    token_url = 'https://myanimelist.net/v1/oauth2/token'
    auth_header = base64.b64encode(
        f"{current_app.config['MAL_CLIENT_ID']}:{current_app.config['MAL_CLIENT_SECRET']}".encode()
    ).decode()
    
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'client_id': current_app.config['MAL_CLIENT_ID'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': current_app.config['MAL_REDIRECT_URI'],
        'code_verifier': code_verifier
    }
    
    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()  # Will raise HTTPError for 4xx/5xx
        token_data = response.json()
        
        # Get MAL user info
        headers = {'Authorization': f'Bearer {token_data["access_token"]}'}
        user_response = requests.get(
            'https://api.myanimelist.net/v2/users/@me',
            headers=headers
        )
        user_response.raise_for_status()
        user_data = user_response.json()
        
        # Update user with MAL data
        current_user.mal_profile_pic = user_data.get('picture')
        current_user.mal_user_id = user_data.get('id')
        
        # Update user model
        current_user.mal_access_token = token_data['access_token']
        current_user.mal_refresh_token = token_data['refresh_token']
        current_user.mal_user_id = user_data['id']
        current_user.mal_username = user_data['name']
        db.session.commit()
        
        flash('MAL account linked successfully!', 'success')
    except requests.exceptions.HTTPError as e:
        current_app.logger.error(f"MAL HTTP error: {e.response.text}")
        flash('Failed to link MAL account: Invalid client credentials or code', 'danger')
    except Exception as e:
        current_app.logger.error(f"MAL error: {str(e)}", exc_info=True)
        flash('Failed to link MAL account: Unexpected error', 'danger')
    
    return redirect(url_for('main.profile'))

# app.py - Add update route
@csrf.exempt
@bp.route('/update_mal_status/<int:mal_id>', methods=['POST'])  # Change parameter name
@login_required
def update_mal_status(mal_id):
    try:
        if not current_user.mal_access_token:
            return jsonify({'success': False, 'error': 'Not linked to MAL'}), 401
        
        # Get anime by MAL ID instead of internal ID
        anime = Anime.query.filter_by(mal_id=mal_id).first_or_404()
        if not anime.mal_id:
            return jsonify({'success': False, 'error': 'Anime has no MAL ID'}), 400

        # Parse and validate input
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        status = data.get('status')
        episodes = int(data.get('episodes', 0))
        score = int(data.get('score', 0)) if data.get('score') else 0

        if score < 0 or score > 10:
            return jsonify({'success': False, 'error': 'Score must be between 0-10'}), 400

        # Prepare MAL API request
        mal_data = {
            'status': status,
            'num_watched_episodes': episodes,
            'score': score
        }

        headers = {'Authorization': f'Bearer {current_user.mal_access_token}'}
        
        # Make request to MAL API
        response = requests.put(
    f'https://api.myanimelist.net/v2/anime/{anime.mal_id}/my_list_status',
    headers=headers,
    data=mal_data
)
        response.raise_for_status()

        return jsonify({'success': True}), 200

    except requests.exceptions.HTTPError as e:
        # Handle MAL API errors
        error_message = f"MAL API error: {e.response.text}"
        current_app.logger.error(error_message)
        return jsonify({'success': False, 'error': error_message}), 502

    except Exception as e:
        # Handle other errors
        error_message = f"Unexpected error: {str(e)}"
        current_app.logger.error(error_message)
        return jsonify({'success': False, 'error': error_message}), 500

# app.py - Add new route
@bp.route('/get_mal_anime_list')
@login_required
def get_mal_anime_list():
    if not current_user.mal_access_token:
        return jsonify([])
    
    headers = {'Authorization': f'Bearer {current_user.mal_access_token}'}
    params = {'fields': 'list_status', 'limit': 1000}
    
    try:
        response = requests.get(
            'https://api.myanimelist.net/v2/users/@me/animelist',
            headers=headers,
            params=params
        )
        response.raise_for_status()
        return jsonify(response.json().get('data', []))
    except Exception as e:
        current_app.logger.error(f"MAL list error: {str(e)}")
        return jsonify([])
    
@bp.route('/admin/spotlight', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_spotlight():
    # Get search query
    search_query = request.args.get('q', '')
    
    # Get all anime (paginated)
    page = request.args.get('page', 1, type=int)
    query = Anime.query.order_by(Anime.title.asc())
    
    if search_query:
        query = query.filter(Anime.title.ilike(f'%{search_query}%'))
    
    anime_list = query.paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/spotlight.html', 
                         anime_list=anime_list,
                         search_query=search_query)

@bp.route('/')
def index():
    spotlights = Anime.query.filter_by(is_spotlight=True).order_by(db.func.random()).limit(5).all()
    best_anime = Anime.query.order_by(Anime.mal_score.desc()).limit(8).all()
    two_weeks_ago = datetime.utcnow() - timedelta(days=14)
    trending_anime_ids = db.session.query(
        WatchHistory.anime_id,
        db.func.count(WatchHistory.anime_id).label('views')
    ).filter(WatchHistory.timestamp >= two_weeks_ago
    ).group_by(WatchHistory.anime_id
    ).order_by(db.desc('views')
    ).limit(8).all()
    
    trending_anime_ids = [anime_id for (anime_id, views) in trending_anime_ids]
    trending = Anime.query.filter(Anime.id.in_(trending_anime_ids)).all()
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
        best_anime=best_anime,
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
    original_email = current_user.email

    # Get watch history and comments
    watch_history = WatchHistory.query.filter_by(user_id=current_user.id)\
                                      .order_by(WatchHistory.timestamp.desc())\
                                      .limit(10).all()
    user_comments = Comment.query.filter_by(user_id=current_user.id)\
                                 .order_by(Comment.created_at.desc())\
                                 .limit(10).all()

    if form.validate_on_submit():
        email_changed = form.email.data != original_email
        
        # Update username and email
        current_user.username = form.username.data
        current_user.email = form.email.data
        
        # If email changed, mark as unverified and send verification email
        if email_changed:
            current_user.email_verified = False
            send_verification_email(current_user)
            flash("تم تغيير البريد الإلكتروني. يرجى التحقق من بريدك الجديد لتفعيله.", "warning")

        # Update password if provided
        if form.password.data:
            current_user.password = form.password.data

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

    # Handle comments
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

    # Get top-level comments
    comments = Comment.query.filter_by(anime_id=anime.id, parent_id=None)\
                            .order_by(Comment.created_at.desc()).all()

    logger.debug("Entered /watch route")

    # Fetch MAL status if user is authenticated and linked to MAL
    existing_status = None
    existing_episodes = None
    existing_score = None

    if current_user.is_authenticated and current_user.mal_access_token:
        headers = {'Authorization': f'Bearer {current_user.mal_access_token}'}
        try:
            # Correct endpoint for single anime status
            response = requests.get(
                f'https://api.myanimelist.net/v2/anime/{anime.mal_id}/my_list_status',
                headers=headers
            )
            logger.debug(f"MAL API Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                mal_data = response.json()
                existing_status = mal_data.get('status')
                existing_episodes = mal_data.get('num_watched_episodes')
                existing_score = mal_data.get('score')
            else:
                logger.error(f"MAL API Error: {response.status_code}")
        except Exception as e:
            logger.error(f"Error: {str(e)}")

    # Random spotlights and trending anime
    spotlights = Anime.query.order_by(db.func.random()).limit(5).all()
    trending = Anime.query.order_by(db.func.random()).limit(8).all()
    latest_page = request.args.get('latest_page', 1, type=int)
    latest_episodes = Episode.query.order_by(Episode.id.desc()).paginate(page=latest_page, per_page=40, error_out=False)

    # Handle AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template(
            '_common_content.html',
            trending=trending,
            latest_episodes=latest_episodes,
            GENRE_TRANSLATIONS=GENRE_TRANSLATIONS
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
        existing_status=existing_status,
        existing_episodes=existing_episodes,
        existing_score=existing_score,
        GENRE_TRANSLATIONS=GENRE_TRANSLATIONS
    )
    
# app.py

# app.py
@bp.route('/toggle_spotlight/<int:anime_id>', methods=['POST'])
@login_required
@admin_required
def toggle_spotlight(anime_id):
    anime = Anime.query.get_or_404(anime_id)
    anime.is_spotlight = not anime.is_spotlight
    db.session.commit()
    
    # Stay on the same page after toggle
    page = request.args.get('page', 1)
    search_query = request.args.get('q', '')
    return redirect(url_for('main.manage_spotlight', 
                          page=page, 
                          q=search_query))

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
                    portrait_image=form.portrait_image.data,
                    mal_id=form.mal_id.data  # Store the MAL ID
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
    page = request.args.get('page', 1, type=int)  # Get the current page number from URL query parameters
    per_page = 30  # Number of anime per page (adjust as needed)
    
    # Query the database and paginate the results
    anime_list = Anime.query.order_by(Anime.title).paginate(page=page, per_page=per_page, error_out=False)
    
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

    comment = Comment.query.get_or_404(comment_id)
    vote = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()

    if vote:
        if vote.vote == 1:
            # User already liked, so remove the like
            db.session.delete(vote)
        else:
            # User previously disliked, change to like
            vote.vote = 1
    else:
        # New like
        vote = CommentVote(user_id=current_user.id, comment_id=comment_id, vote=1)
        db.session.add(vote)

    db.session.commit()

    # Recalculate likes and dislikes after commit
    comment.likes = CommentVote.query.filter_by(comment_id=comment_id, vote=1).count()
    comment.dislikes = CommentVote.query.filter_by(comment_id=comment_id, vote=-1).count()
    db.session.commit()

    return jsonify({
        "likes": comment.likes,
        "dislikes": comment.dislikes,
        "user_liked": comment.user_has_liked(current_user),
        "user_disliked": comment.user_has_disliked(current_user)
    }), 200

@bp.route('/dislike_comment', methods=['POST'])
@login_required
def dislike_comment():
    data = request.get_json()
    comment_id = data.get('comment_id')
    if not comment_id:
        return jsonify({"error": "No comment id provided"}), 400

    comment = Comment.query.get_or_404(comment_id)
    vote = CommentVote.query.filter_by(user_id=current_user.id, comment_id=comment_id).first()

    if vote:
        if vote.vote == -1:
            # User already disliked, so remove the dislike
            db.session.delete(vote)
        else:
            # User previously liked, change to dislike
            vote.vote = -1
    else:
        # New dislike
        vote = CommentVote(user_id=current_user.id, comment_id=comment_id, vote=-1)
        db.session.add(vote)

    db.session.commit()

    # Recalculate likes and dislikes after commit
    comment.likes = CommentVote.query.filter_by(comment_id=comment_id, vote=1).count()
    comment.dislikes = CommentVote.query.filter_by(comment_id=comment_id, vote=-1).count()
    db.session.commit()

    return jsonify({
        "likes": comment.likes,
        "dislikes": comment.dislikes,
        "user_liked": comment.user_has_liked(current_user),
        "user_disliked": comment.user_has_disliked(current_user)
    }), 200


# Admin route decorator should be defined before using it
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