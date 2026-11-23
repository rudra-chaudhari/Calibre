import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:flutter/material.dart';

class EventTile extends StatelessWidget {
  final CalendarEvent event;
  final double height;
  final EventColor? color;
  final bool added;
  final bool small;

  const EventTile({
    super.key,
    required this.event,
    required this.height,
    this.color,
    this.added = false,
    this.small = false,
  });

  @override
  Widget build(BuildContext context) {
    final pal = color ?? eventPalette[event.colorIndex % eventPalette.length];
    final title = added ? '✓ ${event.title}' : event.title;
    final compact = height < (small ? 44 : 52);
    final titleLines = height < (small ? 64 : 80) ? 1 : 2;
    final titleStyle = TextStyle(
      fontSize: small ? 12 : 15,
      fontWeight: FontWeight.w700,
      color: pal.fg,
    );

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: small ? 8 : 12,
        vertical: small ? 4 : 6,
      ),
      clipBehavior: Clip.hardEdge,
      decoration: BoxDecoration(
        color: pal.bg,
        borderRadius: BorderRadius.circular(small ? 10 : 12),
      ),
      child: compact
          ? Align(
              alignment: Alignment.centerLeft,
              child: Text(
                title,
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
                    title,
                    maxLines: titleLines,
                    overflow: TextOverflow.ellipsis,
                    style: titleStyle,
                  ),
                ),
                Text(
                  '${timelabel(event.startMin)} – ${timelabel(event.endMin)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: small ? 10.5 : 13,
                    color: pal.fg.withAlpha(200),
                  ),
                ),
              ],
            ),
    );
  }
}