import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/services/api_exception.dart';
import 'package:calibre/services/auth_service.dart';
import 'package:calibre/services/token_storage.dart';
import 'package:calibre/state/auth_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:calibre/widgets/hour_grid.dart';
import 'package:flutter/material.dart';

enum CalendarTab { mine, dept, insti }

bool isTask(CalendarEvent e) {
  return e.id.startsWith('task-');
}

DateTime _startOf(CalendarEvent e) {
  return DateTime(e.date.year, e.date.month, e.date.day, 0, e.startMin);
}

DateTime _endOf(CalendarEvent e) {
  return DateTime(e.date.year, e.date.month, e.date.day, 0, e.endMin);
}

bool eventsOverlap(CalendarEvent a, CalendarEvent b) {
  return _startOf(a).isBefore(_endOf(b)) && _endOf(a).isAfter(_startOf(b));
}

String _utc(DateTime d) {
  return DateTime(d.year, d.month, d.day).toUtc().toIso8601String();
}

Future<void> guarded(
  BuildContext context,
  Future<void> Function() action,
) async {
  final messenger = ScaffoldMessenger.of(context);
  final auth = AuthScope.of(context);
  try {
    await action();
  } on ApiException catch (e) {
    if (e.statusCode == 401) {
      await auth.signOut();
    } else {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    }
  } catch (e) {
    messenger.showSnackBar(SnackBar(content: Text('$e')));
  }
}

class EventState extends ChangeNotifier {
  final AuthService _api = AuthService(TokenStorage());
  final Map<String, int> _categoryIds = {};
  final Set<String> _done = {};
  final Set<String> _upDone = {};
  List<CalendarEvent> _mine = [];
  List<CalendarEvent> _tasks = [];
  List<CalendarEvent> _other = [];
  List<CalendarEvent> _upcoming = [];
  List<Map<String, dynamic>>? _timetable;
  DateTime _from = startofweek(DateTime.now());
  int _days = 7;
  CalendarTab tab = CalendarTab.mine;
  DateTime? upcomingDay;
  void Function(DateTime day)? openDay;

  List<CalendarEvent> get upcoming => _upcoming;

  void setTab(CalendarTab value) {
    tab = value;
    _other = [];
    notifyListeners();
  }

  Future<void> reload() async {
    await load(_from, _days);
    await loadUpcoming();
  }

  Future<void> load(DateTime from, int days) async {
    final shown = tab;
    _from = from;
    _days = days;
    await _loadCategories();

    final to = addDays(from, days);
    final range =
        'start_date=${isoDate(from)}&end_date=${isoDate(to)}&page_size=200';
    final mine = await _fetch('/events/?$range');

    List<Map<String, dynamic>> tasks = [];
    List<Map<String, dynamic>> other = [];
    if (shown == CalendarTab.mine) {
      final taskRange =
          'due_after=${_utc(from)}&due_before=${_utc(to)}&page_size=200';
      tasks = await _fetch('/tasks/?$taskRange');
    } else {
      final source = shown == CalendarTab.dept ? 'cse' : 'insti';
      other = await _fetch('/external-events/?source=$source&$range');
    }

    if (!isSameDay(_from, from) || _days != days || tab != shown) return;

    final otherId = shown == CalendarTab.dept ? 'dept' : 'insti';
    _mine = [];
    for (final j in mine) {
      _mine.add(_mineFrom(j));
    }
    _tasks = [];
    _done.clear();
    for (final j in tasks) {
      _tasks.add(_taskFrom(j));
      if (j['status'] == 'done') _done.add('task-${j['id']}');
    }
    _other = [];
    for (final j in other) {
      _other.add(CalendarEvent.fromJson(j, calendarId: otherId, colorIndex: 0));
    }
    notifyListeners();
  }

  Future<void> loadUpcoming() async {
    await _loadCategories();
    final today = dateOnly(DateTime.now());
    final to = addDays(today, 2);
    final range =
        'start_date=${isoDate(today)}&end_date=${isoDate(to)}&page_size=200';
    final taskRange =
        'due_after=${_utc(today)}&due_before=${_utc(to)}&page_size=200';

    final events = await _fetch('/events/?$range');
    final tasks = await _fetch('/tasks/?$taskRange');

    _upcoming = [];
    _upDone.clear();
    for (final j in events) {
      _upcoming.add(_mineFrom(j));
    }
    for (final j in tasks) {
      _upcoming.add(_taskFrom(j));
      if (j['status'] == 'done') _upDone.add('task-${j['id']}');
    }
    upcomingDay = today;
    notifyListeners();
  }

  Future<void> add(CalendarEvent event, RepeatRule? repeat) async {
    await _loadCategories();
    final body = _body(event);
    if (repeat != null) body['repeat'] = repeat.toJson();
    await _api.postJson('/events/', body);
    await reload();
  }

  Future<List<Map<String, dynamic>>> loadTimetable() async {
    _timetable ??= await _fetch('/timetable/?page_size=200');
    return _timetable!;
  }

  Future<int> addCourses(
    List<Map<String, dynamic>> slots,
    DateTime until,
  ) async {
    await _loadCategories();

    final weekStart = startofweek(DateTime.now());
    final weekRange =
        'start_date=${isoDate(weekStart)}&end_date=${isoDate(addDays(weekStart, 7))}&page_size=200';
    final existing = <CalendarEvent>[];
    for (final j in await _fetch('/events/?$weekRange')) {
      existing.add(_mineFrom(j));
    }

    final groups = <String, List<Map<String, dynamic>>>{};
    for (final s in slots) {
      final key =
          '${s['course_code']}-${s['start_time']}-${s['end_time']}-${s['room']}-${s['section']}';
      groups.putIfAbsent(key, () => []).add(s);
    }

    int added = 0;
    for (final group in groups.values) {
      final first = group.first;
      final weekdays = <int>[];
      for (final s in group) {
        weekdays.add(s['weekday'] as int);
      }
      weekdays.sort();

      DateTime day = weekStart;
      while (!weekdays.contains(day.weekday - 1)) {
        day = addDays(day, 1);
      }
      if (day.isAfter(until)) continue;

      String title = first['course_code'].toString();
      final room = (first['room'] ?? '').toString();
      if (room.isNotEmpty) title = '$title · $room';

      final startMin = minutesOf(first['start_time'] as String);
      final endMin = minutesOf(first['end_time'] as String);

      final already = existing.any(
        (m) => m.title == title && m.startMin == startMin && m.endMin == endMin,
      );
      if (already) continue;

      final event = CalendarEvent(
        id: '',
        title: title,
        date: day,
        startMin: startMin,
        endMin: endMin,
        colorIndex: calendarById('academic').colorIndex,
        calendarId: 'academic',
        notes: (first['instructor'] ?? '').toString(),
      );

      final body = _body(event);
      body['repeat'] = RepeatRule('weekly', weekdays, until).toJson();
      await _api.postJson('/events/', body);
      added++;
    }
    return added;
  }

  Future<void> update(CalendarEvent event, String scope) async {
    Map<String, dynamic> body;
    if (scope == 'this') {
      body = _body(event);
    } else {
      body = {
        'title': event.title,
        'notes': event.notes,
        'category': _categoryIds[event.calendarId],
      };
    }
    await _api.patchJson('/events/${event.id}/?scope=$scope', body);
    await reload();
  }

  Future<void> remove(CalendarEvent event, String scope) async {
    await _api.deleteJson('/events/${event.id}/?scope=$scope');
    await reload();
  }

  Future<void> setTaskDone(CalendarEvent task, bool done) async {
    final id = task.id.substring(5);
    final action = done ? 'complete' : 'reopen';
    await _api.postJson('/tasks/$id/$action/', {});
    await reload();
  }

  Future<void> addToMine(CalendarEvent external) async {
    if (isAdded(external)) return;
    final data = await _api.postJson('/external-events/${external.id}/add/', {});
    _mine.add(_mineFrom(data));
    notifyListeners();
  }

  List<CalendarEvent> _source() {
    if (tab != CalendarTab.mine) return _other;
    final all = List<CalendarEvent>.from(_mine);
    all.addAll(_tasks);
    return all;
  }

  List<CalendarEvent> eventsForColumn(DateTime day) {
    final cut = HourGrid.startHour * 60;
    final nextDay = addDays(day, 1);
    return _source().where((e) {
      final sameDayDaytime = isSameDay(e.date, day) && e.startMin >= cut;
      final nextDayEarly = isSameDay(e.date, nextDay) && e.startMin < cut;
      return sameDayDaytime || nextDayEarly;
    }).toList();
  }

  List<CalendarEvent> eventsOn(DateTime day) {
    final list = _source().where((e) => isSameDay(e.date, day)).toList();
    list.sort((a, b) => a.startMin.compareTo(b.startMin));
    return list;
  }

  bool isDone(CalendarEvent e) {
    return _done.contains(e.id);
  }

  bool upcomingDone(CalendarEvent e) {
    return _upDone.contains(e.id);
  }

  bool isAdded(CalendarEvent e) {
    if (e.externalId.isEmpty) return false;
    return _mine.any((m) => _sameOrigin(m, e));
  }

  bool clashes(CalendarEvent e) {
    return _mine.any((m) => !_sameOrigin(m, e) && eventsOverlap(m, e));
  }

  EventColor? colorFor(CalendarEvent e) {
    if (tab == CalendarTab.mine) {
      if (e.endMin > e.startMin) return null;
      return isDone(e) ? freeColor : clashColor;
    }
    return clashes(e) ? clashColor : freeColor;
  }

  bool _sameOrigin(CalendarEvent a, CalendarEvent b) {
    return a.source == b.source && a.externalId == b.externalId;
  }

  Map<String, dynamic> _body(CalendarEvent e) {
    final body = e.toJson();
    body['category'] = _categoryIds[e.calendarId];
    return body;
  }

  CalendarEvent _mineFrom(Map<String, dynamic> json) {
    final category = json['category'];
    String calendarId = 'personal';
    if (category != null && category == _categoryIds['academic']) {
      calendarId = 'academic';
    }
    return CalendarEvent.fromJson(
      json,
      calendarId: calendarId,
      colorIndex: calendarById(calendarId).colorIndex,
    );
  }

  CalendarEvent _taskFrom(Map<String, dynamic> json) {
    final due = DateTime.parse(json['due_at'] as String).toLocal();
    final minutes = due.hour * 60 + due.minute;
    return CalendarEvent(
      id: 'task-${json['id']}',
      title: json['title'].toString(),
      date: dateOnly(due),
      startMin: minutes,
      endMin: minutes,
      colorIndex: calendarById('academic').colorIndex,
      calendarId: 'academic',
      notes: (json['notes'] ?? '').toString(),
      source: (json['source'] ?? 'manual').toString(),
      externalId: (json['external_id'] ?? '').toString(),
    );
  }

  Future<List<Map<String, dynamic>>> _fetch(String path) async {
    final all = <Map<String, dynamic>>[];
    int page = 1;
    while (true) {
      final data = await _api.getJson('$path&page=$page') as Map<String, dynamic>;
      all.addAll((data['results'] as List).cast<Map<String, dynamic>>());
      if (data['next'] == null) return all;
      page++;
    }
  }

  Future<void> _loadCategories() async {
    if (_categoryIds.isNotEmpty) return;
    final data = await _api.getJson('/categories/');
    final list = data is List ? data : data['results'] as List;
    for (final c in list) {
      final name = (c['name'] as String).toLowerCase();
      if (name == 'personal') _categoryIds['personal'] = c['id'] as int;
      if (name == 'academics') _categoryIds['academic'] = c['id'] as int;
    }
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