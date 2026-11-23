# Generated migration for course schedule and deleted event models

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
        ('planner', '0002_externalevent_event_series_id_alter_event_source_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course_code', models.CharField(max_length=50, unique=True)),
                ('course_name', models.CharField(max_length=200)),
                ('slot', models.CharField(max_length=20)),
                ('weekdays', models.JSONField(default=list)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('venue', models.CharField(blank=True, max_length=200)),
                ('semester_start', models.DateField()),
                ('semester_end', models.DateField()),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'course_schedule',
                'ordering': ['course_code', 'slot'],
            },
        ),
        migrations.AddIndex(
            model_name='courseschedule',
            index=models.Index(fields=['course_code'], name='course_sch_course__idx'),
        ),
        migrations.AddIndex(
            model_name='courseschedule',
            index=models.Index(fields=['slot'], name='course_sch_slot_idx'),
        ),
        migrations.CreateModel(
            name='DeletedEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.ForeignKey(on_delete=models.CASCADE, related_name='planner_deletedevent_set', to=settings.AUTH_USER_MODEL)),
                ('source', models.CharField(max_length=10)),
                ('external_id', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'planner_deletedevent',
            },
        ),
        migrations.AddConstraint(
            model_name='deletedevent',
            constraint=models.UniqueConstraint(fields=('user', 'source', 'external_id'), name='uniq_deleted_event'),
        ),
        migrations.AddIndex(
            model_name='deletedevent',
            index=models.Index(fields=['user', 'source'], name='deleted_eve_user_s_idx'),
        ),
    ]
