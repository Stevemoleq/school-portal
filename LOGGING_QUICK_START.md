# Logging System - Quick Reference

## ✅ What's Been Implemented

### 1. **Logging Utilities** (`apps/core/logging_utils.py`)
- `log_user_action()` - Log user actions with context
- `log_security_event()` - Log security-related events
- `log_database_operation()` - Log DB create/update/delete
- `log_error_with_context()` - Log errors with full context
- `@view_logger` - Decorator to auto-log view access & execution time
- `get_client_ip()` - Extract client IP from request

### 2. **Logging Middleware** (`apps/core/logging_middleware.py`)
- Auto-logs all HTTP requests and responses
- Tracks execution time
- Records user, IP address, and status code
- Skips static/media files

### 3. **Log Files** (in `logs/` directory)
- **school_portal.log** - General application logs
- **security.log** - Security events (login attempts, unauthorized access)
- **errors.log** - Error stack traces and exceptions

### 4. **Integrated Logging in Views**
- ✅ `apps/accounts/views.py` - Login, registration, profile updates
- ✅ `apps/results/views.py` - Results access tracking
- (Other apps ready for logging integration)

---

## 🚀 Quick Start Usage

### Import & Use in Views
```python
import logging
from apps.core.logging_utils import log_user_action, log_security_event

logger = logging.getLogger(__name__)

# Log user action
log_user_action('Deleted a class', user=request.user, details={'class_id': 5})

# Log security event
log_security_event('UNAUTHORIZED_ACCESS', user=request.user, ip_address='192.168.1.1')

# Simple log
logger.info("Something important happened")
logger.error("An error occurred", exc_info=True)
```

### Use View Logger Decorator
```python
from apps.core.logging_utils import view_logger

@view_logger
@login_required
def my_view(request):
    return render(request, 'template.html')
```

---

## 📊 Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed info during development |
| INFO | Important actions (logins, registrations) |
| WARNING | Suspicious activities, security alerts |
| ERROR | Exceptions and failures |

---

## 📂 View Logs

### Live Console Output (Development)
```bash
python manage.py runserver  # Logs appear in terminal
```

### View Log Files
```bash
# Last 50 lines of general log
tail -50 logs/school_portal.log

# Real-time security log
tail -f logs/security.log

# All errors
cat logs/errors.log
```

---

## 🔧 Configuration

**Location**: `school_portal/settings.py` → `LOGGING` dict

**Change log levels**:
```python
'apps.accounts': {
    'level': 'DEBUG',  # Change to: DEBUG, INFO, WARNING, ERROR
},
```

---

## 📝 Where It's Already Used

✅ **Login Attempts** - Success/failure with IP logged to `security.log`
✅ **Student Registration** - New registrations logged with email
✅ **Results Access** - Student results views logged
✅ **Profile Updates** - Changes tracked with user details

---

## 📚 Full Guide

See **LOGGING_GUIDE.md** for comprehensive documentation including:
- Advanced usage examples
- Best practices
- Monitoring & analysis
- Troubleshooting
- Security considerations

---

## 🎯 Next Steps

1. **Test it**: Start the dev server and check `logs/` folder
2. **Review**: Check `logs/security.log` for security events
3. **Extend**: Add logging to remaining views/models
4. **Monitor**: Set up alerts for errors in production
5. **Archive**: Implement log rotation/archiving strategy

---

## ✨ Key Benefits

✅ **Debug Issues** - Full context when errors occur
✅ **Security** - Track login attempts and unauthorized access
✅ **Audit Trail** - See who did what and when
✅ **Performance** - Track slow requests
✅ **Compliance** - Document all important actions

