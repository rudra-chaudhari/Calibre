from django.db import transaction

from .models import User


@transaction.atomic
def register_user(email, password, name="") -> User:
    user = User.objects.create_user(email=email, password=password, name=name)
    # TODO(common): seed default categories here once the common app exists
    return user
