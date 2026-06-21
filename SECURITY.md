# Security Implementation Guide

## Security Measures Implemented

### 1. **Rate Limiting on Login** ✅
- **File**: `apps/accounts/views.py`
- **Implementation**: `@ratelimit(key='ip', rate='5/m', method='POST', block=True)` and
  `@ratelimit(key='post:username', rate='10/h', method='POST', block=True)`.
- **Parent login** (`apps/parents/views.py`): same policy, keyed on `ip` and `post:login_id`.
- **Student registration** (`apps/accounts/views.py`): `key='ip', rate='5/h', block=True`.
- **Password reset** (`apps/accounts/views.py`): `key='user', rate='10/h'`.
- **Note**: rate-limit counters are scoped to the default cache (LocMemCache).
  In multi-process / multi-worker production deployments configure a
  shared cache (Redis / Memcached) via `CACHES` in `settings.py`.
- **Prevents**: Brute force attacks, credential stuffing.

### 2. **Authorization Checks (Role-Based Access Control)** ✅
- **Student Dashboard**: Only students can access
- **Teacher Dashboard**: Only teachers can access
- **Accountant Dashboard**: Only users with an `Accountant` profile
- **Admin Dashboard**: Only `is_superuser` users (NOT `is_staff`).
  Accountants are intentionally NOT `is_staff` to prevent privilege
  escalation.
- **Audit log**: Restricted to superusers (exposes staff usernames / IPs).
- **Announcement detail view**: Filtered by `target_audience` for the
  caller's role.

### 3. **HTTPS/SSL Security** ✅
- `SECURE_SSL_REDIRECT = True` - Forces HTTPS in production
- `SESSION_COOKIE_SECURE = True` - Session cookies only over HTTPS
- `CSRF_COOKIE_SECURE = True` - CSRF cookies only over HTTPS
- `SECURE_HSTS_SECONDS = 31536000` - HTTP Strict Transport Security for 1 year
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_HSTS_PRELOAD = True`
- `X_FRAME_OPTIONS = 'DENY'` - Prevents clickjacking
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SECURE_REFERRER_POLICY = 'same-origin'`
- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` -
  only effective when running behind a single trusted proxy hop.

### 4. **XSS (Cross-Site Scripting) Protection** ✅
- Django templates auto-escape HTML by default (prevents XSS in templates)
- `SECURE_CONTENT_TYPE_NOSNIFF` set (modern equivalent of the legacy
  `SECURE_BROWSER_XSS_FILTER` setting, which was removed in Django 4.0+)
- File uploads (e.g. bank slips) are verified by magic bytes, not just
  the client-supplied `Content-Type` header.

### 5. **CSRF (Cross-Site Request Forgery) Protection** ✅
- `{% csrf_token %}` in all forms
- `CSRF_COOKIE_SECURE = True` for production
- `CSRF_TRUSTED_ORIGINS` is built from the explicit `ALLOWED_HOSTS` list
  in production — no wildcards.

### 6. **SQL Injection Protection** ✅
- Django ORM (parameterized queries) is used everywhere.
- The one place raw SQL appears (`apps/accounts/student_id.py`) uses
  parameter binding and is wrapped in a transaction with a PostgreSQL
  `pg_advisory_xact_lock` to make sequence generation race-free.

### 7. **Password Security** ✅
- Django's built-in password validators enabled:
  - `UserAttributeSimilarityValidator`
  - `MinimumLengthValidator`
  - `CommonPasswordValidator`
  - `NumericPasswordValidator`
- Student/teacher/parent accounts are now created with **random opaque
  passwords** (no longer derived from `student_id`, `employee_id`, or
  `phone_number` — see git history).
- A new management command `python manage.py create_admin` replaces
  the previous `create_superuser.py` script; it generates a strong
  random password if one is not provided via env var.

### 8. **Secret Key Management** ✅
- `SECRET_KEY` is required at startup; the application refuses to
  boot in production without a non-default value.
- `.env.example` ships with empty placeholders for `SECRET_KEY` and
  `DB_PASSWORD`; never commit the real `.env`.

### 9. **Debug Mode Management** ✅
- `DEBUG = False` is the production default. When `DEBUG=True` the
  app warns (on stderr) that the dev `SECRET_KEY` is in use.

### 10. **ALLOWED_HOSTS Configuration** ✅
- `ALLOWED_HOSTS` is required in production; the previous `.onrender.com`
  wildcard default has been removed. The app refuses to start in
  production without an explicit list.

### 11. **Audit Trail** ✅
- All fee-management actions (`approve_payment`, `reject_payment`,
  `record_payment`, `create_fee_structure`, `download_receipt`, ...)
  are written to `AuditLog`.
- `manage_results` now writes a `log_user_action` entry for every
  result create / update / delete / publish-state change.
- The audit log view (`/fees/audit-log/`) is restricted to superusers.

### 12. **File Uploads** ✅
- The bank-slip image upload (`BankPaymentReceiptForm`) validates
  size, declared MIME type, **and** magic bytes before accepting the
  file. The `deposit_slip` is rejected if its content does not look
  like a real JPEG or PNG.

## Testing the Security

### Test 1: Rate Limiting
```bash
# 6 failed logins within 60 seconds should now hard-block (HTTP 403)
# before the view runs at all. Use a fresh IP / cleared cookie store
# because django-ratelimit keys on IP.
```

### Test 2: Authorization
```bash
# Login as student, try accessing:
# - /accounts/teacher-dashboard/ → Should redirect
# - /accounts/admin-dashboard/ → Should redirect
# - /fees/audit-log/ → Should redirect (superuser only)
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

### Test 6: Audience ACL on announcements
```bash
# As a student, visit /announcements/5/ for a teacher-only
# announcement by id. Expected: 404.
```

## Environment Variables Required

Add these to `.env` for production:

```env
# Security
DEBUG=False
SECRET_KEY=<output of `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DBNAME
# or:
# DB_HOST=production-db-server
# DB_PASSWORD=production-password

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## To Generate a Secure Secret Key

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## To Create a Superuser

```bash
# Either set DJANGO_SUPERUSER_PASSWORD=<your-strong-password> and run:
python manage.py create_admin

# Or pass --password / --noinput explicitly.
```

## Additional Security Recommendations

### 1. **Enable 2FA (Two-Factor Authentication)**
```bash
pip install django-otp qrcode
```

### 2. **Configure a shared cache for rate limits**
django-ratelimit's default uses Django's `LocMemCache`, which is
per-process. In production configure `CACHES` to use Redis or
Memcached so the limit is global across workers.

### 3. **Database Security**
- Use strong PostgreSQL passwords
- Create separate database user (not `postgres` superuser)
- Enable SSL for database connections

### 4. **Deployment Security**
- Never run Django with `DEBUG=True` in production
- Use production WSGI server (Gunicorn, uWSGI)
- Keep Django and packages updated
- Run `python manage.py check --deploy`

### 5. **Logging & Monitoring**
- Audit log is restricted to superusers
- Log authentication failures
- Monitor for suspicious activity
- Set up alerts for failed login attempts

### 6. **Backup & Recovery**
- Regular database backups
- Encrypted backup storage
- Test recovery procedures

## Security Audit Checklist

- [x] Rate limiting on login (IP + username, hard-block)
- [x] Rate limiting on student registration
- [x] Role-based access control (superuser-gated admin)
- [x] Authorization checks on all views
- [x] HTTPS/SSL enforcement
- [x] XSS protection (auto-escape + content-type nosniff)
- [x] CSRF protection (explicit trusted origins)
- [x] SQL injection prevention (ORM + advisory locks)
- [x] Secret key management (mandatory in production)
- [x] Debug mode disabled in production
- [x] ALLOWED_HOSTS (no wildcards in production)
- [x] File-upload magic-byte verification
- [x] Audit trail (superuser-only view)
- [x] Account-enumeration hardening (random opaque passwords)
- [x] Announcement audience ACL on detail view
- [ ] 2FA implementation (recommended)
- [ ] External WAF / bot protection (recommended)

## Support

For security issues:
1. Don't commit secrets to version control
2. Rotate passwords regularly
3. Monitor access logs
4. Keep software updated
5. Test security changes in staging first

