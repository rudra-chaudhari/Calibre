import 'dart:math';

import '../models/calendar_event.dart';

class PlacedEvent {
  final CalendarEvent event;
  final int column;
  final int columns;
  const PlacedEvent(this.event, this.column, this.columns);
}

List<PlacedEvent> layoutEvents(List<CalendarEvent> events) {
  final sorted = [...events];
  sorted.sort((a, b) {
    final c = a.startMin.compareTo(b.startMin);
    return c != 0 ? c : b.endMin.compareTo(a.endMin);
  });

  final result = <PlacedEvent>[];
  var cluster = <CalendarEvent>[];
  var clusterEnd = -1;

  void flush() {
    if (cluster.isEmpty) return;
    final laneEnds = <int>[];
    final lanes = <int>[];
    for (final e in cluster) {
      var lane = -1;
      for (var i = 0; i < laneEnds.length; i++) {
        if (laneEnds[i] <= e.startMin) {
          lane = i;
          break;
        }
      }
      if (lane == -1) {
        laneEnds.add(e.endMin);
        lane = laneEnds.length - 1;
      } else {
        laneEnds[lane] = e.endMin;
      }
      lanes.add(lane);
    }
    for (var i = 0; i < cluster.length; i++) {
      result.add(PlacedEvent(cluster[i], lanes[i], laneEnds.length));
    }
    cluster = <CalendarEvent>[];
  }

  for (final e in sorted) {
    if (cluster.isNotEmpty && e.startMin >= clusterEnd) flush();
    clusterEnd = cluster.isEmpty ? e.endMin : max(clusterEnd, e.endMin);
    cluster.add(e);
  }
  flush();
  return result;
}