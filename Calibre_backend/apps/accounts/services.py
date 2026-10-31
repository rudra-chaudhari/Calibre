from django.db import transaction

from .models import User


@transaction.atomic
def register_user(email, password, name="") -> User:
    user = User.objects.create_user(email=email, password=password, name=name)
    from apps.common.services import seed_default_categories

    seed_default_categories(user)
    return user
