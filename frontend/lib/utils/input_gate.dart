import 'package:flutter/services.dart';

import '../config/constants.dart';

/// Characters a question may contain: letters (with accents), digits, spaces
/// and `, . : ? !`. The server applies the same rule (belem_converse/gate.py).
final allowedChars = RegExp(r'[\p{L}\p{N} ,.:?!]', unicode: true);

/// Drops anything else as it is typed or pasted, and stops at 400 characters.
final inputGateFormatters = <TextInputFormatter>[
  FilteringTextInputFormatter.allow(allowedChars),
  LengthLimitingTextInputFormatter(AppConstants.maxMessageLength),
];
