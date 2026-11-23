from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "due_at")
    list_filter = ("status", "source")
    search_fields = ("title", "notes")
