import 'dart:convert';
import 'dart:math';

import 'package:calibre/services/api_exception.dart';
import 'package:flutter/services.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';

class MoodleToken {
  final String signature;
  final String token;
  final String? privateToken;
  final String passport;

  const MoodleToken({
    required this.signature,
    required this.token,
    required this.privateToken,
    required this.passport,
  });
}

class MoodleService {
  static const String _site = 'https://moodle.iitb.ac.in';
  static const String _scheme = 'moodlemobile';

  String _newPassport() {
    final random = Random.secure();
    return List.generate(16, (_) => random.nextInt(16).toRadixString(16)).join();
  }

  Future<MoodleToken> fetchToken() async {
    final passport = _newPassport();
    final loginUri = Uri.parse('$_site/admin/tool/mobile/launch.php').replace(
      queryParameters: {
        'service': 'moodle_mobile_app',
        'passport': passport,
      },
    );

    String callback;
    try {
      callback = await FlutterWebAuth2.authenticate(
        url: loginUri.toString(),
        callbackUrlScheme: _scheme,
      );
    } on PlatformException {
      throw ApiException('Moodle sign-in was cancelled.');
    }

    final marker = callback.indexOf('token=');
    if (marker == -1) {
      throw ApiException('Moodle did not return a token.');
    }
    var encoded = callback.substring(marker + 6);
    if (encoded.contains('%')) {
      encoded = Uri.decodeComponent(encoded);
    }

    final String decoded;
    try {
      decoded = utf8.decode(base64.decode(base64.normalize(encoded)));
    } catch (_) {
      throw ApiException('Moodle returned a token in an unexpected format.');
    }

    final parts = decoded.split(':::');
    if (parts.length < 2) {
      throw ApiException('Moodle returned a token in an unexpected format.');
    }
    return MoodleToken(
      signature: parts[0],
      token: parts[1],
      privateToken: parts.length > 2 ? parts[2] : null,
      passport: passport,
    );
  }
}