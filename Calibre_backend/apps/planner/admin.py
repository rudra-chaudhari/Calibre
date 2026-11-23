from django.contrib import admin

from .models import Event, Routine, RoutineCheckin, TimetableEntry


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "start_at", "end_at", "source")
    list_filter = ("kind", "source")
    search_fields = ("title",)


@admin.register(Routine)
class RoutineAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_active", "start_date", "end_date")
    list_filter = ("is_active",)
    search_fields = ("title",)


@admin.register(RoutineCheckin)
class RoutineCheckinAdmin(admin.ModelAdmin):
    list_display = ("routine", "user", "date", "done")
    list_filter = ("done",)


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ("course_code", "department", "section", "weekday", "start_time", "end_time", "room", "instructor")
    list_filter = ("department", "weekday")
    search_fields = ("course_code", "instructor", "room")
