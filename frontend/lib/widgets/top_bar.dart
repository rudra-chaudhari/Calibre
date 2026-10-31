import 'package:flutter/material.dart';
import 'package:calibre/utils/date_utils.dart';

class TopBar extends StatelessWidget {
  final DateTime date;
  final int index;
  final ValueChanged<int> onChanged;

  const TopBar({
    super.key,
    required this.date,
    required this.index,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '${monthnames[date.month - 1]} ${date.year}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w700,
                color: Colors.black87,
              ),
            ),
          ),
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 0, label: Text('Week')),
              ButtonSegment(value: 1, label: Text('Day')),
            ],
            selected: {index},
            showSelectedIcon: false,
            onSelectionChanged: (selection) => onChanged(selection.first),
          ),
          const Expanded(child: SizedBox()),
        ],
      ),
    );
  }
}