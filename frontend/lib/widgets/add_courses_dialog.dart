import 'package:calibre/services/api_exception.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/utils/date_utils.dart';
import 'package:flutter/material.dart';

class CoursePick {
  final List<Map<String, dynamic>> slots;
  final DateTime until;

  const CoursePick(this.slots, this.until);
}

DateTime _defaultUntil() {
  final now = DateTime.now();
  if (now.month >= 7) return DateTime(now.year, 12, 15);
  return DateTime(now.year, 4, 30);
}

class AddCoursesDialog extends StatefulWidget {
  final EventState events;

  const AddCoursesDialog({super.key, required this.events});

  @override
  State<AddCoursesDialog> createState() => _AddCoursesDialogState();
}

class _AddCoursesDialogState extends State<AddCoursesDialog> {
  final TextEditingController _search = TextEditingController();
  final Set<String> _selected = {};
  List<Map<String, dynamic>> _slots = [];
  List<String> _departments = [];
  String? _department;
  DateTime _until = _defaultUntil();
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final slots = await widget.events.loadTimetable();
      final names = <String>{};
      for (final s in slots) {
        names.add(s['department'].toString());
      }
      final list = names.toList();
      list.sort();
      if (!mounted) return;
      setState(() {
        _slots = slots;
        _departments = list;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  Map<String, List<Map<String, dynamic>>> _courses() {
    final query = _search.text.trim().toLowerCase();
    final result = <String, List<Map<String, dynamic>>>{};
    for (final s in _slots) {
      if (s['department'] != _department) continue;
      final code = s['course_code'].toString();
      final instructor = (s['instructor'] ?? '').toString();
      final text = '$code $instructor'.toLowerCase();
      if (query.isNotEmpty && !text.contains(query)) continue;
      result.putIfAbsent(code, () => []).add(s);
    }
    return result;
  }

  String _summary(List<Map<String, dynamic>> list) {
    final parts = <String>[];
    for (final s in list) {
      final day = weekdaynames[s['weekday'] as int];
      final time = timelabel(minutesOf(s['start_time'] as String));
      final text = '$day $time';
      if (!parts.contains(text)) parts.add(text);
    }
    final instructor = (list.first['instructor'] ?? '').toString();
    if (instructor.isEmpty) return parts.join(', ');
    return '${parts.join(', ')}\n$instructor';
  }

  Future<void> _pickUntil() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _until,
      firstDate: DateTime.now(),
      lastDate: DateTime(2100),
    );
    if (picked != null) setState(() => _until = picked);
  }

  void _confirm() {
    final picked = <Map<String, dynamic>>[];
    for (final s in _slots) {
      if (_selected.contains(s['course_code'].toString())) picked.add(s);
    }
    Navigator.pop(context, CoursePick(picked, _until));
  }

  Widget _courseList() {
    if (_department == null) {
      return const Center(child: Text('Select a department.'));
    }
    final courses = _courses();
    if (courses.isEmpty) {
      return const Center(child: Text('No courses found.'));
    }
    final codes = courses.keys.toList();
    codes.sort();
    return ListView(
      children: [
        for (final code in codes)
          CheckboxListTile(
            value: _selected.contains(code),
            controlAffinity: ListTileControlAffinity.leading,
            title: Text(code),
            subtitle: Text(_summary(courses[code]!)),
            onChanged: (on) {
              setState(() {
                if (on == true) {
                  _selected.add(code);
                } else {
                  _selected.remove(code);
                }
              });
            },
          ),
      ],
    );
  }

  Widget _body() {
    if (_error != null) {
      return Center(
        child: Text(_error!, style: const TextStyle(color: Colors.red)),
      );
    }
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        DropdownButton<String>(
          isExpanded: true,
          hint: const Text('Select department'),
          value: _department,
          items: [
            for (final d in _departments)
              DropdownMenuItem(value: d, child: Text(d)),
          ],
          onChanged: (value) => setState(() => _department = value),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: _search,
          onChanged: (_) => setState(() {}),
          decoration: const InputDecoration(
            labelText: 'Search course or instructor',
            prefixIcon: Icon(Icons.search),
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        Expanded(child: _courseList()),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: _pickUntil,
          icon: const Icon(Icons.event_repeat, size: 18),
          label: Text(
            'Until ${_until.day} ${shortmonth[_until.month - 1]} ${_until.year}',
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Add courses'),
      content: SizedBox(width: 460, height: 480, child: _body()),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _selected.isEmpty ? null : _confirm,
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFFF26D4A),
          ),
          child: Text('Add ${_selected.length}'),
        ),
      ],
    );
  }
}