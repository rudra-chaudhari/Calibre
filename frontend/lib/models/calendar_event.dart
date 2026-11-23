import 'package:calibre/utils/date_utils.dart';

class RepeatRule {
  final String freq;
  final List<int> weekdays;
  final DateTime until;

  const RepeatRule(this.freq, this.weekdays, this.until);

  Map<String, dynamic> toJson() {
    return {
      'freq': freq,
      if (freq == 'weekly') 'weekdays': weekdays,
      'until': isoDate(until),
    };
  }
}

class CalendarEvent {
  final String id;
  final String title;
  final DateTime date; 
  final int startMin; 
  final int endMin;
  final int colorIndex;
  final String calendarId;
  final String notes;
  final String source;
  final String externalId;
  final String? seriesId;

  const CalendarEvent({
    required this.id,
    required this.title,
    required this.date,
    required this.startMin,
    required this.endMin,
    required this.colorIndex,
    required this.calendarId,
    this.notes = '',
    this.source = 'manual',
    this.externalId = '',
    this.seriesId,
  });

  factory CalendarEvent.fromJson(
    Map<String, dynamic> json, {
    required String calendarId,
    required int colorIndex,
  }) {
    final start = DateTime.parse(json['start_at'] as String).toLocal();
    final end = DateTime.parse(json['end_at'] as String).toLocal();
    final startMin = start.hour * 60 + start.minute;
     return CalendarEvent(
      id: json['id'].toString(),
      title: json['title'].toString(),
      date: dateOnly(start),
      startMin: startMin,
      endMin: startMin + end.difference(start).inMinutes,
      colorIndex: colorIndex,
      calendarId: calendarId,
      notes: (json['notes'] ?? json['description'] ?? '').toString(),
      source: (json['source'] ?? 'manual').toString(),
      externalId: (json['external_id'] ?? '').toString(),
      seriesId: json['series_id']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    final start = DateTime(date.year, date.month, date.day, 0, startMin);
    final end = DateTime(date.year, date.month, date.day, 0, endMin);
    return {
      'title': title,
      'notes': notes,
      'start_at': start.toUtc().toIso8601String(),
      'end_at': end.toUtc().toIso8601String(),
    };
  }

  CalendarEvent copyWith({
    String? title,
    DateTime? date,
    int? startMin,
    int? endMin,
    int? colorIndex,
    String? calendarId,
    String? notes,
  }) {
    return CalendarEvent(
      id: id,
      title: title ?? this.title,
      date: date ?? this.date,
      startMin: startMin ?? this.startMin,
      endMin: endMin ?? this.endMin,
      colorIndex: colorIndex ?? this.colorIndex,
      calendarId: calendarId ?? this.calendarId,
      notes: notes ?? this.notes,
      source: source,
      externalId: externalId,
      seriesId: seriesId,
    );
  }
}