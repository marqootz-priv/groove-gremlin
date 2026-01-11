# Deployment Guide

This guide covers deploying the Spotify Tools web application to various hosting services.

## Prerequisites

Before deploying, ensure you have:
- ✅ Production-ready `SECRET_KEY` (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)
- ✅ Database URL (PostgreSQL recommended for production)
- ✅ Redis instance for background jobs
- ✅ Spotify API credentials
- ✅ Updated redirect URIs for production domain

## Deployment Options

### Option 1: Heroku (Easiest)

#### Setup

1. **Install Heroku CLI**:
   ```bash
   # macOS
   brew tap heroku/brew && brew install heroku
   
   # Or download from: https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login to Heroku**:
   ```bash
   heroku login
   ```

3. **Create App**:
   ```bash
   cd webapp
   heroku create your-app-name
   ```

4. **Add PostgreSQL**:
   ```bash
   heroku addons:create heroku-postgresql:essential-0
   ```
   Note: The `mini` plan is end-of-life. `essential-0` is the current cheapest option ($5/month).

5. **Add Redis**:
   ```bash
   heroku addons:create heroku-redis:mini
   ```
   The `mini` plan is $3/month and should be sufficient for development/small apps.

6. **Set Environment Variables**:
   ```bash
   heroku config:set SECRET_KEY=your-generated-secret-key
   heroku config:set SPOTIFY_CLIENT_ID=your-client-id
   heroku config:set SPOTIFY_CLIENT_SECRET=your-client-secret
   heroku config:set SPOTIFY_REDIRECT_URI=https://your-app-name.herokuapp.com/spotify/callback
   ```

7. **Deploy**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   heroku git:remote -a your-app-name
   git push heroku main
   ```

8. **Run Migrations**:
   ```bash
   heroku run "python -c 'from app import app, db; app.app_context().push(); db.create_all()'" --app your-app-name
   ```
   Note: The command must be in quotes, and use single quotes inside for the Python code.

9. **Start Worker** (in separate terminal or via Heroku Scheduler):
   ```bash
   heroku run rq worker spotify_tools
   ```

#### Cost
- **Essential-0 PostgreSQL**: $5/month
- **Mini Redis**: $3/month
- **Hobby Dyno**: $7/month (or Eco at $5/month if available)
- **Total**: ~$15-17/month for basic setup
- Note: Heroku no longer has a free tier for dynos, but addons have low-cost options

---

### Option 2: Google Cloud Platform (App Engine)

#### Setup

1. **Install Google Cloud SDK**:
   ```bash
   # macOS
   brew install --cask google-cloud-sdk
   ```

2. **Login and Set Project**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Enable APIs**:
   ```bash
   gcloud services enable appengine.googleapis.com
   gcloud services enable sqladmin.googleapis.com
   ```

4. **Create Cloud SQL Instance**:
   ```bash
   gcloud sql instances create spotify-tools-db \
     --database-version=POSTGRES_14 \
     --tier=db-f1-micro \
     --region=us-central1
   ```

5. **Create Database**:
   ```bash
   gcloud sql databases create spotify_tools --instance=spotify-tools-db
   ```

6. **Update `app.yaml`** with your configuration

7. **Deploy**:
   ```bash
   gcloud app deploy
   ```

#### Cost
- **Free tier**: Limited (28 hours/day free)
- **Paid**: ~$25-50/month depending on traffic

---

### Option 3: Firebase Functions (Serverless)

#### Setup

1. **Install Firebase CLI**:
   ```bash
   npm install -g firebase-tools
   ```

2. **Login**:
   ```bash
   firebase login
   ```

3. **Initialize Project**:
   ```bash
   cd webapp
   firebase init functions
   # Select Python, use existing app.py
   ```

4. **Update `firebase.json`** if needed

5. **Deploy**:
   ```bash
   firebase deploy --only functions
   ```

**Note**: Firebase Functions for Python is newer and may have limitations. Consider App Engine or Cloud Run instead.

---

### Option 4: DigitalOcean App Platform

#### Setup

1. **Create App**:
   - Go to DigitalOcean App Platform
   - Connect GitHub repository
   - Select `webapp/` as source directory

2. **Configure**:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Run command: `gunicorn app:app`

3. **Add Database**:
   - Add PostgreSQL database component
   - Add Redis component

4. **Set Environment Variables**:
   - Add all required env vars in App Settings

5. **Deploy**:
   - Automatic on git push

#### Cost
- **Basic**: $12/month (app) + $15/month (database) + $15/month (Redis) = ~$42/month

---

### Option 5: Railway

#### Setup

1. **Sign up** at railway.app
2. **New Project** → Deploy from GitHub
3. **Add PostgreSQL** service
4. **Add Redis** service
5. **Set environment variables**
6. **Deploy**

#### Cost
- **Hobby**: $5/month + usage
- **Pro**: $20/month + usage

---

### Option 6: Render

#### Setup

1. **Sign up** at render.com
2. **New Web Service** → Connect GitHub
3. **Configure**:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
4. **Add PostgreSQL** database
5. **Add Redis** instance
6. **Set environment variables**

#### Cost
- **Free tier**: Limited (spins down after inactivity)
- **Starter**: $7/month (web) + $7/month (database) + $7/month (Redis) = ~$21/month

---

## Production Checklist

### Security

- [ ] Change `SECRET_KEY` to strong random value
- [ ] Use environment variables for all secrets
- [ ] Enable HTTPS (automatic on most platforms)
- [ ] Add CSRF protection (Flask-WTF)
- [ ] Add rate limiting
- [ ] Validate all inputs
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set up proper logging
- [ ] Add error monitoring (Sentry)

### Performance

- [ ] Use Gunicorn with multiple workers
- [ ] Set up Redis for background jobs
- [ ] Configure database connection pooling
- [ ] Add caching where appropriate
- [ ] Set up CDN for static assets (if needed)

### Monitoring

- [ ] Set up application logging
- [ ] Add error tracking (Sentry)
- [ ] Monitor database performance
- [ ] Set up uptime monitoring
- [ ] Configure alerts

### Database Migrations

For production, use Flask-Migrate:

```bash
pip install flask-migrate

# In app.py, add:
from flask_migrate import Migrate
migrate = Migrate(app, db)

# Then:
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

## Running Workers

Background workers need to run separately. Options:

### Option 1: Separate Process

```bash
# On your server
rq worker spotify_tools --url $REDIS_URL
```

### Option 2: Heroku Worker Dyno

Add to `Procfile`:
```
worker: rq worker spotify_tools --url $REDIS_URL
```

Then:
```bash
heroku ps:scale worker=1
```

### Option 3: Systemd Service (VPS)

Create `/etc/systemd/system/spotify-tools-worker.service`:

```ini
[Unit]
Description=Spotify Tools RQ Worker
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/webapp
Environment="REDIS_URL=redis://localhost:6379"
ExecStart=/path/to/venv/bin/rq worker spotify_tools --url $REDIS_URL
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable spotify-tools-worker
sudo systemctl start spotify-tools-worker
```

## Environment Variables

Required for all deployments:

```bash
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@host:5432/dbname
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SPOTIFY_REDIRECT_URI=https://your-domain.com/spotify/callback
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_URL=redis://your-redis-host:6379
```

## Testing Deployment

1. **Test Registration/Login**
2. **Test Spotify OAuth**
3. **Test Job Creation**
4. **Test Worker Processing**
5. **Test Job Results**

## Troubleshooting

### "Database connection failed"
- Check `DATABASE_URL` is correct
- Ensure database is accessible
- Check firewall rules

### "Worker not processing jobs"
- Verify Redis is running
- Check worker is running: `rq info`
- Check Redis connection

### "Spotify OAuth not working"
- Verify redirect URI matches exactly
- Check redirect URI is in Spotify app settings
- Ensure HTTPS is used in production

### "Jobs stuck in pending"
- Worker may not be running
- Check Redis connection
- Review worker logs

## Recommended Setup

For production, I recommend:

1. **Heroku** - Easiest, good for small-medium scale
2. **Railway** - Modern, good pricing
3. **DigitalOcean App Platform** - More control, good pricing
4. **Google Cloud Run** - Serverless, pay per use

Choose based on:
- Expected traffic
- Budget
- Technical expertise
- Scaling needs
