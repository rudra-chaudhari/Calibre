import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:flutter/material.dart';

class AddEventDialog extends StatefulWidget {
  final String id;
  final DateTime initialDate;

  const AddEventDialog({super.key, required this.id, required this.initialDate});

  @override
  State<AddEventDialog> createState() => _AddEventDialogState();
}

class _AddEventDialogState extends State<AddEventDialog> {
  final TextEditingController _title = TextEditingController();
  late DateTime _date = widget.initialDate;
  TimeOfDay _start = const TimeOfDay(hour: 9, minute: 0);
  TimeOfDay _end = const TimeOfDay(hour: 10, minute: 0);
  String _calendarId = 'personal';
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    super.dispose();
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2020),
      lastDate: DateTime(2100),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _pickTime(bool isStart) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: isStart ? _start : _end,
    );
    if (picked == null) return;
    setState(() {
      if (isStart) {
        _start = picked;
      } else {
        _end = picked;
      }
    });
  }

  void _save() {
    final title = _title.text.trim();
    if (title.isEmpty) {
      setState(() => _error = 'Enter a title.');
      return;
    }
    final startMin = _start.hour * 60 + _start.minute;
    var endMin = _end.hour * 60 + _end.minute;
    if (endMin == startMin) {
      setState(() => _error = 'Start and end cannot be the same.');
      return;
    }
    if (endMin < startMin) endMin += 1440;
    Navigator.pop(
      context,
      CalendarEvent(
        id: widget.id,
        title: title,
        date: dateOnly(_date),
        startMin: startMin,
        endMin: endMin,
        colorIndex: calendarById(_calendarId).colorIndex,
        calendarId: _calendarId,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('New event'),
      content: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _title,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Title',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              children: [
                for (final c in defaultCalendars)
                  ChoiceChip(
                    label: Text(c.name),
                    selected: _calendarId == c.id,
                    selectedColor: eventPalette[c.colorIndex].bg,
                    onSelected: (_) => setState(() => _calendarId = c.id),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              onPressed: _pickDate,
              icon: const Icon(Icons.calendar_today, size: 18),
              label: Text(
                '${_date.day} ${shortmonth[_date.month - 1]} ${_date.year}',
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => _pickTime(true),
                    child: Text(_start.format(context)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => _pickTime(false),
                    child: Text(_end.format(context)),
                  ),
                ),
              ],
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _save,
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFFF26D4A),
          ),
          child: const Text('Save'),
        ),
      ],
    );
  }
}