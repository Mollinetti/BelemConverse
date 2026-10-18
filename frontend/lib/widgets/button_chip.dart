import 'package:flutter/material.dart';

/// An [ActionChip] that assistive technology announces as a plain button.
///
/// Flutter marks every chip as selectable, which the web engine turns into
/// role="checkbox" aria-checked="false": a screen reader would read
/// "Ver mais, checkbox, not checked" for what is an ordinary button.
class ButtonChip extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final Widget? avatar;
  final Color? backgroundColor;
  final BorderSide? side;

  const ButtonChip({
    super.key,
    required this.label,
    required this.onPressed,
    this.avatar,
    this.backgroundColor,
    this.side,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      enabled: onPressed != null,
      label: label,
      onTap: onPressed,
      excludeSemantics: true,
      child: ActionChip(
        avatar: avatar,
        label: Text(label),
        backgroundColor: backgroundColor,
        side: side,
        onPressed: onPressed,
      ),
    );
  }
}
