import 'package:flutter/material.dart';
import 'package:calibre/utils/date_utils.dart';

class DayHeader extends StatelessWidget {
  final DateTime date;
  final VoidCallback onMenuPressed;

  const DayHeader({
    super.key,
    required this.date,
    required this.onMenuPressed,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 120,
      color: Color(0xFFF26D4A),
      child: Row(
        children: [
          Container(
            width: 250,
            color: Color(0xFFF05C33),
            child: Column(
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: IconButton(
                    icon: Icon(Icons.menu, color: Colors.white),
                    onPressed: onMenuPressed,
                  ),
                ),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '${date.day}',
                        style: TextStyle(
                          fontSize: 30,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      Text(
                        monthnames[date.month - 1].substring(0, 3),
                        style: TextStyle(color: Colors.white),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Center(
              child: Text(
                'Today',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 30,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}