import 'package:flutter_test/flutter_test.dart';
import 'package:belem_converse/main.dart';

void main() {
  testWidgets('App loads successfully', (WidgetTester tester) async {
    await tester.pumpWidget(const BelemConverseApp());
    
    // Verify the app title is present
    expect(find.text('BelemConverse'), findsOneWidget);
  });
}
