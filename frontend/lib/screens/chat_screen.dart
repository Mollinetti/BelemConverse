import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../config/constants.dart';
import '../providers/chat_provider.dart';
import '../providers/settings_provider.dart';
import '../widgets/message_bubble.dart';

/// Main chat screen
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 100), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }

  void _handleSubmit() {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    final settings = context.read<SettingsProvider>();
    // Ensure language code is 'pt-BR' or 'en' per OpenAPI spec
    final languageCode = settings.languageCode == 'pt' ? 'pt-BR' : settings.languageCode;
    context.read<ChatProvider>().sendMessage(
          text,
          language: languageCode,
        );

    _textController.clear();
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: _buildAppBar(),
      body: Column(
        children: [
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
              color: Colors.white.withOpacity(0.2),
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
          child: Text(
            settings.language.flag,
            style: const TextStyle(fontSize: 20),
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
                : Colors.white.withOpacity(0.5),
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
          case 'clear':
            _showClearHistoryDialog();
            break;
          case 'about':
            _showAboutDialog();
            break;
        }
      },
      itemBuilder: (context) => [
        const PopupMenuItem(
          value: 'clear',
          child: Row(
            children: [
              Icon(Icons.delete_outline, color: ParaColors.textSecondary),
              SizedBox(width: 8),
              Text('Clear history'),
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

        WidgetsBinding.instance.addPostFrameCallback((_) {
          _scrollToBottom();
        });

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.symmetric(vertical: 16),
          itemCount: chat.messages.length,
          itemBuilder: (context, index) {
            return MessageBubble(
              message: chat.messages[index],
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
                color: ParaColors.vermelho.withOpacity(0.1),
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
    final suggestions = isPortuguese
        ? [
            'Melhores restaurantes de Belém',
            'Pontos turísticos perto de mim',
            'Onde comer açaí?',
            'Hotéis bem avaliados',
          ]
        : [
            'Best restaurants in Belém',
            'Tourist spots nearby',
            'Where to eat açaí?',
            'Highly rated hotels',
          ];

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      alignment: WrapAlignment.center,
      children: suggestions.map((suggestion) {
        return ActionChip(
          label: Text(suggestion),
          backgroundColor: ParaColors.surface,
          side: BorderSide(color: ParaColors.divider),
          onPressed: () {
            _textController.text = suggestion;
            _handleSubmit();
          },
        );
      }).toList(),
    );
  }

  Widget _buildInputArea() {
    return Container(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 12,
        bottom: MediaQuery.of(context).padding.bottom + 12,
      ),
      decoration: BoxDecoration(
        color: ParaColors.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _textController,
              focusNode: _focusNode,
              maxLength: AppConstants.maxMessageLength,
              maxLines: 4,
              minLines: 1,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _handleSubmit(),
              decoration: InputDecoration(
                hintText: (context.watch<SettingsProvider>().languageCode == 'pt-BR' ||
                          context.watch<SettingsProvider>().languageCode == 'pt')
                    ? 'Digite sua pergunta...'
                    : 'Type your question...',
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
          Consumer<ChatProvider>(
            builder: (context, chat, _) {
              return FloatingActionButton(
                onPressed: chat.isLoading ? null : _handleSubmit,
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
              );
            },
          ),
        ],
      ),
    );
  }

  void _showClearHistoryDialog() {
    final settings = context.read<SettingsProvider>();
    final isPortuguese = settings.languageCode == 'pt-BR' || settings.languageCode == 'pt';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          isPortuguese ? 'Limpar histórico' : 'Clear history',
        ),
        content: Text(
          isPortuguese
              ? 'Deseja apagar todas as mensagens?'
              : 'Do you want to delete all messages?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(isPortuguese ? 'Cancelar' : 'Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              context.read<ChatProvider>().clearHistory();
              Navigator.pop(context);
            },
            child: Text(isPortuguese ? 'Limpar' : 'Clear'),
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
        
        if (!chat.selectedPlaceTypes.isEmpty || chat.openNowFilter) {
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: ParaColors.surface,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
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
      selectedColor: ParaColors.vermelho.withOpacity(0.2),
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


