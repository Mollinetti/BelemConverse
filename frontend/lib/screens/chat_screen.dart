import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../config/constants.dart';
import '../providers/chat_provider.dart';
import '../providers/settings_provider.dart';
import '../utils/input_gate.dart';
import '../widgets/button_chip.dart';
import '../widgets/message_bubble.dart';

/// Main chat screen
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  /// Example questions on the empty state; each must pass the input gate.
  static const examples = {
    'pt-BR': [
      'Melhores restaurantes de Belém',
      'Pontos turísticos perto de mim',
      'Onde comer açaí?',
      'Bares abertos agora',
    ],
    'en': [
      'Best restaurants in Belém',
      'Tourist spots nearby',
      'Where to eat açaí?',
      'Highly rated hotels',
    ],
  };

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();
  int _shownMessages = 0;

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  /// Called after the frame that added a message, so the extent is final.
  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  /// 'pt-BR' or 'en' per the OpenAPI spec.
  String get _languageCode {
    final code = context.read<SettingsProvider>().languageCode;
    return code == 'pt' ? 'pt-BR' : code;
  }

  bool get _isPortuguese => context.watch<SettingsProvider>().languageCode != 'en';

  void _handleSubmit() => _ask(_textController.text);

  void _ask(String text) {
    final chat = context.read<ChatProvider>();
    if (text.trim().isEmpty || !chat.canSend) return;
    chat.sendMessage(text, language: _languageCode);
    _textController.clear();
  }

  void _seeMore() {
    context.read<ChatProvider>().seeMore(language: _languageCode);
  }

  String _turnsLeftLabel(int n, bool pt) {
    if (pt) return n == 1 ? '1 pergunta restante' : '$n perguntas restantes';
    return n == 1 ? '1 question left' : '$n questions left';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: _buildAppBar(),
      body: Column(
        children: [
          _buildWakingBanner(),
          _buildFilterChips(),
          Expanded(child: _buildMessageList()),
          _buildInputArea(),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      title: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.chat, size: 20),
          ),
          const SizedBox(width: 10),
          const Text('BelemConverse'),
        ],
      ),
      actions: [
        _buildLanguageToggle(),
        _buildLocationButton(),
        _buildMenuButton(),
      ],
    );
  }

  Widget _buildLanguageToggle() {
    return Consumer<SettingsProvider>(
      builder: (context, settings, _) {
        return TextButton(
          onPressed: () => settings.toggleLanguage(),
          style: TextButton.styleFrom(foregroundColor: Colors.white),
          child: Tooltip(
            message: settings.language.name,
            child: Text(
              settings.language.short,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
          ),
        );
      },
    );
  }

  Widget _buildLocationButton() {
    return Consumer<ChatProvider>(
      builder: (context, chat, _) {
        return IconButton(
          icon: Icon(
            chat.useLocation ? Icons.location_on : Icons.location_off,
            color: chat.hasLocation
                ? Colors.white
                : Colors.white.withValues(alpha: 0.5),
          ),
          onPressed: () {
            chat.toggleLocation();
            if (chat.useLocation) {
              chat.requestLocation();
            }
          },
          tooltip: chat.useLocation ? 'Location enabled' : 'Location disabled',
        );
      },
    );
  }

  Widget _buildMenuButton() {
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert),
      onSelected: (value) {
        switch (value) {
          case 'new':
            context.read<ChatProvider>().newConversation();
            break;
          case 'about':
            _showAboutDialog();
            break;
        }
      },
      itemBuilder: (context) => [
        PopupMenuItem(
          value: 'new',
          child: Row(
            children: [
              const Icon(Icons.refresh, color: ParaColors.textSecondary),
              const SizedBox(width: 8),
              Text(_isPortuguese ? 'Nova conversa' : 'New conversation'),
            ],
          ),
        ),
        const PopupMenuItem(
          value: 'about',
          child: Row(
            children: [
              Icon(Icons.info_outline, color: ParaColors.textSecondary),
              SizedBox(width: 8),
              Text('About'),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildMessageList() {
    return Consumer<ChatProvider>(
      builder: (context, chat, _) {
        if (chat.messages.isEmpty) {
          return _buildEmptyState();
        }

        if (chat.messages.length != _shownMessages) {
          _shownMessages = chat.messages.length;
          WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
        }

        // Chips and "Ver mais" belong to the newest answer only.
        final latest = chat.isLoading
            ? -1
            : chat.messages.lastIndexWhere((m) => !m.isUser && !m.isLoading);
        final pt = _isPortuguese;

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.symmetric(vertical: 16),
          itemCount: chat.messages.length,
          itemBuilder: (context, index) {
            final isLatest = index == latest;
            return MessageBubble(
              message: chat.messages[index],
              onFollowUp: isLatest && chat.canSend ? _ask : null,
              onSeeMore: isLatest ? _seeMore : null,
              seeMoreLabel: pt ? 'Ver mais' : 'See more',
            );
          },
        );
      },
    );
  }

  Widget _buildEmptyState() {
    final settings = context.watch<SettingsProvider>();
    final isPortuguese = settings.languageCode == 'pt-BR' || settings.languageCode == 'pt';

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: ParaColors.vermelho.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.chat_bubble_outline,
                size: 64,
                color: ParaColors.vermelho,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              isPortuguese
                  ? 'Bem-vindo ao BelemConverse!'
                  : 'Welcome to BelemConverse!',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              isPortuguese
                  ? 'Seu guia inteligente para Belém do Pará.\nPergunte sobre restaurantes, hotéis, pontos turísticos e muito mais!'
                  : 'Your smart guide to Belém do Pará.\nAsk about restaurants, hotels, tourist spots, and more!',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: ParaColors.textSecondary,
                  ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),
            _buildSuggestions(isPortuguese),
          ],
        ),
      ),
    );
  }

  Widget _buildSuggestions(bool isPortuguese) {
    final suggestions = ChatScreen.examples[isPortuguese ? 'pt-BR' : 'en']!;

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: suggestions.map((suggestion) {
        return ButtonChip(
          label: suggestion,
          backgroundColor: ParaColors.surface,
          side: BorderSide(color: ParaColors.divider),
          onPressed: () => _ask(suggestion),
        );
      }).toList(),
    );
  }

  Widget _buildWakingBanner() {
    return Consumer<ChatProvider>(
      builder: (context, chat, _) {
        if (chat.serverReady) return const SizedBox.shrink();
        final pt = _isPortuguese;
        final text = chat.serverUnavailable
            ? (pt
                ? 'O servidor não respondeu. Recarregue a página para tentar de novo.'
                : 'The server did not respond. Reload the page to try again.')
            : (pt
                ? 'Acordando o servidor (até 1 min)…'
                : 'Waking up the server (up to 1 min)…');
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          color: ParaColors.azul.withValues(alpha: 0.08),
          child: Row(
            children: [
              if (!chat.serverUnavailable) ...[
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 12),
              ],
              Expanded(child: Text(text)),
            ],
          ),
        );
      },
    );
  }

  Widget _buildInputArea() {
    final chat = context.watch<ChatProvider>();
    final pt = _isPortuguese;
    final finished = chat.turnsLeft == 0;
    return Container(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 12,
        bottom: MediaQuery.of(context).padding.bottom + 8,
      ),
      decoration: BoxDecoration(
        color: ParaColors.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _textController,
                  focusNode: _focusNode,
                  enabled: !finished,
                  inputFormatters: inputGateFormatters,
                  maxLength: AppConstants.maxMessageLength,
                  maxLines: 4,
                  minLines: 1,
                  keyboardType: TextInputType.text,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _handleSubmit(),
                  decoration: InputDecoration(
                    hintText: finished
                        ? (pt ? 'Conversa encerrada' : 'Conversation over')
                        : (pt ? 'Digite sua pergunta...' : 'Type your question...'),
                    counterText: '',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(24),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                    fillColor: ParaColors.background,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              if (finished)
                FilledButton.icon(
                  onPressed: chat.newConversation,
                  icon: const Icon(Icons.refresh),
                  label: Text(pt ? 'Nova conversa' : 'New conversation'),
                )
              else
                FloatingActionButton(
                  onPressed: chat.canSend ? _handleSubmit : null,
                  mini: true,
                  elevation: 0,
                  child: chat.isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.send),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${pt ? 'Letras, números e , . : ? !' : 'Letters, digits and , . : ? !'}'
            ' · ${_turnsLeftLabel(chat.turnsLeft, pt)}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: ParaColors.textSecondary,
                ),
          ),
        ],
      ),
    );
  }

  void _showAboutDialog() {
    showAboutDialog(
      context: context,
      applicationName: 'BelemConverse',
      applicationVersion: '1.0.0',
      applicationIcon: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: ParaColors.vermelho,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Icon(
          Icons.chat,
          color: Colors.white,
          size: 32,
        ),
      ),
      children: [
        const Text(
          'Your AI-powered guide to Belém do Pará.\n\n'
          'Ask about restaurants, hotels, tourist spots, and more!',
        ),
      ],
    );
  }

  Widget _buildFilterChips() {
    return Consumer<ChatProvider>(
      builder: (context, chat, _) {
        final settings = context.watch<SettingsProvider>();
        final isPortuguese = settings.languageCode == 'pt-BR' || settings.languageCode == 'pt';
        
        if (chat.selectedPlaceTypes.isNotEmpty || chat.openNowFilter) {
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: ParaColors.surface,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                // Place type filters
                if (chat.selectedPlaceTypes.contains('restaurant'))
                  _buildFilterChip(
                    label: isPortuguese ? 'Restaurantes' : 'Restaurants',
                    onTap: () => chat.togglePlaceTypeFilter('restaurant'),
                    isSelected: true,
                  ),
                if (chat.selectedPlaceTypes.contains('bar'))
                  _buildFilterChip(
                    label: isPortuguese ? 'Bares' : 'Bars',
                    onTap: () => chat.togglePlaceTypeFilter('bar'),
                    isSelected: true,
                  ),
                if (chat.selectedPlaceTypes.contains('park'))
                  _buildFilterChip(
                    label: isPortuguese ? 'Parques' : 'Parks',
                    onTap: () => chat.togglePlaceTypeFilter('park'),
                    isSelected: true,
                  ),
                // Open now filter
                if (chat.openNowFilter)
                  _buildFilterChip(
                    label: isPortuguese ? 'Aberto agora' : 'Open now',
                    onTap: () => chat.toggleOpenNowFilter(),
                    isSelected: true,
                  ),
                // Clear all button
                if (chat.selectedPlaceTypes.isNotEmpty || chat.openNowFilter)
                  _buildFilterChip(
                    label: isPortuguese ? 'Limpar' : 'Clear',
                    onTap: () => chat.clearFilters(),
                    isSelected: false,
                    isClearButton: true,
                  ),
              ],
            ),
          );
        }
        
        // Show filter options when no filters are active
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildFilterChip(
                label: isPortuguese ? 'Restaurantes' : 'Restaurants',
                onTap: () => chat.togglePlaceTypeFilter('restaurant'),
                isSelected: false,
              ),
              _buildFilterChip(
                label: isPortuguese ? 'Bares' : 'Bars',
                onTap: () => chat.togglePlaceTypeFilter('bar'),
                isSelected: false,
              ),
              _buildFilterChip(
                label: isPortuguese ? 'Parques' : 'Parks',
                onTap: () => chat.togglePlaceTypeFilter('park'),
                isSelected: false,
              ),
              _buildFilterChip(
                label: isPortuguese ? 'Aberto agora' : 'Open now',
                onTap: () => chat.toggleOpenNowFilter(),
                isSelected: false,
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildFilterChip({
    required String label,
    required VoidCallback onTap,
    required bool isSelected,
    bool isClearButton = false,
  }) {
    return FilterChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (_) => onTap(),
      backgroundColor: ParaColors.surface,
      selectedColor: ParaColors.vermelho.withValues(alpha: 0.2),
      checkmarkColor: ParaColors.vermelho,
      labelStyle: TextStyle(
        color: isSelected ? ParaColors.vermelho : ParaColors.textPrimary,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        fontSize: 12,
      ),
      side: BorderSide(
        color: isSelected ? ParaColors.vermelho : ParaColors.divider,
        width: isSelected ? 1.5 : 1,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }
}


