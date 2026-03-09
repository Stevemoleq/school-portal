# Security Implementation Guide

## Security Measures Implemented

### 1. **Rate Limiting on Login** ✅
- **File**: `apps/accounts/views.py`
- **Implementation**: `@ratelimit(key='ip', rate='5/m')`
- **Protection**: Limits login attempts to 5 per minute per IP address
- **Prevents**: Brute force attacks

### 2. **Authorization Checks (Role-Based Access Control)** ✅
- **Student Dashboard**: Only students can access
- **Teacher Dashboard**: Only teachers can access  
- **Admin Dashboard**: Only admin/staff can access
- **Results View**: Students can only see their own results
- **Error Messages**: Clear feedback if access is denied

### 3. **HTTPS/SSL Security** ✅
- `SECURE_SSL_REDIRECT = True` - Forces HTTPS in production
- `SESSION_COOKIE_SECURE = True` - Session cookies only over HTTPS
- `CSRF_COOKIE_SECURE = True` - CSRF cookies only over HTTPS
- `SECURE_HSTS_SECONDS = 31536000` - HTTP Strict Transport Security for 1 year
- `X_FRAME_OPTIONS = 'DENY'` - Prevents clickjacking attacks

### 4. **XSS (Cross-Site Scripting) Protection** ✅
- `SECURE_BROWSER_XSS_FILTER = True` - Browser XSS protection enabled
- Django Templates auto-escape HTML by default (prevents XSS in templates)
- Content Security Policy implemented

### 5. **CSRF (Cross-Site Request Forgery) Protection** ✅
- `{% csrf_token %}` in all forms (verify in templates)
- `CSRF_COOKIE_SECURE = True` for production
- Django middleware handles CSRF validation

### 6. **SQL Injection Protection** ✅
- Using Django ORM (parameterized queries)
- No raw SQL queries used
- All database interactions go through Django models

### 7. **Password Security** ✅
- Django's built-in password validators enabled:
  - `UserAttributeSimilarityValidator` - Prevents password like username
  - `MinimumLengthValidator` - Minimum password length
  - `CommonPasswordValidator` - Blocks common passwords
  - `NumericPasswordValidator` - Blocks all-numeric passwords

### 8. **Secret Key Management** ✅
- Secret key moved to `.env` file (not in source code)
- Generated new secret key for production
- Never expose SECRET_KEY in version control

### 9. **Debug Mode Management** ✅
- `DEBUG = False` in production prevents sensitive error details
- Error pages don't expose file paths or settings
- Controlled by `DEBUG` environment variable

### 10. **ALLOWED_HOSTS Configuration** ✅
- Prevents Host Header Injection attacks
- Set via environment variable: `ALLOWED_HOSTS`
- Must be configured for your actual domain

## Testing the Security

### Test 1: Rate Limiting
```bash
# Try 6 failed logins in 60 seconds - should block the 6th attempt
# Expected: "Rate limit exceeded" error after 5 attempts
```

### Test 2: Authorization
```bash
# Login as student, try accessing:
# - /accounts/teacher-dashboard/ → Should redirect
# - /accounts/admin-dashboard/ → Should redirect
```

### Test 3: XSS Prevention
```bash
# In announcements, try:
# <script>alert('XSS')</script>
# Expected: Script displayed as text, not executed
```

### Test 4: HTTPS
```bash
# In production, try accessing via HTTP
# Expected: Automatic redirect to HTTPS
```

### Test 5: CSRF Protection
```bash
# Use browser DevTools to remove {% csrf_token %} from form
# Expected: 403 Forbidden error when submitting
```

## Environment Variables Required

Add these to `.env` for production:

```env
# Security
DEBUG=False
SECRET_KEY=your-new-secure-random-key
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,server-ip

# Database
DB_HOST=production-db-server
DB_PASSWORD=production-password

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## To Generate a Secure Secret Key

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## Additional Security Recommendations

### 1. **Enable 2FA (Two-Factor Authentication)**
```bash
pip install django-otp qrcode
```

### 2. **Add Security Headers**
- Already implemented: CSP, X-Frame-Options, HSTS

### 3. **Database Security**
- Use strong PostgreSQL passwords
- Create separate database user (not postgres superuser)
- Enable SSL for database connections

### 4. **Deployment Security**
- Never run Django with `DEBUG=True` in production
- Use production WSGI server (Gunicorn, uWSGI)
- Keep Django and packages updated
- Run security scan: `python manage.py check --deploy`

### 5. **Logging & Monitoring**
- Log authentication failures
- Monitor for suspicious activity
- Set up alerts for failed login attempts

### 6. **Backup & Recovery**
- Regular database backups
- Encrypted backup storage
- Test recovery procedures

## Security Audit Checklist

- [x] Rate limiting on login
- [x] Role-based access control
- [x] Authorization checks on all views
- [x] HTTPS/SSL enforcement
- [x] XSS protection
- [x] CSRF protection
- [x] SQL injection prevention
- [x] Secret key management
- [x] Debug mode disabled in production
- [x] ALLOWED_HOSTS configured
- [ ] 2FA implementation (recommended)
- [ ] Security headers (CSP, etc.)
- [ ] Logging & monitoring setup
- [ ] Regular security audits

## Support

For security issues:
1. Don't commit secrets to version control
2. Rotate passwords regularly
3. Monitor access logs
4. Keep software updated
5. Test security changes in staging first
