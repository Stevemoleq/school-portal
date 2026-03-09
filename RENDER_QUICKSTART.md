# Quick Start: Deploy to Render

## Files Created for Deployment:
- ✅ `Procfile` - Tells Render how to run your app
- ✅ `render.yaml` - Auto-configuration for Render
- ✅ `requirements.txt` - All dependencies
- ✅ `DEPLOYMENT.md` - Full deployment guide
- ✅ `.gitignore` - Prevents committing sensitive files
- ✅ Settings updated for Render

## 5-Minute Deployment:

### 1. Generate New Secret Key
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```
Save the output - you'll need it.

### 2. Push to GitHub
```bash
git init
git add .
git commit -m "Ready for Render deployment"
git branch -M main
git remote add origin https://github.com/yourusername/school-portal.git
git push -u origin main
```

### 3. Deploy on Render
1. Go to https://render.com
2. Sign up (free)
3. Click "New +"
4. Select "Blueprint"
5. Connect GitHub repo
6. Click "Deploy"

### 4. Set Environment Variables
In Render dashboard:
- `SECRET_KEY`: Paste your generated key
- `ALLOWED_HOSTS`: (Render fills this automatically)
- `EMAIL_HOST_USER`: Your email (optional)
- `EMAIL_HOST_PASSWORD`: App password (optional)

### 5. Create Admin User
In Render Shell:
```bash
python school_portal/manage.py createsuperuser
```

### 6. Visit Your Site!
- App: `https://your-app-name.onrender.com`
- Admin: `https://your-app-name.onrender.com/admin`

## Important Notes:

⚠️ **After each push to GitHub, Render auto-deploys** - no manual steps needed!

⚠️ **Keep .env local (don't commit)** - Render manages environment variables

⚠️ **Free tier may have 15-min sleep** - Upgrade to "Standard" ($7/mo) if needed

⚠️ **Database included free** - 256 MB PostgreSQL (sufficient for school use)

## Troubleshooting:

**App won't deploy?**
- Check Render logs (Logs tab in dashboard)
- Verify all required environment variables set
- Make sure `Procfile` is in root directory

**Static files not loading?**
- May take a minute after deploy
- Clear browser cache
- Check collectstatic ran in build logs

**Can't connect to database?**
- Verify DATABASE_URL is set correctly
- Wait 30 seconds after database creation
- Check PostgreSQL database exists

##Next Steps:

1. ✅ Deploy to Render
2. ✅ Test login with admin credentials
3. ✅ Add students/teachers/results
4. ✅ Enable email (optional)
5. ✅ Set custom domain (optional)
6. ✅ Monitor performance

## Free Resources:

- Server: Shared (Render)
- Database: 256 MB PostgreSQL
- Bandwidth: 100 GB/month
- Build time: Unlimited

## Upgrade Path:

| Feature | Free | Standard ($7/mo) | Premium ($12/mo) |
|---------|------|------------------|------------------|
| Uptime | Auto-sleep | Always on | Always on |
| CPU | Shared | 0.5 | 1 |
| RAM | 512 MB | 1 GB | 2 GB |
| Good for | Testing | Production | Heavy use |

## Support:
- Render Docs: https://render.com/docs
- Django Docs: https://docs.djangoproject.com
- Issues: Check DEPLOYMENT.md

You're all set! 🚀 Deploy now!
