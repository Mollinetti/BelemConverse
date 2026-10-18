import 'package:belem_converse/config/constants.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fakes.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('counts down to 0 and then cannot send', () async {
    final chat = FakeBackend().provider();

    for (var i = 0; i < AppConstants.maxTurns; i++) {
      expect(chat.canSend, isTrue);
      await chat.sendMessage('bares', language: 'pt-BR');
    }

    expect(chat.turnsLeft, 0);
    expect(chat.canSend, isFalse);
  });

  test('a 5th question is not sent', () async {
    final backend = FakeBackend();
    final chat = backend.provider();
    for (var i = 0; i < 5; i++) {
      await chat.sendMessage('bares', language: 'pt-BR');
    }

    expect(backend.sent.length, 4);
  });

  test('Nova conversa starts a fresh session', () async {
    final chat = FakeBackend().provider();
    await chat.sendMessage('bares', language: 'pt-BR');
    final oldSession = chat.sessionId;

    chat.newConversation();

    expect(chat.sessionId, isNot(oldSession));
    expect(chat.messages, isEmpty);
    expect(chat.turnsLeft, AppConstants.maxTurns);
  });

  test('every request carries the session id', () async {
    final backend = FakeBackend();
    final chat = backend.provider();

    await chat.sendMessage('bares', language: 'pt-BR');
    await chat.seeMore(language: 'pt-BR');

    expect(backend.sent.map((b) => b['session_id']).toSet(), {chat.sessionId});
  });

  test('see more appends results without spending a question', () async {
    final backend = FakeBackend();
    final chat = backend.provider();
    await chat.sendMessage('bares', language: 'pt-BR');
    final turnsLeft = chat.turnsLeft;

    await chat.seeMore(language: 'pt-BR');

    expect(backend.sent.last['action'], 'more');
    expect(chat.turnsLeft, turnsLeft);
    expect(chat.messages.last.places.map((p) => p.placeId), ['p5', 'p6', 'p7', 'p8', 'p9']);
    // The follow-ups stay offered under the newest answer.
    expect(chat.messages.last.followUps, ['Abertos agora', 'Cafés']);
  });

  test('a reload starts fresh: no history is restored', () async {
    SharedPreferences.setMockInitialValues({
      'chat_history': '[{"id":"1","content":"old","isUser":true,"timestamp":"2026-01-01T00:00:00"}]',
    });
    final chat = FakeBackend().provider();

    await chat.initialize();

    expect(chat.messages, isEmpty);
  });

  testWidgets('waking up: not ready until health answers', (tester) async {
    final backend = FakeBackend(healthy: false);
    final chat = backend.provider();

    chat.initialize();
    await tester.pump(const Duration(seconds: 10));
    expect(chat.serverReady, isFalse);

    backend.healthy = true;
    await tester.pump(const Duration(seconds: 3));
    expect(chat.serverReady, isTrue);
    expect(chat.serverUnavailable, isFalse);
  });

  testWidgets('waking up: polling stops at 90 s', (tester) async {
    final backend = FakeBackend(healthy: false);
    final chat = backend.provider();

    chat.initialize();
    await tester.pump(const Duration(seconds: 91));
    final checks = backend.healthChecks;
    await tester.pump(const Duration(seconds: 60));

    expect(checks, inInclusiveRange(29, 31));
    expect(backend.healthChecks, checks);
    expect(chat.serverReady, isFalse);
    expect(chat.serverUnavailable, isTrue);
  });
}
