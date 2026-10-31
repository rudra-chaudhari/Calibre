class User {
  final int id;
  final String email;
  final String name;
  final String timezone;
  final String workStart;
  final String workEnd;
  final DateTime dateJoined;

  const User({
    required this.id,
    required this.email,
    required this.name,
    required this.timezone,
    required this.workStart,
    required this.workEnd,
    required this.dateJoined,

  });

 factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as int,
      email: json['email'] as String,
      name: (json['name'] as String?) ?? '',
      timezone: json['timezone'] as String,
      workStart: json['work_start'] as String,
      workEnd: json['work_end'] as String,
      dateJoined: DateTime.parse(json['date_joined'] as String),
    );

}

}