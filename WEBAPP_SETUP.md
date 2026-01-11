# Web Application Setup Guide

This guide explains how to set up and deploy the web application version of Spotify Tools.

## Overview

The web app provides:
- ✅ User accounts and authentication
- ✅ Spotify OAuth integration (no password needed)
- ✅ Instagram username storage
- ✅ Web-based job queue
- ✅ Job history and results
- ✅ Access from anywhere via browser

## Quick Start

### 1. Install Dependencies

```bash
cd webapp
pip install -r requirements.txt
```

### 2. Set Up Environment

Create `webapp/.env`:

```bash
SECRET_KEY=generate-a-random-secret-key-here
DATABASE_URL=sqlite:///spotify_tools.db
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:5000/spotify/callback
```

**Important**: 
- Generate a strong `SECRET_KEY` (use: `python -c "import secrets; print(secrets.token_hex(32))"`)
- Update `SPOTIFY_REDIRECT_URI` for production

### 3. Run the App

```bash
python app.py
```

Visit: http://localhost:5000

## User Flow

### For End Users

1. **Register**: Create account at `/register`
2. **Login**: Access dashboard at `/login`
3. **Connect Spotify**: Click "Connect Spotify" → OAuth flow
4. **Set Instagram**: Enter Instagram username (password provided per-run)
5. **Run Jobs**: Click action buttons to queue jobs
6. **View Results**: Check job status and download results

### For Administrators

- Monitor all users and jobs
- Manage database
- View logs and errors

## Architecture

```
User Browser
    ↓
Flask Web App (app.py)
    ↓
SQLAlchemy Database (users, jobs)
    ↓
Background Workers (TODO: Celery/RQ)
    ↓
Spotify API / Instagram Automation
```

## Current Status

### ✅ Implemented

- User registration/login
- Spotify OAuth connection
- Instagram username storage
- Job creation and tracking
- Web interface (templates)
- Database models

### 🚧 TODO (For Full Functionality)

1. **Background Job Processing**
   - Add Celery or RQ
   - Implement worker processes
   - Process jobs asynchronously

2. **Job Implementation**
   - Port CLI script logic to web app
   - Follow artists from saved tracks
   - Find Instagram accounts
   - Find concerts
   - Randomize playlists

3. **Instagram Automation**
   - Integrate with Apify API
   - Or run Selenium in workers
   - Handle Instagram credentials securely

4. **Production Features**
   - Error handling and logging
   - Email notifications
   - File downloads
   - API endpoints
   - Admin panel

## Adding Background Jobs

### Option 1: Celery (Recommended)

```bash
pip install celery redis
```

```python
# In app.py
from celery import Celery

celery = Celery('spotify_tools', broker='redis://localhost:6379')

@celery.task
def process_follow_artists(user_id, job_id):
    # Implementation here
    pass
```

Run worker:
```bash
celery -A app.celery worker --loglevel=info
```

### Option 2: RQ (Simpler)

```bash
pip install rq redis
```

```python
from rq import Queue
from redis import Redis

redis_conn = Redis()
q = Queue(connection=redis_conn)

# Enqueue job
job = q.enqueue(process_follow_artists, user_id, job_id)
```

Run worker:
```bash
rq worker
```

## Deployment

### Development

```bash
python app.py  # Uses Flask dev server
```

### Production

Use Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### With Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## Security Checklist

- [ ] Change `SECRET_KEY` in production
- [ ] Use environment variables for all secrets
- [ ] Enable HTTPS
- [ ] Add CSRF protection (Flask-WTF)
- [ ] Add rate limiting
- [ ] Validate all inputs
- [ ] Use PostgreSQL in production (not SQLite)
- [ ] Set up proper logging
- [ ] Add error monitoring (Sentry)

## Database Migrations

For production, use Flask-Migrate:

```bash
pip install flask-migrate
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

## Next Steps

1. **Implement background workers** (Celery/RQ)
2. **Port CLI logic** to web app functions
3. **Add job result downloads**
4. **Add email notifications**
5. **Deploy to production** (Heroku, DigitalOcean, etc.)

## Comparison: Web App vs CLI

| Aspect | CLI Scripts | Web App |
|--------|-------------|---------|
| Setup | Per-user | One-time server setup |
| Access | Local machine | Anywhere (browser) |
| User Management | Manual | Built-in accounts |
| Credentials | .env files | OAuth + database |
| Job History | Files | Database |
| Sharing | Share code | Share URL |
| Maintenance | Per-user | Centralized |

The web app is better for:
- Teams/organizations
- Non-technical users
- Centralized management
- Access from multiple devices

The CLI scripts are better for:
- Developers
- Local automation
- Full control
- No server needed
