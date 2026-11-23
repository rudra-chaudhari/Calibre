from rest_framework import serializers


class ConnectSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=2000, required=True)


class StatusSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    moodle_userid = serializers.IntegerField(allow_null=True)
    last_synced_at = serializers.DateTimeField(allow_null=True)
    last_error = serializers.CharField()
    imported = serializers.DictField()


class SyncSummarySerializer(serializers.Serializer):
    tasks = serializers.DictField()
    events = serializers.DictField()
    course_events = serializers.DictField(required=False)
    synced_at = serializers.DateTimeField()
    window = serializers.DictField()
