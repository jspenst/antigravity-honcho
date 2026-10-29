# Antigravity Honcho Plugin

<div align="center">
  <img src="assets/logo.svg" alt="Honcho Logo" width="120" />
  <p><strong>Memória persistente, raciocínio em segundo plano e cognição social para o Google Antigravity.</strong></p>
</div>

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Antigravity](https://img.shields.io/badge/Antigravity-2.0+-purple.svg)](https://antigravity.google)
[![Honcho](https://img.shields.io/badge/Honcho-v3-blue.svg)](https://honcho.dev)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://python.org)

Este plugin integra o [Honcho](https://honcho.dev) diretamente ao **Google Antigravity**, fornecendo:
* **Captura automática e transparente:** Sem precisar chamar ferramentas manuais, cada turno do diálogo é salvo no Honcho com redação automática de tokens/senhas e colapso de código extenso.
* **Recall na inicialização de conversas:** Ao abrir um chat, o Antigravity recebe o seu *Peer Card*, o perfil de usuário e o resumo do projeto automaticamente.
* **Servidor MCP completo e ultrarrápido:** Ferramentas sob demanda para buscar conversas passadas (`search`), consultar o agente dialético (`chat`, `workspace_chat`) e gravar preferências duradouras (`create_conclusions`).
* **Zero dependências externas:** O plugin roda em Python nativo com a biblioteca padrão (`urllib`, `json`, `pathlib`), sem precisar compilar Node/Bun na máquina cliente e sem risco de quebrar no boot.

---

## Instalação Rápida

### Opção 1: Via Git (Recomendada)

Clone o repositório diretamente na pasta de plugins do Antigravity:

**No Windows (PowerShell):**
```powershell
git clone https://github.com/<seu-usuario>/antigravity-honcho.git "$env:USERPROFILE\.gemini\config\plugins\honcho"
```

**No Linux / macOS (Bash):**
```bash
git clone https://github.com/<seu-usuario>/antigravity-honcho.git ~/.gemini/config/plugins/honcho
```

### Opção 2: Instalador em 1 linha

**Windows:**
```powershell
irm https://raw.githubusercontent.com/<seu-usuario>/antigravity-honcho/main/install.ps1 | iex
```

**Linux / macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/<seu-usuario>/antigravity-honcho/main/install.sh | bash
```

### Opção 3: Por Projeto / Equipe

Se você deseja compartilhar o plugin com o seu time através do repositório do projeto, coloque a pasta em:
```text
seu-projeto/
└── .agents/
    └── plugins/
        └── honcho/
```
Qualquer desenvolvedor com Antigravity que abrir o projeto terá o Honcho ativado automaticamente.

> **Importante:** Após instalar, reinicie o Antigravity para que o novo plugin seja descoberto.

---

## Ferramentas MCP Disponíveis

| Ferramenta | Descrição |
| :--- | :--- |
| `get_peer_context` | Retorna o Peer Card e a Representação consolidada do usuário |
| `chat` | Faz perguntas em linguagem natural sobre o usuário ao modelo do Honcho |
| `workspace_chat` | Pergunta transversal cruzando dados de todo o workspace |
| `search` | Busca híbrida (semântica + BM25) nas mensagens e conversas salvas |
| `query_conclusions` | Busca semântica nos fatos e preferências inferidos pelo Honcho |
| `list_conclusions` | Lista as conclusões mais recentes extraídas pelo sistema |
| `create_conclusions` | Salva imediatamente uma nova preferência durável ou decisão técnica |

---

## Configuração

O plugin lê automaticamente `~/.honcho/config.json` (compartilhado com Claude Code, Cursor, Codex e Honcho CLI) ou variáveis de ambiente:

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `HONCHO_URL` | `http://127.0.0.1:8000` | URL do backend Honcho (local, Docker ou Tailscale) |
| `HONCHO_API_KEY` | *(vazio)* | Chave de API (opcional para self-hosted com `AUTH_USE_AUTH=false`) |
| `HONCHO_WORKSPACE_ID` | `antigravity` | Workspace do Honcho onde os dados são gravados |
| `HONCHO_PEER_NAME` | `<usuário do SO>` | Nome do seu peer humano |
| `HONCHO_SESSION_STRATEGY` | `project` | `project` (sessão persistente por repositório) ou `conversation` (sessão por chat) |

### Exemplo de `~/.honcho/config.json`:
```json
{
  "schemaVersion": 1,
  "baseUrl": "http://127.0.0.1:8000",
  "workspace": "antigravity",
  "peerName": "developer",
  "enabled": true
}
```

---

## Validação e Diagnóstico

Para testar a conectividade com o Honcho a qualquer momento:

```powershell
python honcho_hook.py --test
```

Saída esperada:
```text
=== Diagnóstico Antigravity <-> Honcho ===
Ativo (enabled)   : True
Honcho Base URL   : http://127.0.0.1:8000
Workspace ID      : antigravity
Peer do Usuário   : developer
Peer do Agente    : antigravity
Estratégia Sessão : project
Arquivo de Estado : C:\Users\...\.honcho\antigravity_state.json
Servidor Online   : SIM
```

---

## Licença

Distribuído sob a licença [MIT](LICENSE).
