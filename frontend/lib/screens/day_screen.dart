import 'package:calibre/widgets/week_grid.dart';
import 'package:flutter/material.dart';

class DayScreen extends StatelessWidget {
  final DateTime date;
  const DayScreen({super.key, required this.date});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: WeekGrid(days: [date]),
      ),
    );
  }
}