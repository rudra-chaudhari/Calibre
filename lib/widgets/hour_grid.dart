import 'package:flutter/material.dart';
import 'package:calibre/utils/date_utils.dart';

class HourGrid extends StatefulWidget {
  static const double hourHeight = 100;
  static const int startHour = 6;
  static const int endHour = 29;

  final DateTime date;

  const HourGrid({super.key, required this.date});

  @override
  State<HourGrid> createState() => _HourGridState();
}

class _HourGridState extends State<HourGrid> {
  late final ScrollController _controller;

  @override
  void initState() {
    super.initState();

    double offset = 0;
    final now = DateTime.now();
    if (isSameDay(widget.date, now)) {
      final rowsFromTop = (now.hour - HourGrid.startHour) % 24;
      if (rowsFromTop > 0) {
        offset = rowsFromTop * HourGrid.hourHeight;
      }
    }

    _controller = ScrollController(initialScrollOffset: offset);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final rowCount = HourGrid.endHour - HourGrid.startHour + 1;

    return ListView.builder(
      controller: _controller,
      itemCount: rowCount,
      itemBuilder: (context, index) {
        final hour = HourGrid.startHour + index;
        return Container(
          height: HourGrid.hourHeight,
          decoration: BoxDecoration(
            border: Border(top: BorderSide(color: Colors.black12)),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(
                width: 70,
                child: Padding(
                  padding: EdgeInsets.only(left: 8, top: 4),
                  child: Text(
                    hourlabel(hour % 24),
                    style: TextStyle(fontSize: 12, color: Colors.black54),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}