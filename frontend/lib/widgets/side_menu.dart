import 'package:calibre/services/api_exception.dart';
import 'package:calibre/services/moodle_service.dart';
import 'package:calibre/state/auth_state.dart';
import 'package:calibre/state/event_state.dart';
import 'package:calibre/widgets/add_courses_dialog.dart';
import 'package:calibre/widgets/today_card.dart';
import 'package:flutter/material.dart';

const _tabLabels = {
  CalendarTab.mine: 'My events',
  CalendarTab.dept: 'Department events',
  CalendarTab.insti: 'Institute events',
};

class SideMenu extends StatefulWidget {
  final VoidCallback onNewEvent;
  final ValueChanged<CalendarTab> onTab;

  const SideMenu({super.key, required this.onNewEvent, required this.onTab});

  @override
  State<SideMenu> createState() => _SideMenuState();
}

class _SideMenuState extends State<SideMenu> {
  final MoodleService _moodle = MoodleService();
  bool _connected = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _checkStatus();
  }

  Future<void> _checkStatus() async {
    try {
      final connected = await _moodle.isConnected();
      if (mounted) setState(() => _connected = connected);
    } catch (_) {}
  }

  Future<void> _moodleAction() async {
    final messenger = ScaffoldMessenger.of(context);
    final events = EventScope.of(context);
    setState(() => _busy = true);
    try {
      if (!_connected) {
        await _moodle.connect();
        _connected = true;
      }
      await _moodle.sync();
      await events.reload();
      messenger.showSnackBar(const SnackBar(content: Text('Moodle synced.')));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _addCourses() async {
    final events = EventScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final pick = await showDialog<CoursePick>(
      context: context,
      builder: (_) => AddCoursesDialog(events: events),
    );
    if (pick == null || !mounted) return;

    await guarded(context, () async {
      final added = await events.addCourses(pick.slots, pick.until);
      await events.reload();
      String text = 'Courses added.';
      if (added == 0) text = 'Those courses are already in your calendar.';
      messenger.showSnackBar(SnackBar(content: Text(text)));
    });
  }

  Widget _tabButton(CalendarTab tab, String text, EventState events) {
    Color bg = Colors.transparent;
    Color fg = Colors.black87;
    if (events.tab == tab) {
      bg = const Color(0xFFF26D4A);
      fg = Colors.white;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FilledButton(
        onPressed: () => widget.onTab(tab),
        style: FilledButton.styleFrom(
          backgroundColor: bg,
          foregroundColor: fg,
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
        child: Text(text),
      ),
    );
  }

  Widget _moodleIcon() {
    if (_busy) {
      return const SizedBox(
        width: 16,
        height: 16,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    if (_connected) return const Icon(Icons.check_circle_outline);
    return const Icon(Icons.link);
  }

  @override
  Widget build(BuildContext context) {
    final auth = AuthScope.of(context);
    final events = EventScope.of(context);
    final user = auth.user!;

    String label = user.email;
    if (user.name.isNotEmpty) label = user.name;
    String initial = '?';
    if (label.isNotEmpty) initial = label[0].toUpperCase();

    return Container(
      width: 280,
      color: const Color(0xFFF5E3BD),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          FilledButton.icon(
            onPressed: widget.onNewEvent,
            icon: const Icon(Icons.add),
            label: const Text('New event'),
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFF26D4A),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
          const SizedBox(height: 28),
          for (final entry in _tabLabels.entries)
            _tabButton(entry.key, entry.value, events),
          const SizedBox(height: 24),
          const Expanded(child: TodayCard()),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _addCourses,
            icon: const Icon(Icons.school_outlined),
            label: const Text('Add courses'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _busy ? null : _moodleAction,
            icon: _moodleIcon(),
            label: Text(_connected ? 'Sync Moodle' : 'Connect Moodle'),
          ),
          const SizedBox(height: 12),
          PopupMenuButton<String>(
            tooltip: '',
            onSelected: (value) {
              if (value == 'signout') auth.signOut();
            },
            itemBuilder: (context) => [
              PopupMenuItem(enabled: false, child: Text(user.email)),
              const PopupMenuDivider(),
              const PopupMenuItem(value: 'signout', child: Text('Sign out')),
            ],
            child: Row(
              children: [
                CircleAvatar(
                  backgroundColor: const Color(0xFFF26D4A),
                  foregroundColor: Colors.white,
                  child: Text(initial),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    label,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      color: Colors.black87,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}