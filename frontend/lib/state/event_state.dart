import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/widgets/hour_grid.dart';
import 'package:flutter/material.dart';

class EventState extends ChangeNotifier {
  final List<CalendarEvent> _events = [];
  int _nextId = 1;

  String newId() => 'e${_nextId++}';

  List<CalendarEvent> eventsForColumn(DateTime day) {
    final cut = HourGrid.startHour * 60;
    final nextDay = addDays(day, 1);
    return _events.where((e) {
      final sameDayDaytime = isSameDay(e.date, day) && e.startMin >= cut;
      final nextDayEarly = isSameDay(e.date, nextDay) && e.startMin < cut;
      return sameDayDaytime || nextDayEarly;
    }).toList();
  }

  void add(CalendarEvent event) {
    _events.add(event.copyWith(date: dateOnly(event.date)));
    notifyListeners();
  }
}

class EventScope extends InheritedNotifier<EventState> {
  const EventScope({
    super.key,
    required EventState state,
    required super.child,
  }) : super(notifier: state);

  static EventState of(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<EventScope>()!.notifier!;
  }
}