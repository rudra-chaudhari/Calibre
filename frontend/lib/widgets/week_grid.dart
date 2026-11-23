import 'dart:math' as math;

import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_layout.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:calibre/widgets/add_event_dialog.dart';
import 'package:calibre/widgets/event_tile.dart';
import 'package:calibre/widgets/hour_grid.dart';
import 'package:flutter/material.dart';

class _Slot {
  final CalendarEvent? event;
  final List<CalendarEvent> hidden;
  final double top;

  const _Slot(this.event, this.hidden, this.top);
}

class WeekGrid extends StatelessWidget {
  static const double gutterWidth = HourGrid.gutterWidth;
  static const double pointHeight = 44;
  static const double weekPointHeight = 34;
  static const double moreHeight = 22;

  final List<DateTime> days;

  const WeekGrid({super.key, required this.days});

  bool get _single => days.length == 1;

  double get _pointH {
    return _single ? pointHeight : weekPointHeight;
  }

  CalendarEvent _toGridTime(CalendarEvent e) {
    final start = HourGrid.gridMin(e.startMin);
    var end = start + (e.endMin - e.startMin);
    if (end > 1440) end = 1440;
    return e.copyWith(startMin: start, endMin: end);
  }

  double _tileHeight(PlacedEvent p) {
    final top = HourGrid.y(p.event.startMin.toDouble());
    final bottom = HourGrid.y(p.event.endMin.toDouble());
    return math.max(bottom - top - 2, _single ? 36.0 : 28.0);
  }

  List<_Slot> _slots(List<CalendarEvent> points) {
    final h = _pointH;
    final cap = ((HourGrid.hourHeight + 2) / (h + 2)).floor();

    final sorted = List<CalendarEvent>.from(points);
    sorted.sort((a, b) {
      final aMin = HourGrid.gridMin(a.startMin);
      final bMin = HourGrid.gridMin(b.startMin);
      return bMin.compareTo(aMin);
    });

    final groups = <List<_Slot>>[];
    double? prevTop;
    for (final e in sorted) {
      final minutes = HourGrid.gridMin(e.startMin).toDouble();
      double top = HourGrid.y(minutes) - h;
      final collided = prevTop != null && top + h + 2 > prevTop;
      if (collided) {
        top = prevTop - h - 2;
        groups.last.add(_Slot(e, [], top));
      } else {
        groups.add([_Slot(e, [], top)]);
      }
      prevTop = top;
    }

    final slots = <_Slot>[];
    for (final g in groups) {
      if (g.length <= cap) {
        slots.addAll(g);
        continue;
      }
      final shown = math.max(cap - 1, 1);
      final hidden = <CalendarEvent>[];
      for (int i = shown; i < g.length; i++) {
        hidden.add(g[i].event!);
      }
      final moreTop = g.first.top + h - moreHeight;
      slots.add(_Slot(null, hidden, moreTop));
      for (int i = 0; i < shown; i++) {
        slots.add(_Slot(g[i].event, [], moreTop - 2 - h - i * (h + 2)));
      }
    }
    return slots;
  }

  Future<String?> _askScope(BuildContext context, String verb) {
    return showDialog<String>(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        title: Text('$verb repeating event'),
        children: [
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dialogContext, 'this'),
            child: const Text('This event'),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dialogContext, 'following'),
            child: const Text('This and following events'),
          ),
          SimpleDialogOption(
            onPressed: () => Navigator.pop(dialogContext, 'all'),
            child: const Text('All events'),
          ),
        ],
      ),
    );
  }

  Future<void> _edit(
    BuildContext context,
    EventState events,
    CalendarEvent event,
  ) async {
    final result = await showDialog<DialogResult>(
      context: context,
      builder: (_) => AddEventDialog(initialDate: event.date, existing: event),
    );
    if (result == null || !context.mounted) return;

    var scope = 'this';
    if (event.seriesId != null) {
      final verb = result.delete ? 'Delete' : 'Edit';
      final picked = await _askScope(context, verb);
      if (picked == null || !context.mounted) return;
      scope = picked;
    }

    await guarded(context, () {
      if (result.delete) return events.remove(event, scope);
      return events.update(result.event!, scope);
    });
  }

  Future<void> _deadline(
    BuildContext context,
    EventState events,
    CalendarEvent event,
  ) async {
    final done = events.isDone(event);
    final date = event.date;
    final dueText =
        'Due ${date.day} ${shortmonth[date.month - 1]} ${date.year}, ${timelabel(event.startMin)}';

    final toggle = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(event.title),
        content: Text(dueText),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Close'),
          ),
          if (isTask(event))
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFFF26D4A),
              ),
              child: Text(done ? 'Mark not done' : 'Mark done'),
            ),
        ],
      ),
    );

    if (toggle != true || !context.mounted) return;
    await guarded(context, () => events.setTaskDone(event, !done));
  }

  Future<void> _menu(
    BuildContext context,
    EventState events,
    CalendarEvent event,
    Offset position,
  ) async {
    final overlay = Overlay.of(context).context.findRenderObject() as RenderBox;
    final added = events.isAdded(event);
    final choice = await showMenu<String>(
      context: context,
      position: RelativeRect.fromRect(
        position & const Size(1, 1),
        Offset.zero & overlay.size,
      ),
      items: [
        PopupMenuItem(
          value: 'add',
          enabled: !added,
          child: Text(added ? 'Added to my events' : 'Add to my events'),
        ),
      ],
    );
    if (choice == 'add' && context.mounted) {
      await guarded(context, () => events.addToMine(event));
    }
  }

  Future<void> _showAll(
    BuildContext context,
    EventState events,
    List<CalendarEvent> items,
  ) async {
    final picked = await showDialog<CalendarEvent>(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        title: const Text('More events'),
        children: [
          for (final e in items)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(dialogContext, e),
              child: Text('${timelabel(e.startMin)}   ${e.title}'),
            ),
        ],
      ),
    );
    if (picked == null || !context.mounted) return;
    if (events.tab == CalendarTab.mine) {
      await _deadline(context, events, picked);
    }
  }

  Widget _tile(
    BuildContext context,
    EventState events,
    CalendarEvent event,
    double height,
  ) {
    final mine = events.tab == CalendarTab.mine;
    final deadline = mine && event.endMin <= event.startMin;

    VoidCallback? onTap;
    if (mine && deadline) {
      onTap = () => _deadline(context, events, event);
    } else if (mine) {
      onTap = () => _edit(context, events, event);
    }

    void Function(TapUpDetails)? onRightClick;
    if (!mine) {
      onRightClick = (d) => _menu(context, events, event, d.globalPosition);
    }

    EventColor? color = events.colorFor(event);
    if (deadline) {
      color = events.isDone(event) ? freeColor : clashColor;
    }

    return GestureDetector(
      onTap: onTap,
      onSecondaryTapUp: onRightClick,
      child: EventTile(
        event: event,
        height: height,
        color: color,
        small: !_single,
        added: mine ? events.isDone(event) : events.isAdded(event),
      ),
    );
  }

  Widget _more(
    BuildContext context,
    EventState events,
    DateTime day,
    List<CalendarEvent> hidden,
  ) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () {
        if (_single) {
          _showAll(context, events, hidden);
        } else {
          events.openDay?.call(day);
        }
      },
      child: Padding(
        padding: const EdgeInsets.only(left: 8),
        child: Align(
          alignment: Alignment.centerLeft,
          child: Text(
            '+${hidden.length} more',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: _single ? 13 : 12,
              fontWeight: FontWeight.w700,
              color: const Color(0xFFF26D4A),
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _dayChildren(
    BuildContext context,
    EventState events,
    DateTime day,
    double width,
  ) {
    final timed = <CalendarEvent>[];
    final points = <CalendarEvent>[];
    for (final e in events.eventsForColumn(day)) {
      if (e.endMin > e.startMin) {
        timed.add(e);
      } else {
        points.add(e);
      }
    }

    final byId = {for (final e in timed) e.id: e};
    final placed = layoutEvents([for (final e in timed) _toGridTime(e)]);

    final children = <Widget>[];
    for (final p in placed) {
      final height = _tileHeight(p);
      children.add(
        Positioned(
          top: HourGrid.y(p.event.startMin.toDouble()) + 1,
          left: width / p.columns * p.column + 2,
          width: width / p.columns - 4,
          height: height,
          child: _tile(context, events, byId[p.event.id]!, height),
        ),
      );
    }

    for (final s in _slots(points)) {
      final isMore = s.event == null;
      children.add(
        Positioned(
          top: s.top < 0 ? 0 : s.top,
          left: 2,
          right: 2,
          height: isMore ? moreHeight : _pointH,
          child: isMore
              ? _more(context, events, day, s.hidden)
              : _tile(context, events, s.event!, _pointH),
        ),
      );
    }
    return children;
  }

  @override
  Widget build(BuildContext context) {
    final events = EventScope.of(context);
    return HourGrid(
      days: days,
      dayChildren: (day, width) => _dayChildren(context, events, day, width),
    );
  }
}