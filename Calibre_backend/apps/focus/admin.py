from django.contrib import admin

from .models import FocusSession


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "status", "started_at", "actual_min")
    list_filter = ("status", "kind")
    search_fields = ("what_worked", "what_didnt")
