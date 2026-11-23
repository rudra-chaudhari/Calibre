import 'package:calibre/screens/day_screen.dart';
import 'package:calibre/screens/month_screen.dart';
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
  void initState() {
    super.initState();
    _events.openDay = _openDay;
    WidgetsBinding.instance.addPostFrameCallback((_) => _reload());
  }

  @override
  void dispose() {
    _events.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    DateTime from = _selectedDate;
    int days = 7;
    if (_viewIndex == 2) {
      from = DateTime(_selectedDate.year, _selectedDate.month, 1);
      days = 42;
    }
    final start = startofweek(from);
    await guarded(context, () => _events.load(start, days));
  }

  void _shift(int direction) {
    final d = _selectedDate;
    DateTime next;
    if (_viewIndex == 2) {
      next = DateTime(d.year, d.month + direction, 1);
    } else if (_viewIndex == 0) {
      next = addDays(d, direction * 7);
    } else {
      next = addDays(d, direction);
    }
    setState(() => _selectedDate = next);
    _reload();
  }

  Future<void> _newEvent() async {
    final result = await showDialog<DialogResult>(
      context: context,
      builder: (_) => AddEventDialog(initialDate: _selectedDate),
    );
    final event = result?.event;
    if (event == null || !mounted) return;
    await guarded(context, () => _events.add(event, result!.repeat));
  }

  void _setTab(CalendarTab tab) {
    _events.setTab(tab);
    _reload();
  }

  void _openDay(DateTime day) {
    setState(() {
      _selectedDate = day;
      _viewIndex = 1;
    });
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      WeekScreen(date: _selectedDate),
      DayScreen(date: _selectedDate),
      MonthScreen(date: _selectedDate, onDay: _openDay),
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
                  child: SideMenu(onNewEvent: _newEvent, onTab: _setTab),
                ),
              ),
            ),
            Expanded(
              child: Column(
                children: [
                  TopBar(
                    date: _selectedDate,
                    index: _viewIndex,
                    onChanged: (i) {
                      setState(() => _viewIndex = i);
                      _reload();
                    },
                    onPrevious: () => _shift(-1),
                    onNext: () => _shift(1),
                    onToday: () {
                      setState(() => _selectedDate = dateOnly(DateTime.now()));
                      _reload();
                    },
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