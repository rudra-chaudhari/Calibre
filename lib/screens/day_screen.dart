import 'package:flutter/material.dart';
import '../widgets/hour_grid.dart';

class DayScreen extends StatelessWidget {
  final DateTime date;
  const DayScreen({super.key, required this.date});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: HourGrid(date : date),
    );
  }
}