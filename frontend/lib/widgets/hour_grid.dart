import 'dart:async';

import 'package:calibre/utils/date_utils.dart';
import 'package:flutter/material.dart';

class HourGrid extends StatefulWidget {
  static const double hourHeight = 100;
  static const double gutterWidth = 64;
  static const int startHour = 0;
  static const int rows = 24;

  final List<DateTime> days;
  final List<Widget> Function(DateTime day, double width) dayChildren;

  const HourGrid({super.key, required this.days, required this.dayChildren});

  static int gridMin(int startMin) {
    return (startMin - startHour * 60) % 1440;
  }

  static double y(double minutes) {
    return minutes / 60 * hourHeight;
  }

  @override
  State<HourGrid> createState() => _HourGridState();
}

class _HourGridState extends State<HourGrid> {
  final ScrollController _controller = ScrollController();
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(minutes: 1), (_) {
      if (mounted) setState(() {});
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _centerOnNow());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  double _nowTop(DateTime now) {
    final minutes = HourGrid.gridMin(now.hour * 60 + now.minute);
    return HourGrid.y(minutes.toDouble());
  }

  void _centerOnNow() {
    if (!_controller.hasClients) return;
    final position = _controller.position;
    final target = _nowTop(DateTime.now()) - position.viewportDimension / 2;
    _controller.jumpTo(target.clamp(0.0, position.maxScrollExtent));
  }

  Widget _nowLine() {
    const red = Color(0xFFE53935);
    return IgnorePointer(
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: const BoxDecoration(color: red, shape: BoxShape.circle),
          ),
          Expanded(child: Container(height: 2, color: red)),
        ],
      ),
    );
  }

  Widget _gutter() {
    return SizedBox(
      width: HourGrid.gutterWidth,
      child: Column(
        children: [
          for (int i = 0; i < HourGrid.rows; i++)
            SizedBox(
              height: HourGrid.hourHeight,
              child: Align(
                alignment: Alignment.topCenter,
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    hourlabel((HourGrid.startHour + i) % 24),
                    style: const TextStyle(fontSize: 12, color: Colors.black54),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _column(DateTime day, bool isToday, double? nowTop) {
    return Container(
      decoration: BoxDecoration(
        color: isToday ? const Color(0x14F26D4A) : null,
        border: const Border(left: BorderSide(color: Colors.black12)),
      ),
      child: LayoutBuilder(
        builder: (context, box) {
          return Stack(
            children: [
              Column(
                children: [
                  for (int i = 0; i < HourGrid.rows; i++)
                    Container(
                      height: HourGrid.hourHeight,
                      decoration: const BoxDecoration(
                        border: Border(top: BorderSide(color: Colors.black12)),
                      ),
                    ),
                ],
              ),
              ...widget.dayChildren(day, box.maxWidth),
              if (nowTop != null)
                Positioned(
                  top: nowTop - 5,
                  left: 0,
                  right: 0,
                  height: 10,
                  child: _nowLine(),
                ),
            ],
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final today = dateOnly(now);
    final nowDay = now.hour < HourGrid.startHour ? addDays(today, -1) : today;

    return SingleChildScrollView(
      controller: _controller,
      child: SizedBox(
        height: HourGrid.rows * HourGrid.hourHeight,
        child: Row(
          children: [
            _gutter(),
            for (final day in widget.days)
              Expanded(
                child: _column(
                  day,
                  isSameDay(day, today),
                  isSameDay(day, nowDay) ? _nowTop(now) : null,
                ),
              ),
          ],
        ),
      ),
    );
  }
}