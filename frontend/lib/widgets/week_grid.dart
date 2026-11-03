import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/widgets/hour_grid.dart';
import 'package:flutter/material.dart';

class WeekGrid extends StatelessWidget {
  static const double gutterWidth = 64;
  static const int rows = 24;

  final List<DateTime> days;

  const WeekGrid({super.key, required this.days});

  @override
  Widget build(BuildContext context) {
    final today = dateOnly(DateTime.now());
    final double rowHeight = HourGrid.hourHeight.toDouble();

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
                child: Container(
                  decoration: BoxDecoration(
                    color: isSameDay(day, today)
                        ? const Color(0x14F26D4A)
                        : null,
                    border: const Border(
                      left: BorderSide(color: Colors.black12),
                    ),
                  ),
                  child: Column(
                    children: [
                      for (int i = 0; i < rows; i++)
                        Container(
                          height: rowHeight,
                          decoration: const BoxDecoration(
                            border: Border(
                              top: BorderSide(color: Colors.black12),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}