import 'dart:math' as math;

import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:flutter/material.dart';

class MonthScreen extends StatelessWidget {
  final DateTime date;
  final ValueChanged<DateTime> onDay;

  const MonthScreen({super.key, required this.date, required this.onDay});

  Widget _chip(EventState events, CalendarEvent e) {
    final pal =
        events.colorFor(e) ?? eventPalette[e.colorIndex % eventPalette.length];
    final title = events.isDone(e) ? '✓ ${e.title}' : e.title;
    return Container(
      height: 30,
      margin: const EdgeInsets.only(bottom: 3),
      padding: const EdgeInsets.symmetric(horizontal: 10),
      alignment: Alignment.centerLeft,
      decoration: BoxDecoration(
        color: pal.bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: pal.fg,
        ),
      ),
    );
  }

  Widget _cell(EventState events, DateTime day, DateTime today) {
    final inMonth = day.month == date.month;
    final isToday = isSameDay(day, today);
    final items = events.eventsOn(day);

    Color dayColor = Colors.black87;
    if (isToday) {
      dayColor = Colors.white;
    } else if (!inMonth) {
      dayColor = Colors.black38;
    }

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => onDay(day),
      child: Container(
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: isToday ? const Color(0x14F26D4A) : null,
          border: const Border(
            left: BorderSide(color: Colors.black12),
            top: BorderSide(color: Colors.black12),
          ),
        ),
        child: LayoutBuilder(
          builder: (context, box) {
            final fit = math.max(((box.maxHeight - 34) / 33).floor(), 0);
            int shown = items.length;
            if (items.length > fit) shown = math.max(fit - 1, 0);

            return SingleChildScrollView(
              physics: const NeverScrollableScrollPhysics(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: isToday ? const Color(0xFFF26D4A) : null,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '${day.day}',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: dayColor,
                      ),
                    ),
                  ),
                  const SizedBox(height: 3),
                  for (final e in items.take(shown)) _chip(events, e),
                  if (items.length > shown)
                    Padding(
                      padding: const EdgeInsets.only(left: 4),
                      child: Text(
                        '+${items.length - shown} more',
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFFF26D4A),
                        ),
                      ),
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _weekdayHeader() {
    final names = <Widget>[];
    for (final name in weekdaynames) {
      names.add(
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Center(
              child: Text(
                name,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.black54,
                ),
              ),
            ),
          ),
        ),
      );
    }
    return Row(children: names);
  }

  @override
  Widget build(BuildContext context) {
    final events = EventScope.of(context);
    final start = startofweek(DateTime(date.year, date.month, 1));
    final today = dateOnly(DateTime.now());

    final weeks = <Widget>[];
    for (int w = 0; w < 6; w++) {
      final cells = <Widget>[];
      for (int d = 0; d < 7; d++) {
        final day = addDays(start, w * 7 + d);
        cells.add(Expanded(child: _cell(events, day, today)));
      }
      weeks.add(
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: cells,
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          children: [
            _weekdayHeader(),
            Expanded(child: Column(children: weeks)),
          ],
        ),
      ),
    );
  }
}