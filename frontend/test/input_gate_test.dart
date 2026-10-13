import 'package:belem_converse/utils/input_gate.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// The text left after typing or pasting [text] into an empty gated field.
String typed(String text) {
  var value = TextEditingValue(
    text: text,
    selection: TextSelection.collapsed(offset: text.length),
  );
  for (final formatter in inputGateFormatters) {
    value = formatter.formatEditUpdate(TextEditingValue.empty, value);
  }
  return value.text;
}

void main() {
  test('keeps letters with accents, digits, spaces and , . : ? !', () {
    expect(typed('Praça da República, 20:00.'), 'Praça da República, 20:00.');
    expect(typed('Onde tem açaí?!'), 'Onde tem açaí?!');
  });

  test('strips other symbols, markup, newlines and emoji', () {
    expect(typed('Onde tem açaí?! "já" <>{}[];/@#*-_\n🍕 agora'), 'Onde tem açaí?! já  agora');
  });

  test('a pasted script loses its brackets', () {
    expect(typed('<script>alert(1)</script>'), 'scriptalert1script');
  });

  test('truncates at 400 characters', () {
    expect(typed('a' * 600).length, 400);
  });
}
