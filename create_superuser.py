#!/usr/bin/env python
"""
Script to create a default admin user.
Run this locally: python create_superuser.py
"""
import os
import sys
import django

# Add the school_portal directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'school_portal'))

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_portal.settings')
django.setup()

from django.contrib.auth.models import User

def create_admin():
    """Create or update admin user"""
    username = 'admin'
    email = 'admin@example.com'
    password = 'admin123'
    
    user, created = User.objects.get_or_create(username=username)
    user.email = email
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    
    if created:
        print(f"✓ Admin user created successfully!")
    else:
        print(f"✓ Admin user already exists - password updated!")
    
    print(f"\nLogin credentials:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")

if __name__ == '__main__':
    create_admin()
