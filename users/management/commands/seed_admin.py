"""Management command to create initial admin user."""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create initial admin superuser if it does not exist'

    def handle(self, *args, **options):
        username = 'benjoabrasado25'
        email = 'benjo@zcasoftwares.com'
        password = 'Caelum@2024_'

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'Admin user "{username}" already exists.')
            )
            return

        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name='Benjo',
                last_name='Abrasado',
                is_host=True,
            )
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created admin user "{username}"')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create admin user: {e}')
            )
