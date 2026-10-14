
const List<String> monthnames = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const List<String> shortmonth = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

const List<String> weekdaynames = [
  'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'
];

const List<String> fullweekdaynames =[
  'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
];


DateTime dateOnly(DateTime d){

  //Get input date with time = 0:0:0 
  //Used for comparisons etc.
  return DateTime(d.year,d.month,d.day);

}


bool isSameDay(DateTime d1, DateTime d2){

  //used for comapring two datetimes

  return d1.year==d2.year && d1.month == d2.month && d1.day == d2.day;

}



String formatDateString(DateTime d){
  return '${weekdaynames[d.weekday -1]},${d.day} ${monthnames[d.month-1]} ${d.year}';
}

String hourlabel(int hour) {
  final h = hour % 12 == 0 ? 12 : hour % 12;
  final suffix = hour < 12 ? 'AM' : 'PM';
  return '$h $suffix';
}


String fullWeekdayName(DateTime d){

  return fullweekdaynames[d.weekday-1];
}

String month(DateTime d){
  return shortmonth[d.month-1];
}

DateTime addDays(DateTime d, int n){
  return DateTime(d.year, d.month, d.day +n);
}

DateTime startofweek(DateTime d){
  int startDays = 1-d.weekday;

  return addDays(d, startDays);
}