import 'dart:convert';

import 'package:belem_converse/providers/chat_provider.dart';
import 'package:belem_converse/services/api_service.dart';
import 'package:belem_converse/services/location_service.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class NoLocation extends LocationService {
  @override
  Future<Position?> getCurrentPosition() async => null;
}

/// A scripted backend behind a MockClient: 4 turns per session, 12 results.
class FakeBackend {
  bool healthy;
  int healthChecks = 0;
  final sent = <Map<String, dynamic>>[];
  final _turnsUsed = <String, int>{};
  final _shown = <String, int>{};
  List<String> followUps;

  FakeBackend({this.healthy = true, this.followUps = const ['Abertos agora', 'Cafés']});

  http.Client get client => MockClient((request) async {
        if (request.url.path.endsWith('/health')) {
          healthChecks++;
          return _json({'status': healthy ? 'healthy' : 'initializing'});
        }
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        sent.add(body);
        final session = body['session_id'] as String;
        final used = _turnsUsed[session] ?? 0;
        if (body['action'] == 'more') {
          final from = _shown[session] ?? 0;
          _shown[session] = (from + 5).clamp(0, 12);
          return _json(_answer(from, _shown[session]!, 4 - used, const []));
        }
        if (used >= 4) return _json({'code': 'conversation_finished', 'turns_left': 0}, 409);
        _turnsUsed[session] = used + 1;
        _shown[session] = 5;
        return _json(_answer(0, 5, 3 - used, followUps));
      });

  Map<String, dynamic> _answer(int from, int to, int turnsLeft, List<String> chips) => {
        'language': 'pt-BR',
        'answer': 'Resposta',
        'results': [
          for (var i = from; i < to; i++) {'placeId': 'p$i', 'title': 'Lugar $i', 'place_type': 'bar'},
        ],
        'follow_ups': chips,
        'has_more': to < 12,
        'turns_left': turnsLeft,
      };

  static http.Response _json(Object body, [int status = 200]) => http.Response(
        jsonEncode(body),
        status,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );

  ChatProvider provider() => ChatProvider(
        apiService: ApiService(client: client),
        locationService: NoLocation(),
      );
}
