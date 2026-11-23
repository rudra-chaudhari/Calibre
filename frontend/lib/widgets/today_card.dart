import 'dart:async';

import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:flutter/material.dart';

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

String _span(int minutes) {
  if (minutes < 60) return '$minutes min';
  final h = minutes ~/ 60;
  final m = minutes % 60;
  if (m == 0) return '${h}h';
  return '${h}h ${m}m';
}

class TodayCard extends StatefulWidget {
  const TodayCard({super.key});

  @override
  State<TodayCard> createState() => _TodayCardState();
}

class _TodayCardState extends State<TodayCard> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(minutes: 1), (_) => _tick());
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _refresh() {
    if (!mounted) return;
    EventScope.of(context).loadUpcoming().catchError((_) {});
  }

  void _tick() {
    if (!mounted) return;
    final day = EventScope.of(context).upcomingDay;
    if (day == null || !isSameDay(day, DateTime.now())) _refresh();
    setState(() {});
  }

  List<CalendarEvent> _on(EventState events, DateTime day, bool tasks) {
    final list = events.upcoming
        .where((e) => isSameDay(e.date, day) && isTask(e) == tasks)
        .toList();
    list.sort((a, b) => a.startMin.compareTo(b.startMin));
    return list;
  }

  Widget _dot(CalendarEvent e) {
    final pal = eventPalette[e.colorIndex % eventPalette.length];
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(color: pal.fg, shape: BoxShape.circle),
    );
  }

  Widget _label(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 14, bottom: 4),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
          color: Colors.black54,
        ),
      ),
    );
  }

  Widget _note(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Text(
        text,
        style: const TextStyle(fontSize: 13, color: Colors.black54),
      ),
    );
  }

  Widget _focus(
    EventState events,
    CalendarEvent e,
    String tag,
    String sub,
    DateTime day,
  ) {
    return InkWell(
      onTap: () => events.openDay?.call(day),
      child: Padding(
        padding: const EdgeInsets.only(top: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              tag,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: Color(0xFFF26D4A),
              ),
            ),
            const SizedBox(height: 2),
            Row(
              children: [
                _dot(e),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    e.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.only(left: 16),
              child: Text(
                sub,
                style: const TextStyle(fontSize: 12, color: Colors.black54),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _line(EventState events, CalendarEvent e, DateTime day, String time) {
    return InkWell(
      onTap: () => events.openDay?.call(day),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          children: [
            _dot(e),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                e.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              time,
              style: const TextStyle(fontSize: 12, color: Colors.black54),
            ),
          ],
        ),
      ),
    );
  }

  Widget _taskRow(EventState events, CalendarEvent task) {
    final done = events.upcomingDone(task);
    TextDecoration? decoration;
    if (done) decoration = TextDecoration.lineThrough;

    return Row(
      children: [
        SizedBox(
          width: 28,
          height: 28,
          child: Checkbox(
            value: done,
            visualDensity: VisualDensity.compact,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            onChanged: (value) {
              guarded(context, () => events.setTaskDone(task, value == true));
            },
          ),
        ),
        const SizedBox(width: 4),
        Expanded(
          child: Text(
            task.title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 13, decoration: decoration),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          timelabel(task.startMin),
          style: const TextStyle(fontSize: 12, color: Colors.black54),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final events = EventScope.of(context);
    final now = DateTime.now();
    final today = dateOnly(now);
    final tomorrow = addDays(today, 1);
    final nowMin = now.hour * 60 + now.minute;

    final todayEvents = _on(events, today, false);
    final todayTasks = _on(events, today, true);
    final tomorrowEvents = _on(events, tomorrow, false);
    final tomorrowTasks = _on(events, tomorrow, true);

    CalendarEvent? current;
    CalendarEvent? next;
    for (final e in todayEvents) {
      if (e.startMin <= nowMin && nowMin < e.endMin) {
        current ??= e;
      } else if (e.startMin > nowMin) {
        next ??= e;
      }
    }

    final eventsLeft = todayEvents.where((e) => e.endMin > nowMin).length;
    final tasksLeft = todayTasks.where((t) => !events.upcomingDone(t)).length;
    final total = eventsLeft + tasksLeft;
    String things = 'things';
    if (total == 1) things = 'thing';
    final weekday = _weekdays[today.weekday - 1];
    final month = _months[today.month - 1];

    final children = <Widget>[
      Text(
        '$weekday ${today.day} $month · $total $things',
        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
      ),
    ];

    if (current != null) {
      children.add(
        _focus(events, current, 'NOW', '${_span(current.endMin - nowMin)} left', today),
      );
    }
    if (next != null) {
      final sub = 'in ${_span(next.startMin - nowMin)} · ${timelabel(next.startMin)}';
      children.add(_focus(events, next, 'NEXT UP', sub, today));
    }
    if (current == null && next == null) {
      children.add(_note('No more events today'));
    }

    if (todayTasks.isNotEmpty) {
      children.add(_label('DUE TODAY'));
      for (final t in todayTasks) {
        children.add(_taskRow(events, t));
      }
    }

    children.add(_label('TOMORROW'));
    final shownEvents = tomorrowEvents.take(2).toList();
    final shownTasks = tomorrowTasks.take(3).toList();
    final extra = tomorrowEvents.length -
        shownEvents.length +
        tomorrowTasks.length -
        shownTasks.length;

    if (tomorrowEvents.isEmpty && tomorrowTasks.isEmpty) {
      children.add(const Text(
        'Nothing planned',
        style: TextStyle(fontSize: 13, color: Colors.black54),
      ));
    }
    for (final e in shownEvents) {
      children.add(_line(events, e, tomorrow, timelabel(e.startMin)));
    }
    for (final t in shownTasks) {
      children.add(_line(events, t, tomorrow, 'due ${timelabel(t.startMin)}'));
    }
    if (extra > 0) {
      children.add(
        InkWell(
          onTap: () => events.openDay?.call(tomorrow),
          child: Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '+$extra more',
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: Color(0xFFF26D4A),
              ),
            ),
          ),
        ),
      );
    }

    return SingleChildScrollView(
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0x338A5A2B),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: children,
        ),
      ),
    );
  }
}