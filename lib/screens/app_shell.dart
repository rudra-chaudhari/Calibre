import 'package:flutter/material.dart';
import 'package:calibre/screens/day_screen.dart';
import 'package:calibre/widgets/day_header.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  static const double _railWidth = 250;

  int _selectedidx = 0;
  bool _menuOpen = false;
  DateTime _selectedDate = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final pages = [
      DayScreen(date: _selectedDate),
      Center(child: Text('Month View')),
      Center(child: Text('Goals')),
    ];

    return Scaffold(
      body: Column(
        children: [
          DayHeader(
            date: _selectedDate,
            onMenuPressed: () {
              setState(() {
                _menuOpen = !_menuOpen;
              });
            },
          ),
          Expanded(
            child: Row(
              children: [
                AnimatedContainer(
                  duration: Duration(milliseconds: 250),
                  curve: Curves.easeInOut,
                  width: _menuOpen ? _railWidth : 0,
                  child: ClipRect(
                    child: OverflowBox(
                      alignment: Alignment.centerLeft,
                      minWidth: _railWidth,
                      maxWidth: _railWidth,
                      child: NavigationRail(
                        minWidth: _railWidth,
                        labelType: NavigationRailLabelType.all,
                        backgroundColor: Color(0xFFFDF0D5),
                        selectedIndex: _selectedidx,
                        onDestinationSelected: (index) {
                          setState(() {
                            _selectedidx = index;
                          });
                        },
                        indicatorColor: Color(0xFFF26D4A),
                        selectedIconTheme: IconThemeData(color: Colors.white),
                        selectedLabelTextStyle:
                            TextStyle(color: Color(0xFFF26D4A)),
                        destinations: [
                          NavigationRailDestination(
                            icon: Icon(Icons.today_outlined),
                            selectedIcon: Icon(Icons.today),
                            label: Text('Day'),
                          ),
                          NavigationRailDestination(
                            icon: Icon(Icons.calendar_month_outlined),
                            selectedIcon: Icon(Icons.calendar_month),
                            label: Text('Month'),
                          ),
                          NavigationRailDestination(
                            icon: Icon(Icons.flag_outlined),
                            selectedIcon: Icon(Icons.flag),
                            label: Text('Goals'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Expanded(child: pages[_selectedidx]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}