import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/widgets/week_day_cards.dart';
import 'package:calibre/widgets/week_grid.dart';
import 'package:flutter/material.dart';

class WeekScreen extends StatelessWidget {
  final DateTime date;

  const WeekScreen({super.key, required this.date});

  @override
  Widget build(BuildContext context) {
    final start = startofweek(date);
    final days = List.generate(7, (i) => addDays(start, i));

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          children: [
            WeekDayCards(days: days),
            const SizedBox(height: 12),
            Expanded(child: WeekGrid(days: days)),
          ],
        ),
      ),
    );
  }
}