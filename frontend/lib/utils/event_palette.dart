import 'package:flutter/painting.dart';

class EventColor {
  final String name;
  final Color bg;
  final Color fg;
  const EventColor(this.name, this.bg, this.fg);
}

const List<EventColor> eventPalette = [
  EventColor('Lavender', Color(0xFFE3D9FB), Color(0xFF4B3A8C)),
  EventColor('Peach', Color(0xFFFFE0CF), Color(0xFF8A4A2B)),
  EventColor('Mint', Color(0xFFD3F2E3), Color(0xFF1F6B4F)),
  EventColor('Sky', Color(0xFFD6E9FB), Color(0xFF1F5A8C)),
  EventColor('Rose', Color(0xFFFBD9E3), Color(0xFF8F2F4F)),
  EventColor('Butter', Color(0xFFFBF0C4), Color(0xFF7A6414)),
];

class CalendarInfo {
  final String id;
  final String name;
  final int colorIndex;
  const CalendarInfo(this.id, this.name, this.colorIndex);
}

const List<CalendarInfo> defaultCalendars = [
  CalendarInfo('personal', 'Personal', 0),
  CalendarInfo('academic', 'Academic', 3),
];

CalendarInfo calendarById(String id) {
  return defaultCalendars.firstWhere(
    (c) => c.id == id,
    orElse: () => defaultCalendars.first,
  );
}