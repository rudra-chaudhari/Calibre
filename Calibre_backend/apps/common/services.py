from django.db import transaction

from .models import Category


DEFAULT_CATEGORIES = [
    {"name": "Personal", "color": "#EC4899", "sort_order": 0},
    {"name": "Academics", "color": "#3B82F6", "sort_order": 1},
]


@transaction.atomic
def seed_default_categories(user):
    """
    Create default categories for a user, idempotently.
    Skips any category name the user already has.
    Uses bulk_create for efficiency.
    """
    existing_names = set(
        Category.objects.filter(user=user).values_list("name", flat=True)
    )
    categories_to_create = []

    for cat in DEFAULT_CATEGORIES:
        if cat["name"] not in existing_names:
            categories_to_create.append(
                Category(
                    user=user,
                    name=cat["name"],
                    color=cat["color"],
                    sort_order=cat["sort_order"],
                    is_default=True,
                )
            )

    if categories_to_create:
        Category.objects.bulk_create(categories_to_create)
