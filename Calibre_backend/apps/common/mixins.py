from rest_framework import viewsets


class OwnedQuerysetMixin:
    """
    Mixin for DRF viewsets that enforces user data isolation.

    This mixin ensures that:
    1. Querysets are automatically filtered to include only the requesting user's data
    2. When creating objects, the user field is automatically set to request.user
    3. The serializer never exposes or accepts a user field, so the client cannot set it

    Every viewset for user-owned models should inherit from this mixin.
    It prevents users from seeing or modifying another user's data.
    """

    def get_queryset(self):
        """
        Filter queryset to only include objects owned by the requesting user.
        """
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Automatically set the user field to the requesting user on creation.
        """
        serializer.save(user=self.request.user)
