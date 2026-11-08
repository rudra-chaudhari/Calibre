import 'dart:math' as math;

import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_layout.dart';
import 'package:calibre/widgets/event_tile.dart';
import 'package:calibre/widgets/hour_grid.dart';
import 'package:flutter/material.dart';

class WeekGrid extends StatelessWidget {
  static const double gutterWidth = 64;
  static const int rows = 24;

  final List<DateTime> days;

  const WeekGrid({super.key, required this.days});

  CalendarEvent _toGridTime(CalendarEvent e) {
    final start = (e.startMin - HourGrid.startHour * 60) % 1440;
    var end = start + (e.endMin - e.startMin);
    if (end > 1440) end = 1440;
    return e.copyWith(startMin: start, endMin: end);
  }

  double _tileHeight(PlacedEvent p, double rowHeight) {
    return math.max(
      (p.event.endMin - p.event.startMin) / 60 * rowHeight - 2,
      24.0,
    );
  }

  Widget _dayColumn(
    DateTime day,
    bool isToday,
    double rowHeight,
    EventState events,
  ) {
    final raw = events.eventsForColumn(day);
    final byId = {for (final e in raw) e.id: e};
    final placed = layoutEvents([for (final e in raw) _toGridTime(e)]);

    return Container(
      decoration: BoxDecoration(
        color: isToday ? const Color(0x14F26D4A) : null,
        border: const Border(left: BorderSide(color: Colors.black12)),
      ),
      child: LayoutBuilder(
        builder: (context, box) {
          final width = box.maxWidth;
          return Stack(
            children: [
              Column(
                children: [
                  for (int i = 0; i < rows; i++)
                    Container(
                      height: rowHeight,
                      decoration: const BoxDecoration(
                        border: Border(top: BorderSide(color: Colors.black12)),
                      ),
                    ),
                ],
              ),
              for (final p in placed)
                Positioned(
                  top: p.event.startMin / 60 * rowHeight + 1,
                  left: width / p.columns * p.column + 2,
                  width: width / p.columns - 4,
                  height: _tileHeight(p, rowHeight),
                  child: EventTile(
                    event: byId[p.event.id]!,
                    height: _tileHeight(p, rowHeight),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final today = dateOnly(DateTime.now());
    final double rowHeight = HourGrid.hourHeight.toDouble();
    final events = EventScope.of(context);

    return SingleChildScrollView(
      child: SizedBox(
        height: rows * rowHeight,
        child: Row(
          children: [
            SizedBox(
              width: gutterWidth,
              child: Column(
                children: [
                  for (int i = 0; i < rows; i++)
                    SizedBox(
                      height: rowHeight,
                      child: Align(
                        alignment: Alignment.topCenter,
                        child: Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            hourlabel((HourGrid.startHour + i) % 24),
                            style: const TextStyle(
                              fontSize: 12,
                              color: Colors.black54,
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
            for (final day in days)
              Expanded(
                child: _dayColumn(day, isSameDay(day, today), rowHeight, events),
              ),
          ],
        ),
      ),
    );
  }
}