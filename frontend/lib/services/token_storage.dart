import 'package:flutter_secure_storage/flutter_secure_storage.dart';


class TokenStorage {

  static const String _accessKey = 'access_token';
  static const String _refreshKey = 'refresh_token';

  final FlutterSecureStorage _storage = FlutterSecureStorage(
    mOptions: MacOsOptions(usesDataProtectionKeychain: false),
  );

  Future<void> saveTokens(String access, String refresh) async {
    await _storage.write(key: _accessKey, value: access);
    await _storage.write(key: _refreshKey, value: refresh);
  }

  Future<String?> readAccess(){
    return _storage.read(key: _accessKey);
  }

  Future<String?> readRefresh(){
    return _storage.read(key: _refreshKey);
  }

  Future<void> clear() async{
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }



}
