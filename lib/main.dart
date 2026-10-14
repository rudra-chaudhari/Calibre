import 'package:flutter/material.dart';
import 'screens/day_screen.dart';
import 'screens/app_shell.dart';
import 'utils/date_utils.dart';
void main() {
  runApp(const MyApp());
}


class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    
    return MaterialApp(
      title: 'Calibre',
      theme: ThemeData(
        colorScheme: .fromSeed(seedColor: Colors.deepPurple),
      ),
      home: AppShell()
      );
  
  }
}

