import 'package:calibre/models/calendar_event.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:calibre/utils/event_palette.dart';
import 'package:flutter/material.dart';

class DialogResult {
  final CalendarEvent? event;
  final RepeatRule? repeat;
  final bool delete;

  const DialogResult({this.event, this.repeat, this.delete = false});
}

class AddEventDialog extends StatefulWidget {
  final DateTime initialDate;
  final CalendarEvent? existing;

  const AddEventDialog({super.key, required this.initialDate, this.existing});

  @override
  State<AddEventDialog> createState() => _AddEventDialogState();
}

class _AddEventDialogState extends State<AddEventDialog> {
  late final TextEditingController _title = TextEditingController(
    text: widget.existing?.title ?? '',
  );
  late DateTime _date = widget.existing?.date ?? widget.initialDate;
  late TimeOfDay _start = widget.existing == null
      ? const TimeOfDay(hour: 9, minute: 0)
      : _timeOf(widget.existing!.startMin);
  late TimeOfDay _end = widget.existing == null
      ? const TimeOfDay(hour: 10, minute: 0)
      : _timeOf(widget.existing!.endMin);
  late String _calendarId = widget.existing?.calendarId ?? 'personal';
  String _freq = 'none';
  final Set<int> _weekdays = {};
  late DateTime _until = addDays(_date, 28);
  String? _error;

  TimeOfDay _timeOf(int minutes) {
    return TimeOfDay(hour: minutes ~/ 60 % 24, minute: minutes % 60);
  }

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

  Future<void> _pickUntil() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _until,
      firstDate: _date,
      lastDate: DateTime(2100),
    );
    if (picked != null) setState(() => _until = picked);
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
    RepeatRule? rule;
    if (widget.existing == null && _freq != 'none') {
      if (_until.isBefore(dateOnly(_date))) {
        setState(() => _error = 'Repeat end is before the event.');
        return;
      }
      final days = {..._weekdays, _date.weekday - 1}.toList()..sort();
      rule = RepeatRule(_freq, days, _until);
    }
    final colorIndex = calendarById(_calendarId).colorIndex;
    final event = widget.existing == null
        ? CalendarEvent(
            id: '',
            title: title,
            date: dateOnly(_date),
            startMin: startMin,
            endMin: endMin,
            colorIndex: colorIndex,
            calendarId: _calendarId,
          )
        : widget.existing!.copyWith(
            title: title,
            date: dateOnly(_date),
            startMin: startMin,
            endMin: endMin,
            colorIndex: colorIndex,
            calendarId: _calendarId,
          );
    Navigator.pop(context, DialogResult(event: event, repeat: rule));
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.existing == null ? 'New event' : 'Edit event'),
      content: SizedBox(
        width: 360,
        child: SingleChildScrollView(
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
              if (widget.existing == null) ...[
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final f in const ['none', 'daily', 'weekly'])
                      ChoiceChip(
                        label: Text(
                          f == 'none'
                              ? 'Does not repeat'
                              : f == 'daily'
                              ? 'Daily'
                              : 'Weekly',
                        ),
                        selected: _freq == f,
                        onSelected: (_) => setState(() => _freq = f),
                      ),
                  ],
                ),
                if (_freq == 'weekly') ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    children: [
                      for (var i = 0; i < 7; i++)
                        FilterChip(
                          label: Text(weekdaynames[i]),
                          selected: _weekdays.contains(i),
                          onSelected: (on) => setState(() {
                            if (on) {
                              _weekdays.add(i);
                            } else {
                              _weekdays.remove(i);
                            }
                          }),
                        ),
                    ],
                  ),
                ],
                if (_freq != 'none') ...[
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: _pickUntil,
                    icon: const Icon(Icons.event_repeat, size: 18),
                    label: Text(
                      'Until ${_until.day} ${shortmonth[_until.month - 1]} ${_until.year}',
                    ),
                  ),
                ],
              ],
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
            ],
          ),
        ),
      ),
      actions: [
        if (widget.existing != null)
          TextButton(
            onPressed: () =>
                Navigator.pop(context, const DialogResult(delete: true)),
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
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