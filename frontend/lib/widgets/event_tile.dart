import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:flutter/material.dart';

class EventTile extends StatelessWidget {
  final CalendarEvent event;
  final double height;

  const EventTile({super.key, required this.event, required this.height});

  @override
  Widget build(BuildContext context) {
    final pal = eventPalette[event.colorIndex % eventPalette.length];
    final compact = height < 40;
    final titleStyle = TextStyle(
      fontSize: 12,
      fontWeight: FontWeight.w700,
      color: pal.fg,
    );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      clipBehavior: Clip.hardEdge,
      decoration: BoxDecoration(
        color: pal.bg,
        borderRadius: BorderRadius.circular(10),
      ),
      child: compact
          ? Align(
              alignment: Alignment.centerLeft,
              child: Text(
                event.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: titleStyle,
              ),
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Flexible(
                  child: Text(
                    event.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: titleStyle,
                  ),
                ),
                Text(
                  '${timelabel(event.startMin)} – ${timelabel(event.endMin)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 10.5,
                    color: pal.fg.withAlpha(200),
                  ),
                ),
              ],
            ),
    );
  }
}