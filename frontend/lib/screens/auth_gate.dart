import 'package:calibre/screens/app_shell.dart';
import 'package:calibre/screens/auth_screen.dart';
import 'package:calibre/state/auth_state.dart';
import 'package:flutter/material.dart';

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    return switch (AuthScope.of(context).status) {
      AuthStatus.checking => const Scaffold(
          backgroundColor: Color(0xFFFDF0D5),
          body: Center(child: CircularProgressIndicator()),
        ),
      AuthStatus.signedOut => const AuthScreen(),
      AuthStatus.signedIn => const AppShell(),
    };
  }
}