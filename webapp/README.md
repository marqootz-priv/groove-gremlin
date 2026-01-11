# Spotify Tools Web Application

A web-based interface for the Spotify Tools suite, allowing users to create accounts, connect their Spotify and Instagram accounts, and run automation tasks through a browser.

## Features

- ✅ **User Accounts**: Register, login, manage profile
- ✅ **Spotify OAuth**: Connect Spotify account securely
- ✅ **Instagram Integration**: Save Instagram username (password provided per-run for security)
- ✅ **Job Queue**: Run tasks as background jobs
- ✅ **Job History**: View past jobs and results
- ✅ **Web Interface**: Easy-to-use browser interface

## Setup

### 1. Install Dependencies

```bash
cd webapp
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```bash
SECRET_KEY=your-secret-key-here-change-in-production
DATABASE_URL=sqlite:///spotify_tools.db
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:5000/spotify/callback
```

### 3. Initialize Database

```bash
python app.py
# This will create the database on first run
```

### 4. Run the Application

```bash
python app.py
```

Visit: http://localhost:5000

## Architecture

### Current Implementation

- **Flask**: Web framework
- **SQLAlchemy**: Database ORM
- **Flask-Login**: User authentication
- **Spotipy**: Spotify API integration

### Database Models

- **User**: User accounts with Spotify/Instagram connections
- **Job**: Job queue and history

### Routes

- `/` - Home page
- `/register` - User registration
- `/login` - User login
- `/dashboard` - Main dashboard
- `/spotify/connect` - Connect Spotify account
- `/spotify/callback` - Spotify OAuth callback
- `/jobs/*` - Job management endpoints

## Deployment

The web app needs to be deployed to a hosting service for others to access it. See **`DEPLOYMENT.md`** for complete deployment instructions for:

- ✅ Heroku (easiest)
- ✅ Google Cloud Platform
- ✅ DigitalOcean
- ✅ Railway
- ✅ Render
- ✅ Firebase Functions

## Background Job Processing

✅ **Implemented**: Background workers using RQ (Redis Queue)

To run workers:
```bash
# Install Redis locally or use cloud Redis
rq worker spotify_tools --url redis://localhost:6379
```

For production, see `DEPLOYMENT.md` for worker setup.

## Job Implementations

✅ **Implemented**: All job types are now functional:

- ✅ Follow artists from saved tracks
- ✅ Find Instagram accounts
- ✅ Find concerts
- ✅ Randomize playlists

Jobs run asynchronously via background workers.

## Next Steps (Optional Enhancements)

1. **Celery** or **RQ** for background tasks
2. **Redis** or **RabbitMQ** as message broker
3. Worker processes to execute jobs

Example with Celery:

```python
from celery import Celery

celery = Celery('spotify_tools', broker='redis://localhost:6379')

@celery.task
def follow_artists_task(user_id, job_id):
    # Get user and job
    user = User.query.get(user_id)
    job = Job.query.get(job_id)
    
    # Update job status
    job.status = 'running'
    db.session.commit()
    
    try:
        # Use existing scripts/logic
        # ... follow artists code ...
        
        job.status = 'completed'
        job.output_data = json.dumps(results)
    except Exception as e:
        job.status = 'failed'
        job.output_data = json.dumps({'error': str(e)})
    
    job.completed_at = datetime.utcnow()
    db.session.commit()
```

### Instagram Automation

For Instagram following, integrate with:
- Apify API (if using Apify actor)
- Or run Selenium tasks in background workers

### Production Deployment

1. **Use PostgreSQL** instead of SQLite
2. **Set strong SECRET_KEY**
3. **Use environment variables** for all secrets
4. **Add HTTPS**
5. **Use production WSGI server** (Gunicorn, uWSGI)
6. **Add error monitoring** (Sentry)
7. **Add logging**

### Additional Features

- Email notifications for job completion
- Scheduled jobs (cron-like)
- Export job results
- API endpoints for programmatic access
- Admin panel for user management

## Security Considerations

- ✅ Passwords are hashed (Werkzeug)
- ✅ Sessions managed by Flask-Login
- ✅ OAuth for Spotify (no password storage)
- ⚠️ Instagram passwords: Currently provided per-run (consider session cookies)
- ⚠️ Add CSRF protection (Flask-WTF)
- ⚠️ Rate limiting for API endpoints
- ⚠️ Input validation and sanitization

## Deployment Options

### Option 1: Heroku

```bash
# Add Procfile
web: gunicorn app:app

# Deploy
git push heroku main
```

### Option 2: Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Option 3: VPS (DigitalOcean, AWS, etc.)

- Use Gunicorn + Nginx
- Set up PostgreSQL
- Use systemd for process management
- Add SSL with Let's Encrypt

## Comparison: Web App vs CLI Scripts

| Feature | CLI Scripts | Web App |
|---------|-------------|---------|
| Setup | Per-user .env | Shared app, user accounts |
| Access | Local only | Anywhere via browser |
| User Management | Manual | Built-in |
| Job History | Files | Database |
| Sharing | Share code | Share URL |
| Maintenance | Per-user | Centralized |

## Migration from CLI

Users can:
1. Create account in web app
2. Connect Spotify (OAuth - no credentials needed)
3. Use same features as CLI scripts
4. View history in dashboard
5. No need for local setup
