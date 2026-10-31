import 'package:flutter/material.dart';

class WeekScreen extends StatelessWidget {
  final DateTime date;
  const WeekScreen({super.key, required this.date});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Text('Week View')),
    );
  }
}