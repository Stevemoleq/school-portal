# Logging System Implementation Guide

## Overview

A comprehensive logging system has been implemented for the School Portal Django application. This system tracks user actions, security events, database operations, and errors with structured logging to both console and file outputs.

---

## 📁 Files Added/Modified

### New Files Created
1. **`apps/core/logging_utils.py`** - Logging utility functions and decorators
2. **`apps/core/logging_middleware.py`** - HTTP request/response logging middleware
3. **`logs/`** - Directory for log files (created automatically)

### Files Modified
1. **`school_portal/settings.py`** - Added LOGGING configuration and middleware
2. **`apps/accounts/views.py`** - Added logging to authentication views
3. **`apps/results/views.py`** - Added logging to results views

---

## 🚀 How to Use

### 1. **Basic Logging (in any view or model)**

```python
import logging
from apps.core.logging_utils import log_user_action, log_security_event, log_database_operation

logger = logging.getLogger(__name__)

# Simple log message
logger.info("User action happened")
logger.warning("Something suspicious")
logger.error("An error occurred", exc_info=True)
```

### 2. **Log User Actions**

```python
from apps.core.logging_utils import log_user_action

# Log a user action
log_user_action(
    'Updated student profile',
    user=request.user,
    details={'student_id': 123, 'field': 'address'}
)
```

### 3. **Log Security Events**

```python
from apps.core.logging_utils import log_security_event, get_client_ip

# Log failed login attempt
log_security_event(
    'LOGIN_FAILED',
    user=attempted_user,
    ip_address=get_client_ip(request),
    details={'attempted_username': username}
)

# Log unauthorized access
log_security_event(
    'UNAUTHORIZED_ACCESS',
    user=request.user,
    ip_address=get_client_ip(request),
    details={'resource': 'admin_panel'}
)
```

### 4. **Log Database Operations**

```python
from apps.core.logging_utils import log_database_operation

# Log when a student is created
log_database_operation(
    'CREATE',
    'Student',
    user=request.user,
    details={'registration_number': 'REG-001', 'class': 'JSS1'}
)

# Log when results are deleted
log_database_operation(
    'DELETE',
    'Result',
    count=5,
    user=request.user,
    details={'term': '1st', 'session': '2024-2025'}
)
```

### 5. **Use the View Logger Decorator**

```python
from apps.core.logging_utils import view_logger

@view_logger
@login_required
def my_view(request):
    """This view will automatically log access and execution time"""
    return render(request, 'template.html')
```

---

## 📊 Log Output Levels

| Level | Used For | Color (Console) |
|-------|----------|-----------------|
| DEBUG | Detailed diagnostic info | Cyan |
| INFO | General informational messages | Blue |
| WARNING | Warning messages, security events | Yellow |
| ERROR | Error messages, exceptions | Red |
| CRITICAL | System critical failures | Red |

---

## 📂 Log Files

The system creates three log files in the `logs/` directory:

### 1. **`school_portal.log`** - General Application Log
- **Rotation**: Every 10MB (keeps 5 backups)
- **Minimum Level**: INFO
- **Contains**: All general application events
- **Example entries**:
  ```
  [INFO] 2024-01-15 10:30:45 | User admin logged in successfully from IP 192.168.1.1
  [INFO] 2024-01-15 10:31:12 | New student registered: REG-10023 (john@school.com)
  ```

### 2. **`security.log`** - Security Events Log
- **Rotation**: Every 10MB (keeps 5 backups)
- **Minimum Level**: WARNING
- **Contains**: Login attempts, unauthorized access, suspicious activities
- **Example entries**:
  ```
  [SECURITY: LOGIN_FAILED] User: Anonymous | IP: 203.0.113.45 | Details: {'attempted_username': 'invalid_user'}
  [SECURITY: UNAUTHORIZED_ACCESS] User: student1 | IP: 192.168.1.5 | Details: {'resource': 'teacher_results'}
  ```

### 3. **`errors.log`** - Error Log
- **Rotation**: Every 10MB (keeps 10 backups)
- **Minimum Level**: ERROR
- **Contains**: Exceptions, critical errors, stack traces
- **Example entries**:
  ```
  [ERROR] 2024-01-15 10:35:20 | Failed to save student profile
  Traceback (most recent call last):
    File "views.py", line 145, in update_student
      student.save()
  ...
  ```

---

## 🔍 Viewing Logs

### View Logs in Development (Console)
Logs automatically print to console during development:

```bash
# Start Django development server
python manage.py runserver

# You'll see logs in the terminal output
[INFO] 2024-01-15 10:30:45 | User admin logged in successfully
[WARNING] [SECURITY: LOGIN_FAILED] User: Anonymous
```

### View Log Files
```bash
# View general logs (last 50 lines)
tail -50 logs/school_portal.log

# View security logs in real-time
tail -f logs/security.log

# View error logs
cat logs/errors.log

# Search for specific entries
grep "LOGIN_FAILED" logs/security.log
grep "john@school.com" logs/school_portal.log
```

### On Windows (PowerShell)
```powershell
# View general logs (last 50 lines)
Get-Content logs/school_portal.log -Tail 50

# View security logs
Get-Content logs/security.log | Select-Object -Last 50

# Search for entries
Select-String "LOGIN_FAILED" logs/security.log
```

---

## 📝 Examples by Feature

### Student Login Tracking
```
[SECURITY: LOGIN_SUCCESS] User: john_doe (ID:15) | IP: 192.168.1.100 | Details: {'method': 'username/email'}
[INFO] 2024-01-15 10:30:45 | User john_doe logged in successfully from IP 192.168.1.100
```

### Failed Login Attempts
```
[SECURITY: LOGIN_FAILED] User: Anonymous | IP: 203.0.113.45 | Details: {'attempted_username': 'invalid_user'}
[WARNING] 2024-01-15 10:31:05 | Failed login attempt for username 'invalid_user' from IP 203.0.113.45
```

### Student Registration
```
[DB: CREATE] Student | Count: 1 | User: john_doe | Details: {'registration_number': 'REG-10023'}
[USER: john_doe (ID:16)] Student registered successfully | Details: {'registration_number': 'REG-10023'}
[INFO] 2024-01-15 10:32:20 | New student registered: REG-10023 (john@school.com)
```

### Unauthorized Access Attempts
```
[WARNING] 2024-01-15 10:35:10 | Access denied: User student1 attempted to access results without student profile
[SECURITY: UNAUTHORIZED_ACCESS] User: student1 | IP: 192.168.1.5
```

### Results View
```
[USER: john_doe (ID:15)] Viewed student results | Details: {'registration_number': 'REG-10023'}
[INFO] 2024-01-15 10:40:30 | User viewed results
```

---

## 🔧 Configuration

The logging configuration is in `school_portal/settings.py` under the `LOGGING` dictionary.

### Key Settings:
- **Log Level**: Set minimum level for each handler/logger
- **Rotation**: Files rotate when they reach 10MB
- **Backup Count**: How many backup files to keep
- **Format**: Customizable log message format

### Change Log Levels
To change the minimum log level for an app, edit `settings.py`:

```python
'apps.accounts': {
    'handlers': ['console', 'file', 'security_file'],
    'level': 'DEBUG',  # Change this: DEBUG, INFO, WARNING, ERROR, CRITICAL
    'propagate': False,
},
```

---

## ✅ Best Practices

1. **Always use structured logging**
   ```python
   # ✅ Good
   log_user_action('Updated profile', user=request.user, details={'field': 'email'})
   
   # ❌ Bad
   logger.info(f"User {request.user} updated {field}")
   ```

2. **Log security-related events explicitly**
   ```python
   # ✅ Always log login/logout attempts
   log_security_event('LOGIN_SUCCESS', user=user, ip_address=ip)
   ```

3. **Include context for debugging**
   ```python
   # ✅ Good - includes relevant details
   log_error_with_context(
       str(e),
       error_type='STUDENT_UPDATE_ERROR',
       user=request.user,
       request_data={'student_id': student_id}
   )
   ```

4. **Use appropriate log levels**
   ```python
   logger.debug("Detailed diagnostic info")      # Development only
   logger.info("Important user actions")         # Normal operations
   logger.warning("Suspicious activities")       # Security concerns
   logger.error("Something went wrong")          # Errors that need attention
   ```

5. **Never log sensitive data**
   ```python
   # ❌ Bad - don't log passwords
   logger.info(f"User login: {username}:{password}")
   
   # ✅ Good - log only what's needed
   log_security_event('LOGIN_SUCCESS', user=user)
   ```

---

## 🔐 Security Considerations

- **Logs contain sensitive information** → Keep log files secure
- **Rotate logs regularly** → Prevents excessive disk usage
- **Monitor security.log** → Watch for suspicious activities
- **Don't expose logs to users** → Keep logs server-side only
- **Archive old logs** → For compliance and auditing

---

## 📈 Monitoring & Analysis

### Quick Statistics
```bash
# Count login attempts per day
grep "LOGIN_" logs/security.log | wc -l

# Find all errors
grep "ERROR" logs/errors.log

# Find errors from specific user
grep "user_email" logs/errors.log
```

### Automated Monitoring
For production, consider:
- **Sentry** - Error tracking and monitoring
- **LogStash** - Centralized logging
- **New Relic** - Application performance monitoring
- **CloudWatch** (AWS) - Log aggregation

---

## 🚨 Troubleshooting

**Q: Logs are not appearing?**
- Check if `DEBUG = True` in development
- Verify log directory has write permissions
- Check console for import errors

**Q: Log files are too large?**
- Rotation is automatic (10MB), but old archives can be deleted
- Reduce log level in settings.py

**Q: Can't find specific log entries?**
```bash
# Search across all logs
grep -r "search_term" logs/

# Search with context
grep -C 5 "error_keyword" logs/school_portal.log
```

---

## 📚 Related Documentation

- [Django Logging Documentation](https://docs.djangoproject.com/en/5.1/topics/logging/)
- [Python Logging Module](https://docs.python.org/3/library/logging.html)
- [Django Security](https://docs.djangoproject.com/en/5.1/topics/security/)

---

## 🎯 Next Steps

1. Review logs periodically for suspicious activity
2. Set up log rotation for production
3. Consider centralizing logs for multi-server deployments
4. Add logging to remaining views as needed
5. Implement log analysis/alerting system
