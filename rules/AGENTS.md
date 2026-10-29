# Memória Persistente Honcho

Você possui memória persistente conectada através do plugin **Honcho**:

- **Captura automática ativa:** Os Lifecycle Hooks (`SessionStart` e `Stop`) já injetam o contexto inicial da sessão e gravam automaticamente as mensagens do usuário e suas respostas finais ao término de cada turno. Não chame ferramentas manuais para duplicar o histórico do chat.
- **Consulta proativa:** Quando contexto de conversas passadas, decisões arquiteturais anteriores ou preferências do usuário puderem ajudar, use as ferramentas do servidor MCP `honcho` (`get_peer_context`, `query_conclusions`, `search`, `chat` ou `workspace_chat`) antes de pedir para o usuário repetir informações.
- **Preferências duráveis:** Sempre que o usuário declarar uma preferência duradoura, convenção de código ou decisão arquitetural importante, registre-a imediatamente com `create_conclusions` (omitindo qualquer chave/segredo).
