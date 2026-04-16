import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config/theme.dart';
import 'providers/chat_provider.dart';
import 'providers/settings_provider.dart';
import 'screens/chat_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const BelemConverseApp());
}

class BelemConverseApp extends StatelessWidget {
  const BelemConverseApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => SettingsProvider()..initialize(),
        ),
        ChangeNotifierProvider(
          create: (_) => ChatProvider()..initialize(),
        ),
      ],
      child: Consumer<SettingsProvider>(
        builder: (context, settings, _) {
          return MaterialApp(
            title: 'BelemConverse',
            debugShowCheckedModeBanner: false,
            theme: AppTheme.lightTheme,
            home: const ChatScreen(),
          );
        },
      ),
    );
  }
}
