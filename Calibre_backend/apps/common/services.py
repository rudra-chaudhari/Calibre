from django.db import transaction

from .models import Category


DEFAULT_CATEGORIES = [
    {"name": "Academics", "color": "#3B82F6", "sort_order": 0},
    {"name": "Work", "color": "#8B5CF6", "sort_order": 1},
    {"name": "Personal", "color": "#EC4899", "sort_order": 2},
    {"name": "Health & Fitness", "color": "#10B981", "sort_order": 3},
    {"name": "Social", "color": "#F59E0B", "sort_order": 4},
    {"name": "Finance", "color": "#14B8A6", "sort_order": 5},
    {"name": "Chores", "color": "#6B7280", "sort_order": 6},
    {"name": "Leisure", "color": "#EF4444", "sort_order": 7},
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
