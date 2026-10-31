import 'package:flutter/material.dart';
import 'package:calibre/screens/day_screen.dart';
import 'package:calibre/screens/week_screen.dart';
import 'package:calibre/widgets/top_bar.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  static const double _menuWidth = 280;

  int _viewIndex = 0;
  final DateTime _selectedDate = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final pages = [
      WeekScreen(date: _selectedDate),
      DayScreen(date: _selectedDate),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFFFDF0D5),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            width: _menuWidth,
            color: const Color(0xFFF5E3BD),
          ),
          Expanded(
            child: Column(
              children: [
                TopBar(
                  date: _selectedDate,
                  index: _viewIndex,
                  onChanged: (i) {
                    setState(() {
                      _viewIndex = i;
                    });
                  },
                ),
                Expanded(child: pages[_viewIndex]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}