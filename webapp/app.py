"""
Groove Gremlin Web Application
A web app for managing Spotify artist following, playlist randomization, concert discovery, and Instagram automation.
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import spotipy
import requests
from spotipy.oauth2 import SpotifyOAuth
import os
from datetime import datetime, timedelta
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Fix DATABASE_URL format for SQLAlchemy 2.0+ (postgres:// -> postgresql://)
database_url = os.getenv('DATABASE_URL', 'sqlite:///spotify_tools.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Template filters
@app.template_filter('tojsonfilter')
def tojson_filter(value):
    return json.dumps(value, indent=2)

@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to dict"""
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}

# Spotify OAuth configuration
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:5000/spotify/callback')


# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Spotify connection
    spotify_access_token = db.Column(db.Text)
    spotify_refresh_token = db.Column(db.Text)
    spotify_token_expires_at = db.Column(db.DateTime)
    spotify_user_id = db.Column(db.String(255))
    spotify_username = db.Column(db.String(255))
    
    # Instagram connection
    instagram_username = db.Column(db.String(255))
    instagram_password = db.Column(db.Text)  # Encrypted Instagram password for Apify runs
    instagram_session_id = db.Column(db.Text)  # Instagram session ID (more reliable than password)
    
    # Job history
    jobs = db.relationship('Job', backref='user', lazy=True)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)  # 'follow_artists', 'find_concerts', 'find_instagram', 'randomize_playlists'
    status = db.Column(db.String(50), default='pending')  # 'pending', 'running', 'completed', 'failed'
    input_data = db.Column(db.Text)  # JSON input
    output_data = db.Column(db.Text)  # JSON output
    progress_percent = db.Column(db.Integer, default=0)  # 0-100
    progress_message = db.Column(db.Text)  # Current status message
    execution_log = db.Column(db.Text)  # Detailed execution log for power users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Check Spotify connection
    spotify_connected = bool(current_user.spotify_access_token)
    
    return render_template('dashboard.html', 
                         spotify_connected=spotify_connected)


@app.route('/features')
@login_required
def features():
    """Features page with tabs for each feature"""
    tab = request.args.get('tab', 'follow_artists')
    spotify_connected = bool(current_user.spotify_access_token)
    
    # Get jobs for the active tab
    jobs = Job.query.filter_by(
        user_id=current_user.id,
        job_type=tab
    ).order_by(Job.created_at.desc()).limit(20).all()
    
    has_instagram_creds = bool(current_user.instagram_session_id or (current_user.instagram_username and current_user.instagram_password))
    
    return render_template('features.html',
                         has_instagram_credentials=has_instagram_creds,
                         active_tab=tab,
                         spotify_connected=spotify_connected,
                         jobs=jobs)


@app.route('/spotify/connect')
@login_required
def spotify_connect():
    """Initiate Spotify OAuth flow"""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        flash('Spotify credentials not configured. Please contact support.')
        return redirect(url_for('dashboard'))
    
    scope = "user-library-read user-follow-read user-follow-modify user-top-read playlist-read-private playlist-modify-private"
    
    try:
        auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=scope,
            cache_path=None  # We'll handle tokens ourselves
        )
        
        auth_url = auth_manager.get_authorize_url()
        session['spotify_state'] = auth_manager.state
        
        return redirect(auth_url)
    except Exception as e:
        import traceback
        app.logger.error(f'Spotify connect error: {str(e)}\n{traceback.format_exc()}')
        flash(f'Error initiating Spotify connection: {str(e)}')
        return redirect(url_for('dashboard'))


@app.route('/spotify/callback')
def spotify_callback():
    """Handle Spotify OAuth callback"""
    error = request.args.get('error')
    if error:
        flash(f'Spotify authorization error: {error}')
        return redirect(url_for('dashboard'))
    
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        flash('No authorization code received from Spotify.')
        return redirect(url_for('dashboard'))
    
    # Check if user is logged in
    if not current_user.is_authenticated:
        flash('Please log in first, then connect Spotify.')
        return redirect(url_for('login'))
    
    # Verify state (if stored in session)
    if 'spotify_state' in session and state != session.get('spotify_state'):
        flash('State mismatch. Please try again.')
        return redirect(url_for('dashboard'))
    
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        cache_path=None
    )
    
    try:
        token_info = auth_manager.get_access_token(code)
        
        if not token_info:
            flash('Failed to get access token from Spotify.')
            return redirect(url_for('dashboard'))
        
        # Store tokens in database
        current_user.spotify_access_token = token_info['access_token']
        current_user.spotify_refresh_token = token_info.get('refresh_token')
        if 'expires_at' in token_info:
            current_user.spotify_token_expires_at = datetime.fromtimestamp(token_info['expires_at'])
        
        # Get user info
        sp = spotipy.Spotify(auth=token_info['access_token'])
        spotify_user = sp.current_user()
        current_user.spotify_user_id = spotify_user['id']
        current_user.spotify_username = spotify_user.get('display_name') or spotify_user.get('id')
        
        db.session.commit()
        
        flash('Spotify account connected successfully!')
    except Exception as e:
        import traceback
        app.logger.error(f'Spotify connection error: {str(e)}\n{traceback.format_exc()}')
        flash(f'Error connecting Spotify: {str(e)}')
    
    return redirect(url_for('dashboard'))


@app.route('/spotify/disconnect')
@login_required
def spotify_disconnect():
    """Disconnect Spotify account"""
    current_user.spotify_access_token = None
    current_user.spotify_refresh_token = None
    current_user.spotify_token_expires_at = None
    current_user.spotify_user_id = None
    current_user.spotify_username = None
    db.session.commit()
    
    flash('Spotify account disconnected')
    return redirect(url_for('dashboard'))


@app.route('/instagram/save', methods=['POST'])
@login_required
def instagram_save():
    """Save Instagram credentials (session ID and/or username/password)"""
    instagram_username = request.form.get('instagram_username')
    instagram_password = request.form.get('instagram_password')
    instagram_session_id = request.form.get('instagram_session_id')
    
    # Update username if provided
    if instagram_username:
        current_user.instagram_username = instagram_username.strip()
    
    # Update password if provided (not empty)
    if instagram_password and instagram_password.strip():
        current_user.instagram_password = instagram_password.strip()
    
    # Update session ID if provided (not empty)
    if instagram_session_id and instagram_session_id.strip():
        current_user.instagram_session_id = instagram_session_id.strip()
    
    db.session.commit()
    
    flash('Instagram credentials saved')
    return redirect(url_for('dashboard'))


@app.route('/jobs/follow-artists', methods=['POST'])
@login_required
def job_follow_artists():
    """Create a job to follow artists from saved tracks"""
    if not current_user.spotify_access_token:
        return jsonify({'error': 'Spotify not connected'}), 400
    
    data = request.json or {}
    include_top = data.get('include_top_artists', False)
    
    # Create job
    job = Job(
        user_id=current_user.id,
        job_type='follow_artists',
        status='pending',
        input_data=json.dumps(data)
    )
    db.session.add(job)
    db.session.commit()
    
    # Queue job for background processing
    try:
        from workers import q, follow_artists_task
        q.enqueue(follow_artists_task, current_user.id, job.id, include_top)
    except Exception as e:
        # Fallback if Redis not available
        job.status = 'failed'
        job.output_data = json.dumps({'error': f'Worker queue unavailable: {str(e)}'})
        db.session.commit()
    
    return jsonify({'job_id': job.id, 'status': 'queued'})


@app.route('/jobs/find-instagram', methods=['POST'])
@login_required
def job_find_instagram():
    """Create a job to find Instagram accounts"""
    if not current_user.spotify_access_token:
        return jsonify({'error': 'Spotify not connected'}), 400
    
    job = Job(
        user_id=current_user.id,
        job_type='find_instagram',
        status='pending',
        input_data=json.dumps(request.json or {})
    )
    db.session.add(job)
    db.session.commit()
    
    # Queue job
    try:
        from workers import q, find_instagram_task
        data = request.json or {}
        q.enqueue(find_instagram_task, current_user.id, job.id, 
                 limit=data.get('limit'),
                 run_apify=data.get('run_apify', True))
    except Exception as e:
        job.status = 'failed'
        job.output_data = json.dumps({'error': f'Worker queue unavailable: {str(e)}'})
        db.session.commit()
    
    return jsonify({'job_id': job.id, 'status': 'queued'})


@app.route('/jobs/find-concerts', methods=['POST'])
@login_required
def job_find_concerts():
    """Create a job to find concerts"""
    if not current_user.spotify_access_token:
        return jsonify({'error': 'Spotify not connected'}), 400
    
    data = request.json or {}
    job = Job(
        user_id=current_user.id,
        job_type='find_concerts',
        status='pending',
        input_data=json.dumps(data)
    )
    db.session.add(job)
    db.session.commit()
    
    # Queue job
    try:
        from workers import q, find_concerts_task
        q.enqueue(find_concerts_task, current_user.id, job.id, 
                 data.get('location'), 
                 data.get('radius_miles'),
                 data.get('months_ahead', 3))
    except Exception as e:
        job.status = 'failed'
        job.output_data = json.dumps({'error': f'Worker queue unavailable: {str(e)}'})
        db.session.commit()
    
    return jsonify({'job_id': job.id, 'status': 'queued'})


@app.route('/api/playlists')
@login_required
def get_playlists():
    """Get user's playlists for selection"""
    if not current_user.spotify_access_token:
        return jsonify({'error': 'Spotify not connected'}), 400
    
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        
        auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            cache_path=None
        )
        
        # Refresh token if needed
        if current_user.spotify_token_expires_at and current_user.spotify_token_expires_at <= datetime.utcnow():
            if current_user.spotify_refresh_token:
                token_info = auth_manager.refresh_access_token(current_user.spotify_refresh_token)
                current_user.spotify_access_token = token_info['access_token']
                current_user.spotify_token_expires_at = datetime.fromtimestamp(token_info['expires_at'])
                db.session.commit()
        
        sp = spotipy.Spotify(auth=current_user.spotify_access_token)
        
        playlists = []
        offset = 0
        while True:
            results = sp.current_user_playlists(limit=50, offset=offset)
            if not results["items"]:
                break
            for playlist in results["items"]:
                if playlist["owner"]["id"] == current_user.spotify_user_id:
                    playlists.append({
                        'id': playlist['id'],
                        'name': playlist['name'],
                        'tracks': playlist.get('tracks', {}).get('total', 0)
                    })
            offset += 50
            if offset >= results["total"]:
                break
        
        return jsonify({'playlists': playlists})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/jobs/randomize-playlists', methods=['POST'])
@login_required
def job_randomize_playlists():
    """Create a job to randomize playlists"""
    if not current_user.spotify_access_token:
        return jsonify({'error': 'Spotify not connected'}), 400
    
    data = request.json or {}
    playlist_ids = data.get('playlist_ids', [])
    
    job = Job(
        user_id=current_user.id,
        job_type='randomize_playlists',
        status='pending',
        input_data=json.dumps(data)
    )
    db.session.add(job)
    db.session.commit()
    
    # Queue job
    try:
        from workers import q, randomize_playlists_task
        q.enqueue(randomize_playlists_task, current_user.id, job.id, playlist_ids)
    except Exception as e:
        job.status = 'failed'
        job.output_data = json.dumps({'error': f'Worker queue unavailable: {str(e)}'})
        db.session.commit()
    
    return jsonify({'job_id': job.id, 'status': 'queued'})


@app.route('/jobs/<int:job_id>')
@login_required
def job_status(job_id):
    """Get job status and results"""
    job = Job.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('dashboard'))
    
    output_data = None
    if job.output_data:
        try:
            output_data = json.loads(job.output_data)
        except Exception:
            output_data = {'raw': job.output_data}
    
    return render_template('job_detail.html', job=job, output_data=output_data)


@app.route('/api/jobs/<int:job_id>/progress')
@login_required
def job_progress_api(job_id):
    """Get job progress as JSON (for polling)"""
    job = Job.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check if job is hung (running for more than 1 hour)
    hung_threshold = datetime.utcnow() - timedelta(hours=1)
    if job.status == 'running' and job.created_at and job.created_at < hung_threshold:
        job.status = 'failed'
        job.progress_message = 'Job timed out (running for more than 1 hour)'
        job.output_data = json.dumps({'error': 'Job timed out after 1 hour'})
        job.completed_at = datetime.utcnow()
        db.session.commit()
    
    return jsonify({
        'status': job.status,
        'progress_percent': job.progress_percent or 0,
        'progress_message': job.progress_message or '',
        'execution_log': job.execution_log or '',
        'completed_at': job.completed_at.isoformat() if job.completed_at else None
    })


@app.route('/api/jobs/status')
@login_required
def jobs_status_api():
    """Get status of recent jobs as JSON (for dashboard polling)"""
    recent_jobs = Job.query.filter_by(user_id=current_user.id).order_by(Job.created_at.desc()).limit(10).all()
    
    # Check for hung jobs (running for more than 1 hour) and mark them as failed
    hung_threshold = datetime.utcnow() - timedelta(hours=1)
    for job in recent_jobs:
        if job.status == 'running' and job.created_at and job.created_at < hung_threshold:
            job.status = 'failed'
            job.progress_message = 'Job timed out (running for more than 1 hour)'
            job.output_data = json.dumps({'error': 'Job timed out after 1 hour'})
            job.completed_at = datetime.utcnow()
            db.session.commit()
    
    jobs_data = []
    for job in recent_jobs:
        jobs_data.append({
            'id': job.id,
            'job_type': job.job_type,
            'status': job.status,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'progress_percent': job.progress_percent or 0,
            'progress_message': job.progress_message or ''
        })
    
    return jsonify({'jobs': jobs_data})


@app.route('/api/jobs/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Manually cancel/fail a hung or running job"""
    job = Job.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if job.status in ['completed', 'failed']:
        return jsonify({'error': 'Job already completed or failed'}), 400
    
    job.status = 'failed'
    job.progress_message = 'Job cancelled by user'
    job.output_data = json.dumps({'error': 'Job cancelled by user'})
    job.completed_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'status': 'cancelled', 'message': 'Job cancelled successfully'})


@app.route('/jobs/<int:job_id>/download')
@login_required
def job_download(job_id):
    """Download job results as JSON"""
    job = Job.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    from flask import Response
    return Response(
        job.output_data or '{}',
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=job_{job_id}_results.json'
        }
    )


@app.route('/jobs/<int:job_id>/download-apify')
@login_required
def job_download_apify(job_id):
    """Download Apify input JSON for Instagram jobs"""
    job = Job.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if job.job_type != 'find_instagram':
        return jsonify({'error': 'This download is only available for Instagram jobs'}), 400
    
    if not job.output_data:
        return jsonify({'error': 'No output data available'}), 404
    
    try:
        output = json.loads(job.output_data)
        apify_input = output.get('apify_input', {})
        
        if not apify_input:
            return jsonify({'error': 'Apify input format not found in results'}), 404
        
        from flask import Response
        return Response(
            json.dumps(apify_input, indent=2),
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename=apify_input_job_{job_id}.json'
            }
        )
    except Exception as e:
        return jsonify({'error': f'Error generating Apify input: {str(e)}'}), 500


# Initialize database on first request (lazy initialization)
# Tables are created via migration command, not on app startup

if __name__ == '__main__':
    # Only enable debug in development, not production
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5000)


@app.route('/api/jobs/<int:job_id>/apify_status')
@login_required
def apify_status(job_id):
    """Check the real-time status of an Apify run for a job"""
    job = Job.query.get_or_404(job_id)
    
    if job.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Parse output_data to get apify_run_id
    try:
        output_data = json.loads(job.output_data) if job.output_data else {}
    except Exception:
        output_data = {}
    
    apify_run_id = output_data.get('apify_run_id')
    
    if not apify_run_id:
        return jsonify({
            'has_apify_run': False,
            'message': 'No Apify run associated with this job'
        })
    
    # Get Apify API token
    apify_api_token = os.getenv('APIFY_API_TOKEN')
    if not apify_api_token:
        return jsonify({
            'has_apify_run': True,
            'apify_run_id': apify_run_id,
            'error': 'Apify API token not configured'
        })
    
    # Fetch run status from Apify
    try:
        run_url = f"https://api.apify.com/v2/actor-runs/{apify_run_id}"
        response = requests.get(
            run_url,
            headers={"Authorization": f"Bearer {apify_api_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            run_data = response.json().get('data', {})
            
            apify_status = run_data.get('status', 'UNKNOWN')
            stats = run_data.get('stats', {})
            
            # Map Apify status to display status
            status_map = {
                'READY': 'queued',
                'RUNNING': 'running',
                'SUCCEEDED': 'completed',
                'FAILED': 'failed',
                'ABORTING': 'cancelling',
                'ABORTED': 'cancelled',
                'TIMED-OUT': 'timed_out'
            }
            
            display_status = status_map.get(apify_status, apify_status.lower())
            
            # Get dataset to see results
            dataset_id = run_data.get('defaultDatasetId')
            results = []
            followed_count = 0
            failed_count = 0
            
            if dataset_id and apify_status == 'SUCCEEDED':
                try:
                    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
                    dataset_response = requests.get(
                        dataset_url,
                        headers={"Authorization": f"Bearer {apify_api_token}"},
                        timeout=10
                    )
                    if dataset_response.status_code == 200:
                        results = dataset_response.json()
                        for item in results:
                            if item.get('status') == 'followed':
                                followed_count += 1
                            elif item.get('status') in ['failed', 'error', 'user_not_found']:
                                failed_count += 1
                except Exception:
                    pass
            
            return jsonify({
                'has_apify_run': True,
                'apify_run_id': apify_run_id,
                'apify_status': apify_status,
                'display_status': display_status,
                'run_url': f"https://console.apify.com/actors/runs/{apify_run_id}",
                'started_at': run_data.get('startedAt'),
                'finished_at': run_data.get('finishedAt'),
                'duration_seconds': stats.get('runTimeSecs'),
                'results': {
                    'followed': followed_count,
                    'failed': failed_count,
                    'total_items': len(results)
                }
            })
        else:
            return jsonify({
                'has_apify_run': True,
                'apify_run_id': apify_run_id,
                'error': f'Failed to fetch Apify status (HTTP {response.status_code})'
            })
            
    except requests.Timeout:
        return jsonify({
            'has_apify_run': True,
            'apify_run_id': apify_run_id,
            'error': 'Apify API request timed out'
        })
    except Exception as e:
        return jsonify({
            'has_apify_run': True,
            'apify_run_id': apify_run_id,
            'error': str(e)
        })
