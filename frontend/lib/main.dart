import 'package:calibre/screens/auth_gate.dart';
import 'package:calibre/state/auth_state.dart';
import 'package:flutter/material.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  final AuthState _auth = AuthState();

  @override
  void initState() {
    super.initState();
    _auth.start();
  }

  @override
  void dispose() {
    _auth.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AuthScope(
      state: _auth,
      child: MaterialApp(
        title: 'Calibre',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFF26D4A)),
          useMaterial3: true,
        ),
        home: const AuthGate(),
      ),
    );
  }
}