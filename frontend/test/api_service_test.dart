import 'dart:convert';

import 'package:belem_converse/services/api_service.dart';
import 'package:belem_converse/utils/session_id.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const sessionId = '3f1c2b9e-8d4a-4c6e-9b1a-2e7f5d0c4a11';

Map<String, dynamic> answer({
  List<String> followUps = const ['Abertos agora', 'Cafés'],
  bool hasMore = true,
  int turnsLeft = 3,
}) =>
    {
      'language': 'pt-BR',
      'answer': 'Recomendo o Bar Um.',
      'results': [
        {'placeId': 'p1', 'title': 'Bar Um', 'place_type': 'bar'},
      ],
      'follow_ups': followUps,
      'has_more': hasMore,
      'turns_left': turnsLeft,
    };

http.Response ok(Object body) => http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      200,
      headers: {'content-type': 'application/json; charset=utf-8'},
    );

void main() {
  test('sends the session id with a question', () async {
    late Map<String, dynamic> sent;
    final api = ApiService(
      client: MockClient((request) async {
        sent = jsonDecode(request.body) as Map<String, dynamic>;
        return ok(answer());
      }),
    );

    await api.sendMessage(message: 'bares', language: 'pt-BR', sessionId: sessionId);

    expect(sent['session_id'], sessionId);
    expect(sent['message'], 'bares');
    expect(sent.containsKey('action'), isFalse);
  });

  test('sends action more and no message when paging', () async {
    late Map<String, dynamic> sent;
    final api = ApiService(
      client: MockClient((request) async {
        sent = jsonDecode(request.body) as Map<String, dynamic>;
        return ok(answer());
      }),
    );

    await api.sendMessage(language: 'pt-BR', sessionId: sessionId, action: 'more');

    expect(sent['session_id'], sessionId);
    expect(sent['action'], 'more');
    expect(sent.containsKey('message'), isFalse);
  });

  test('parses follow-ups, has_more and turns_left', () async {
    final api = ApiService(
      client: MockClient(
        (_) async => ok(answer(turnsLeft: 2)),
      ),
    );

    final message = await api.sendMessage(message: 'bares', language: 'pt-BR', sessionId: sessionId);

    expect(message.content, 'Recomendo o Bar Um.');
    expect(message.places.single.title, 'Bar Um');
    expect(message.followUps, ['Abertos agora', 'Cafés']);
    expect(message.hasMore, isTrue);
    expect(message.turnsLeft, 2);
  });

  for (final (status, matcher) in [
    (409, isA<ConversationFinished>()),
    (429, isA<TooManyRequests>()),
    (422, isA<InvalidInput>()),
  ]) {
    test('maps HTTP $status', () async {
      final api = ApiService(
        client: MockClient(
          (_) async => http.Response('{"code": "conversation_finished", "detail": []}', status),
        ),
      );

      expect(
        api.sendMessage(message: 'bares', language: 'pt-BR', sessionId: sessionId),
        throwsA(matcher),
      );
    });
  }

  test('maps 409 no_previous_results apart from a finished conversation', () async {
    final api = ApiService(
      client: MockClient((_) async => http.Response('{"code": "no_previous_results"}', 409)),
    );

    expect(
      api.sendMessage(language: 'pt-BR', sessionId: sessionId, action: 'more'),
      throwsA(isA<NoPreviousResults>()),
    );
  });

  test('newSessionId makes unique UUID v4s', () {
    final uuidV4 = RegExp(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$');
    final ids = List.generate(1000, (_) => newSessionId());

    expect(ids.every(uuidV4.hasMatch), isTrue);
    expect(ids.toSet().length, 1000);
  });
}
