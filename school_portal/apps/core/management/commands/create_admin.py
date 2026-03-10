from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Creates or updates default admin user'

    def handle(self, *args, **options):
        try:
            user, created = User.objects.get_or_create(username='admin')
            user.set_password('admin123')
            user.email = 'admin@example.com'
            user.is_staff = True
            user.is_superuser = True
            user.save()
            
            if created:
                self.stdout.write(self.style.SUCCESS('✓ Admin user created: admin / admin123'))
            else:
                self.stdout.write(self.style.SUCCESS('✓ Admin password updated: admin / admin123'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error creating admin user: {str(e)}'))

