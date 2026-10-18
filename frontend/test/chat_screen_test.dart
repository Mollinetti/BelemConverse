import 'package:belem_converse/providers/chat_provider.dart';
import 'package:belem_converse/providers/settings_provider.dart';
import 'package:belem_converse/screens/chat_screen.dart';
import 'package:belem_converse/utils/input_gate.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fakes.dart';

Future<ChatProvider> pumpChat(WidgetTester tester, FakeBackend backend) async {
  // Tall enough that every message is built, so "findsNothing" means hidden.
  tester.view.physicalSize = const Size(1080, 8000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({'language': 'pt-BR'});
  final settings = SettingsProvider();
  await settings.initialize();
  final chat = backend.provider();
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: settings),
        ChangeNotifierProvider.value(value: chat),
      ],
      child: const MaterialApp(home: ChatScreen()),
    ),
  );
  chat.initialize();
  await tester.pump();
  return chat;
}

Future<void> ask(WidgetTester tester, ChatProvider chat, [String text = 'bares']) async {
  await chat.sendMessage(text, language: 'pt-BR');
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows the title and the questions left', (tester) async {
    final chat = await pumpChat(tester, FakeBackend());

    expect(find.text('BelemConverse'), findsOneWidget);
    expect(find.textContaining('4 perguntas restantes'), findsOneWidget);

    await ask(tester, chat);
    expect(find.textContaining('3 perguntas restantes'), findsOneWidget);
  });

  testWidgets('follow-up chips and Ver mais under the answer', (tester) async {
    final chat = await pumpChat(tester, FakeBackend());

    await ask(tester, chat);

    expect(find.widgetWithText(ActionChip, 'Abertos agora'), findsOneWidget);
    expect(find.widgetWithText(ActionChip, 'Cafés'), findsOneWidget);
    expect(find.widgetWithText(ActionChip, 'Ver mais'), findsOneWidget);
  });

  testWidgets('Ver mais disappears when the results run out', (tester) async {
    final chat = await pumpChat(tester, FakeBackend());
    await ask(tester, chat);

    await tester.tap(find.widgetWithText(ActionChip, 'Ver mais'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(ActionChip, 'Ver mais'), findsOneWidget);

    await tester.tap(find.widgetWithText(ActionChip, 'Ver mais'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(ActionChip, 'Ver mais'), findsNothing);
    expect(chat.turnsLeft, 3);
  });

  testWidgets('chips only under the latest answer', (tester) async {
    final backend = FakeBackend(followUps: ['Abertos agora']);
    final chat = await pumpChat(tester, backend);
    await ask(tester, chat);

    backend.followUps = ['Bares'];
    await ask(tester, chat, 'restaurantes');

    expect(find.widgetWithText(ActionChip, 'Bares'), findsOneWidget);
    expect(find.widgetWithText(ActionChip, 'Abertos agora'), findsNothing);
    expect(find.widgetWithText(ActionChip, 'Ver mais'), findsOneWidget);
  });

  testWidgets('tapping a chip asks it as a question', (tester) async {
    final backend = FakeBackend();
    final chat = await pumpChat(tester, backend);
    await ask(tester, chat);

    await tester.tap(find.widgetWithText(ActionChip, 'Abertos agora'));
    await tester.pumpAndSettle();

    expect(backend.sent.last['message'], 'Abertos agora');
    expect(chat.turnsLeft, 2);
  });

  testWidgets('at 0 questions left the input is off and Nova conversa shows', (tester) async {
    final chat = await pumpChat(tester, FakeBackend());
    for (var i = 0; i < 4; i++) {
      await ask(tester, chat);
    }

    expect(tester.widget<TextField>(find.byType(TextField)).enabled, isFalse);
    expect(find.widgetWithText(ActionChip, 'Abertos agora'), findsNothing);

    await tester.tap(find.text('Nova conversa'));
    await tester.pumpAndSettle();

    expect(chat.turnsLeft, 4);
    expect(tester.widget<TextField>(find.byType(TextField)).enabled, isTrue);
  });

  testWidgets('waking-up banner until the server answers', (tester) async {
    final backend = FakeBackend(healthy: false);
    await pumpChat(tester, backend);

    expect(find.textContaining('Acordando o servidor'), findsOneWidget);

    backend.healthy = true;
    await tester.pump(const Duration(seconds: 4));

    expect(find.textContaining('Acordando o servidor'), findsNothing);
  });

  testWidgets('chips are announced as buttons, not checkboxes', (tester) async {
    final semantics = tester.ensureSemantics();
    final chat = await pumpChat(tester, FakeBackend());
    expect(
      tester.getSemantics(find.text('Onde comer açaí?')),
      containsSemantics(label: 'Onde comer açaí?', isButton: true, hasTapAction: true, isFocusable: true, hasCheckedState: false, hasSelectedState: false),
    );

    await ask(tester, chat);

    for (final label in ['Ver mais', 'Abertos agora']) {
      expect(
        tester.getSemantics(find.text(label)),
        containsSemantics(label: label, isButton: true, hasTapAction: true, isFocusable: true, hasCheckedState: false, hasSelectedState: false),
      );
    }
    semantics.dispose();
  });

  test('every example question passes the input gate', () {
    for (final example in ChatScreen.examples.values.expand((e) => e)) {
      expect(example.replaceAll(allowedChars, ''), isEmpty, reason: example);
    }
  });
}
