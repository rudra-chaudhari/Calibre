import 'package:calibre/screens/day_screen.dart';
import 'package:calibre/screens/week_screen.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/widgets/side_menu.dart';
import 'package:calibre/widgets/top_bar.dart';
import 'package:flutter/material.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final DateTime _selectedDate = dateOnly(DateTime.now());
  int _viewIndex = 0;

  @override
  Widget build(BuildContext context) {
    final pages = [
      WeekScreen(date: _selectedDate),
      DayScreen(date: _selectedDate),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFFFDF0D5),
      body: Row(
        children: [
          const SideMenu(),
          Expanded(
            child: Column(
              children: [
                TopBar(
                  date: _selectedDate,
                  index: _viewIndex,
                  onChanged: (i) => setState(() => _viewIndex = i),
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