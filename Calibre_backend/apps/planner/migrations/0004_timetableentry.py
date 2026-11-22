# Generated migration for TimetableEntry model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0003_courseschedule_deletedevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='TimetableEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department', models.CharField(max_length=10)),
                ('course_code', models.CharField(max_length=50)),
                ('section', models.CharField(blank=True, default='', max_length=10)),
                ('weekday', models.PositiveSmallIntegerField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('room', models.CharField(blank=True, default='', max_length=100)),
                ('instructor', models.CharField(blank=True, default='', max_length=200)),
                ('marker', models.CharField(blank=True, default='', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'planner_timetableentry',
                'ordering': ['weekday', 'start_time', 'course_code'],
            },
        ),
        migrations.AddConstraint(
            model_name='timetableentry',
            constraint=models.UniqueConstraint(
                fields=('department', 'course_code', 'section', 'weekday', 'start_time', 'end_time', 'instructor'),
                name='uniq_timetable_slot',
            ),
        ),
        migrations.AddIndex(
            model_name='timetableentry',
            index=models.Index(fields=['course_code'], name='timetable__course__idx'),
        ),
        migrations.AddIndex(
            model_name='timetableentry',
            index=models.Index(fields=['weekday', 'start_time'], name='timetable__weekda_idx'),
        ),
    ]
