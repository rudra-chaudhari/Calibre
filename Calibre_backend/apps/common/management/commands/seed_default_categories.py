from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.common.services import seed_default_categories

User = get_user_model()


class Command(BaseCommand):
    help = "Seed default categories for all users (for users who signed up before this app existed)"

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            seed_default_categories(user)
        self.stdout.write(
            self.style.SUCCESS(f"Seeded default categories for {users.count()} users")
        )
