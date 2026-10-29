# Honcho Persistent Memory

You have persistent memory connected via the **Honcho** plugin:

- **Active automatic capture:** Lifecycle Hooks (`SessionStart` and `Stop`) automatically inject initial session context and record user messages and your final responses at the end of each turn. Do not call manual tools to duplicate chat history.
- **Proactive querying:** When past conversation context, prior architectural decisions, or user preferences can help, use the `honcho` MCP server tools (`get_peer_context`, `query_conclusions`, `search`, `chat`, or `workspace_chat`) before asking the user to repeat information.
- **Durable preferences:** Whenever the user states a lasting preference, code convention, or significant architectural decision, immediately record it with `create_conclusions` (omitting any keys/secrets).
