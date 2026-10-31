import 'dart:convert';

import 'package:calibre/config.dart';
import 'package:calibre/models/user.dart';
import 'package:calibre/services/api_exception.dart';
import 'package:calibre/services/token_storage.dart';
import 'package:http/http.dart' as http;

class AuthService {
  final TokenStorage _tokens;

  AuthService(this._tokens);

  Future<User> register(String email, String password, {String? name}) async {
    final body = <String, dynamic>{'email': email, 'password': password};
    if (name != null && name.isNotEmpty) {
      body['name'] = name;
    }
    final data = await _post('/auth/register/', body);
    await _tokens.saveTokens(data['access'], data['refresh']);
    return User.fromJson(data['user']);
  }

  Future<User> login(String email, String password) async {
    final data = await _post('/auth/login/', {
      'email': email,
      'password': password,
    });
    await _tokens.saveTokens(data['access'], data['refresh']);
    return User.fromJson(data['user']);
  }

  Future<User> me() async {
    final access = await _tokens.readAccess();
    if (access == null) {
      throw ApiException('Not signed in', 401);
    }
    final response = await _send(
      () => http.get(
        Uri.parse('$baseUrl/users/me/'),
        headers: _headers(access),
      ),
    );
    return User.fromJson(_decode(response));
  }

  Future<void> logout() async {
    final access = await _tokens.readAccess();
    final refresh = await _tokens.readRefresh();
    if (refresh != null) {
      try {
        await _send(
          () => http.post(
            Uri.parse('$baseUrl/auth/logout/'),
            headers: _headers(access),
            body: jsonEncode({'refresh': refresh}),
          ),
        );
      } on ApiException {
        
      }
    }
    await _tokens.clear();
  }

  Map<String, String> _headers(String? access) {
    return {
      'Content-Type': 'application/json',
      if (access != null) 'Authorization': 'Bearer $access',
    };
  }

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await _send(
      () => http.post(
        Uri.parse('$baseUrl$path'),
        headers: _headers(null),
        body: jsonEncode(body),
      ),
    );
    return _decode(response);
  }

  Future<http.Response> _send(Future<http.Response> Function() request) async {
    try {
      return await request().timeout(const Duration(seconds: 15));
    } catch (_) {
      throw ApiException('Cannot reach the server. Check your connection.');
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) {
        return {};
      }
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw ApiException(_errorMessage(response), response.statusCode);
  }

  String _errorMessage(http.Response response) {
    if (response.statusCode == 429) {
      return 'Too many attempts. Wait a minute and try again.';
    }
    try {
      final data = jsonDecode(response.body);
      if (data is Map<String, dynamic>) {
        if (data['detail'] is String) {
          return data['detail'] as String;
        }
        final parts = <String>[];
        data.forEach((key, value) {
          final text = value is List && value.isNotEmpty
              ? value.first.toString()
              : value.toString();
          parts.add(key == 'non_field_errors' ? text : '$key: $text');
        });
        if (parts.isNotEmpty) {
          return parts.join('\n');
        }
      }
    } catch (_) {}
    return 'Something went wrong (${response.statusCode}).';
  }
}