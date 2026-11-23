from django.contrib import admin

from .models import MoodleConnection


@admin.register(MoodleConnection)
class MoodleConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "moodle_userid", "last_synced_at", "last_error")
    list_filter = ("status",)
    readonly_fields = ("token_encrypted",)
