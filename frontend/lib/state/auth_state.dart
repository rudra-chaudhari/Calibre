import 'package:calibre/models/user.dart';
import 'package:calibre/services/api_exception.dart';
import 'package:calibre/services/auth_service.dart';
import 'package:calibre/services/token_storage.dart';
import 'package:flutter/material.dart';

enum AuthStatus { checking, signedIn, signedOut }

class AuthState extends ChangeNotifier {
  final AuthService _service = AuthService(TokenStorage());

  AuthStatus status = AuthStatus.checking;
  User? user;

  Future<void> start() async {
    try {
      try {
        user = await _service.me();
      } on ApiException catch (e) {
        if (e.statusCode != 401) rethrow;
        await _service.refresh();
        user = await _service.me();
      }
      status = AuthStatus.signedIn;
    } on ApiException catch (e) {
      if (e.statusCode == 401) await _service.logout();
      status = AuthStatus.signedOut;
    }
    notifyListeners();
  }

  Future<void> signIn(String email, String password) async {
    user = await _service.login(email, password);
    status = AuthStatus.signedIn;
    notifyListeners();
  }

  Future<void> register(String email, String password, {String? name}) async {
    user = await _service.register(email, password, name: name);
    status = AuthStatus.signedIn;
    notifyListeners();
  }

  Future<void> signOut() async {
    await _service.logout();
    user = null;
    status = AuthStatus.signedOut;
    notifyListeners();
  }
}

class AuthScope extends InheritedNotifier<AuthState> {
  const AuthScope({
    super.key,
    required AuthState state,
    required super.child,
  }) : super(notifier: state);

  static AuthState of(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<AuthScope>()!.notifier!;
  }
}