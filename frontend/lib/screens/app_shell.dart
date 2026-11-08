import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/screens/day_screen.dart';
import 'package:calibre/screens/week_screen.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/widgets/add_event_dialog.dart';
import 'package:calibre/widgets/side_menu.dart';
import 'package:calibre/widgets/top_bar.dart';
import 'package:flutter/material.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final EventState _events = EventState();
  DateTime _selectedDate = dateOnly(DateTime.now());
  int _viewIndex = 0;
  bool _menuOpen = true;

  @override
  void dispose() {
    _events.dispose();
    super.dispose();
  }

  void _shift(int direction) {
    final step = _viewIndex == 0 ? 7 : 1;
    setState(() => _selectedDate = addDays(_selectedDate, direction * step));
  }

  Future<void> _newEvent() async {
    final event = await showDialog<CalendarEvent>(
      context: context,
      builder: (_) => AddEventDialog(
        id: _events.newId(),
        initialDate: _selectedDate,
      ),
    );
    if (event != null) _events.add(event);
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      WeekScreen(date: _selectedDate),
      DayScreen(date: _selectedDate),
    ];

    return EventScope(
      state: _events,
      child: Scaffold(
        backgroundColor: const Color(0xFFFDF0D5),
        body: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeInOut,
              width: _menuOpen ? 280 : 0,
              child: ClipRect(
                child: OverflowBox(
                  alignment: Alignment.centerLeft,
                  minWidth: 280,
                  maxWidth: 280,
                  child: SideMenu(onNewEvent: _newEvent),
                ),
              ),
            ),
            Expanded(
              child: Column(
                children: [
                  TopBar(
                    date: _selectedDate,
                    index: _viewIndex,
                    onChanged: (i) => setState(() => _viewIndex = i),
                    onPrevious: () => _shift(-1),
                    onNext: () => _shift(1),
                    onToday: () => setState(
                      () => _selectedDate = dateOnly(DateTime.now()),
                    ),
                    onMenu: () => setState(() => _menuOpen = !_menuOpen),
                  ),
                  Expanded(child: pages[_viewIndex]),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}