import 'package:calibre/utils/date_utils.dart';
import 'package:flutter/material.dart';

class TopBar extends StatelessWidget {
  final DateTime date;
  final int index;
  final ValueChanged<int> onChanged;
  final VoidCallback onPrevious;
  final VoidCallback onNext;
  final VoidCallback onToday;
  final VoidCallback onMenu;

  const TopBar({
    super.key,
    required this.date,
    required this.index,
    required this.onChanged,
    required this.onPrevious,
    required this.onNext,
    required this.onToday,
    required this.onMenu,
  });

  @override
  Widget build(BuildContext context) {
    final month = monthnames[date.month - 1];
    final title = index == 1
        ? '${date.day} $month ${date.year}'
        : '$month ${date.year}';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Row(
        children: [
          IconButton(onPressed: onMenu, icon: const Icon(Icons.menu)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
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
            onSelectionChanged: (s) => onChanged(s.first),
          ),
          Expanded(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: onToday,
                  style: TextButton.styleFrom(
                    foregroundColor: const Color(0xFFF26D4A),
                  ),
                  child: const Text('Today'),
                ),
                IconButton(
                  onPressed: onPrevious,
                  icon: const Icon(Icons.chevron_left),
                ),
                IconButton(
                  onPressed: onNext,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}