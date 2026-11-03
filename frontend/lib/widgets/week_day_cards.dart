import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/widgets/week_grid.dart';
import 'package:flutter/material.dart';

class WeekDayCards extends StatelessWidget {
  final List<DateTime> days;

  const WeekDayCards({super.key, required this.days});

  @override
  Widget build(BuildContext context) {
    final today = dateOnly(DateTime.now());
    return Row(
      children: [
        const SizedBox(width: WeekGrid.gutterWidth),
        for (final day in days)
          Expanded(
            child: _DayLabel(day: day, isToday: isSameDay(day, today)),
          ),
      ],
    );
  }
}

class _DayLabel extends StatelessWidget {
  final DateTime day;
  final bool isToday;

  const _DayLabel({required this.day, required this.isToday});

  @override
  Widget build(BuildContext context) {
    final color = isToday ? const Color(0xFFF26D4A) : Colors.black87;
    return Column(
      children: [
        Text(
          weekdaynames[day.weekday - 1],
          style: TextStyle(fontSize: 13, color: color),
        ),
        const SizedBox(height: 2),
        Text(
          '${day.day}',
          style: TextStyle(
            fontSize: 22,
            fontWeight: isToday ? FontWeight.bold : FontWeight.w500,
            color: color,
          ),
        ),
      ],
    );
  }
}