# Render Deployment Guide for School Portal

## Prerequisites
- GitHub account with your project repository
- Render account (free at https://render.com)

## Step 1: Push Code to GitHub

```bash
# Initialize git if not already done
git init
git add .
git commit -m "Initial commit - ready for deployment"

# Create a new repository on GitHub, then push:
git remote add origin https://github.com/yourusername/school-portal.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Render

### Option A: Using render.yaml (Recommended)

1. Go to https://dashboard.render.com
2. Click "New +"
3. Select "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect `render.yaml` and configure everything
6. Click "Deploy"

### Option B: Manual Setup

1. Go to https://dashboard.render.com
2. Click "New +"
3. Select "PostgreSQL" and create a database
   - Name: `school-portal-db`
   - (Note the database URL - you'll need it)

4. Click "New +"
5. Select "Web Service"
6. Connect your GitHub repository

7. Configure the Web Service:
   - **Name**: `school-portal`
   - **Environment**: `Python`
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Build Command**: 
     ```
     pip install -r requirements.txt && python school_portal/manage.py migrate && python school_portal/manage.py collectstatic --noinput
     ```
   - **Start Command**: 
     ```
     gunicorn school_portal.wsgi
     ```
   - **Plan**: Free (or upgrade as needed)

8. Add Environment Variables:
   - `DEBUG`: `False`
   - `SECRET_KEY`: Paste your generated secret key
   - `ALLOWED_HOSTS`: `your-app-name.onrender.com`
   - `DATABASE_URL`: (Database connection string - provided by Render)
   - `EMAIL_HOST`: `smtp.gmail.com`
   - `EMAIL_PORT`: `587`
   - `EMAIL_HOST_USER`: Your email
   - `EMAIL_HOST_PASSWORD`: Your app-specific password

9. Click "Create Web Service"

## Step 3: Generate Secret Key

Before deploying, generate a new secure secret key:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Use this value for the `SECRET_KEY` environment variable.

## Step 4: Create Super User (After First Deploy)

Once deployed, Render gives you a shell access:

1. In Render dashboard, click your Web Service
2. Click "Shell" tab
3. Run:
   ```bash
   python school_portal/manage.py createsuperuser
   ```

## Step 5: Access Your App

After deployment:
- **Website**: https://your-app-name.onrender.com
- **Admin**: https://your-app-name.onrender.com/admin

## Environment Variables Reference

```env
# Django Settings
DEBUG=False
SECRET_KEY=your-generated-secret-key-here
ALLOWED_HOSTS=your-app-name.onrender.com

# Database (Auto-provided by Render)
DATABASE_URL=postgresql://...

# Email Configuration (Optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

## Troubleshooting

### Issue: "ModuleNotFoundError"
**Solution**: Check that `requirements.txt` includes all packages and build command runs `pip install -r requirements.txt`

### Issue: "Static files not loading"
**Solution**: Make sure `collectstatic` runs in build command:
```
python school_portal/manage.py collectstatic --noinput
```

### Issue: "Database migrations failed"
**Solution**: Add this to build command:
```
python school_portal/manage.py migrate
```

### Issue: "ALLOWED_HOSTS error"
**Solution**: Set `ALLOWED_HOSTS` to your Render domain:
```
your-app-name.onrender.com
```

### Issue: "Cannot connect to database"
**Solution**: 
1. Verify `DATABASE_URL` environment variable is set
2. Check it matches your PostgreSQL database connection string
3. Render format: `postgresql://user:password@host:port/database`

## Monitoring Logs

In Render dashboard:
1. Click your Web Service
2. Click "Logs" to see real-time logs
3. Check for errors and deployment status

## Database Access

To access your PostgreSQL database from command line:

```bash
# Using psql (if installed)
psql your-database-url

# Or in Render Shell:
python school_portal/manage.py dbshell
```

## Redeployment

To redeploy after code changes:

```bash
git add .
git commit -m "Your changes"
git push origin main
```

Render automatically redeploys when code is pushed.

## Free Tier Limitations

- **Web Service**: Free tier may sleep after 15 minutes of inactivity
- **Database**: 256 MB PostgreSQL (plenty for a school portal)
- **Bandwidth**: Limited but sufficient for most use cases
- **Storage**: Sufficient for your data

## Upgrade to Paid

If you need:
- No auto-sleep → Upgrade to Standard ($7/month)
- More database space → Upgrade PostgreSQL plan
- Better performance → Upgrade instance type

## Support

For issues:
1. Check Render logs in dashboard
2. Review Django error messages
3. Verify environment variables are set
4. Check `requirements.txt` has all dependencies
5. Ensure `Procfile` is in root directory

## Next Steps

1. Test all features in production
2. Set up a domain name (optional)
3. Configure email for password resets
4. Set up monitoring/alerts
5. Regular database backups (recommended)

## Production Checklist

- [x] PostgreSQL database created
- [x] Environment variables set
- [x] Secret key generated and stored
- [x] DEBUG=False
- [x] ALLOWED_HOSTS configured
- [x] Static files configuration
- [x] Database migrations run
- [x] Superuser created
- [x] Email configuration (optional)
- [x] HTTPS enforced (Render provides automatically)
- [x] Rate limiting enabled
- [x] Security headers configured

Your School Portal is now live on Render!
