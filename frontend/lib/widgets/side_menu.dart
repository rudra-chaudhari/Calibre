import 'package:calibre/state/auth_state.dart';
import 'package:flutter/material.dart';

class SideMenu extends StatelessWidget {
  final VoidCallback onNewEvent;

  const SideMenu({super.key, required this.onNewEvent});

  @override
  Widget build(BuildContext context) {
    final auth = AuthScope.of(context);
    final user = auth.user!;
    final label = (user.name != null && user.name!.isNotEmpty)
        ? user.name!
        : user.email;
    final initial = label.isEmpty ? '?' : label[0].toUpperCase();

    return Container(
      width: 280,
      color: const Color(0xFFF5E3BD),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          FilledButton.icon(
            onPressed: onNewEvent,
            icon: const Icon(Icons.add),
            label: const Text('New event'),
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFFF26D4A),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
          const Expanded(child: SizedBox()),
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