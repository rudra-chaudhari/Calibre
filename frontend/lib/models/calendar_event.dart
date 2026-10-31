class CalendarEvent {
  final String id;
  final String title;
  final DateTime date; 
  final int startMin; 
  final int endMin;
  final int colorIndex;
  final String calendarId;
  final String notes;

  const CalendarEvent({
    required this.id,
    required this.title,
    required this.date,
    required this.startMin,
    required this.endMin,
    required this.colorIndex,
    required this.calendarId,
    this.notes = '',
  });

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
    );
  }
}