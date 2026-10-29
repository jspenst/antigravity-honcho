#!/usr/bin/env python3
"""
Servidor MCP local (Stdio) para o plugin Honcho no Antigravity.

Fala diretamente com a API v3 do Honcho (ex.: http://127.0.0.1:8000) usando
apenas a biblioteca padrão do Python, compartilhando a mesma configuração
de `honcho_hook.py` (`~/.honcho/config.json` e variáveis `HONCHO_*`).

Vantagem: inicializa instantaneamente mesmo que o Docker do Honcho ainda não
esteja rodando no momento em que o Antigravity abre.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from honcho_hook import (  # noqa: E402
    PLUGIN_VERSION,
    HonchoRestClient,
    load_config,
    redact_secrets,
    sanitize_id,
)

SUPPORTED_PROTOCOLS = ("2025-03-26", "2024-11-05")

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_peer_context",
        "description": (
            "Retorna o Peer Card e a Representação consolidada que o Honcho aprendeu "
            "sobre o usuário (ou outro peer). Use no início de tarefas ou para revisar preferências."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "peer_id": {
                    "type": "string",
                    "description": "ID do peer (opcional; padrão: peer do usuário configurado).",
                },
                "search_query": {
                    "type": "string",
                    "description": "Filtro semântico opcional para focar a representação em um tema.",
                },
                "max_conclusions": {
                    "type": "integer",
                    "description": "Máximo de conclusões incluídas (1-100, padrão: 20).",
                },
            },
        },
    },
    {
        "name": "chat",
        "description": (
            "Faz uma pergunta em linguagem natural ao agente dialético do Honcho sobre o usuário "
            "(ex.: 'Quais são as preferências de arquitetura e ferramentas do usuário?')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pergunta em linguagem natural.",
                },
                "peer_id": {
                    "type": "string",
                    "description": "ID do peer consultado (opcional; padrão: peer do usuário).",
                },
                "session_id": {
                    "type": "string",
                    "description": "Opcional: restringir a resposta a uma sessão específica.",
                },
                "reasoning_level": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": "Nível de profundidade do raciocínio (padrão: low).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "workspace_chat",
        "description": (
            "Faz uma pergunta transversal em todo o workspace do Honcho (cruzando múltiplos projetos/sessões)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pergunta em linguagem natural sobre o workspace/projetos.",
                },
                "reasoning_level": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": "Nível de raciocínio (padrão: low).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search",
        "description": (
            "Busca híbrida (semântica + palavras-chave) nas mensagens gravadas de conversas anteriores."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo ou pergunta para buscar nas conversas passadas.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Opcional: filtrar apenas dentro de uma sessão específica.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Número máximo de mensagens retornadas (1-50, padrão: 10).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_conclusions",
        "description": (
            "Busca semântica nas conclusões/fatos derivados pelo Honcho sobre o usuário."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta semântica (ex.: 'estilo de código', 'banco de dados').",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Quantidade máxima de conclusões (1-50, padrão: 10).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_conclusions",
        "description": "Lista as conclusões mais recentes extraídas sobre o usuário.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "size": {
                    "type": "integer",
                    "description": "Quantidade de itens por página (1-100, padrão: 20).",
                },
                "session_id": {
                    "type": "string",
                    "description": "Opcional: listar apenas conclusões ligadas a esta sessão.",
                },
            },
        },
    },
    {
        "name": "create_conclusions",
        "description": (
            "Salva imediatamente uma ou mais conclusões/preferências duráveis sobre o usuário no Honcho."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "conclusions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de fatos ou preferências concisas e autocontidas para memorizar.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Opcional: ID da sessão onde a preferência surgiu.",
                },
            },
            "required": ["conclusions"],
        },
    },
]


def _text_result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    client = HonchoRestClient(cfg)
    ws = urllib.parse.quote(cfg.workspace, safe="")

    try:
        # Garante workspace ativo antes de operações de escrita/consulta
        client._request("POST", "/v3/workspaces", body={"id": cfg.workspace}, timeout=5.0)

        if name == "get_peer_context":
            peer_id = sanitize_id(str(args.get("peer_id") or cfg.user_peer), cfg.user_peer)
            pid = urllib.parse.quote(peer_id, safe="")
            query: dict[str, Any] = {
                "max_conclusions": int(args.get("max_conclusions") or 20),
            }
            if args.get("search_query"):
                query["search_query"] = str(args["search_query"])
            try:
                res = client._request("GET", f"/v3/workspaces/{ws}/peers/{pid}/context", query=query, timeout=15.0)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return _text_result({"peer_id": peer_id, "peer_card": [], "representation": ""})
                raise
            return _text_result(res)

        if name == "chat":
            peer_id = sanitize_id(str(args.get("peer_id") or cfg.user_peer), cfg.user_peer)
            pid = urllib.parse.quote(peer_id, safe="")
            body: dict[str, Any] = {
                "query": str(args["query"]),
                "stream": False,
            }
            if args.get("session_id"):
                body["session_id"] = str(args["session_id"])
            if args.get("reasoning_level"):
                body["reasoning_level"] = str(args["reasoning_level"])
            res = client._request("POST", f"/v3/workspaces/{ws}/peers/{pid}/chat", body=body, timeout=120.0)
            return _text_result(res)

        if name == "workspace_chat":
            body = {
                "query": str(args["query"]),
                "stream": False,
            }
            if args.get("reasoning_level"):
                body["reasoning_level"] = str(args["reasoning_level"])
            res = client._request("POST", f"/v3/workspaces/{ws}/chat", body=body, timeout=120.0)
            return _text_result(res)

        if name == "search":
            limit = max(1, min(50, int(args.get("limit") or 10)))
            body = {"query": str(args["query"]), "limit": limit}
            session_id = args.get("session_id")
            if session_id:
                sid = urllib.parse.quote(str(session_id), safe="")
                path = f"/v3/workspaces/{ws}/sessions/{sid}/search"
            else:
                path = f"/v3/workspaces/{ws}/search"
            res = client._request("POST", path, body=body, timeout=20.0)
            return _text_result(res)

        if name == "query_conclusions":
            top_k = max(1, min(50, int(args.get("top_k") or 10)))
            body = {
                "query": str(args["query"]),
                "top_k": top_k,
                "filters": {
                    "observer_id": cfg.user_peer,
                    "observed_id": cfg.user_peer,
                },
            }
            res = client._request("POST", f"/v3/workspaces/{ws}/conclusions/query", body=body, timeout=20.0)
            return _text_result(res)

        if name == "list_conclusions":
            size = max(1, min(100, int(args.get("size") or 20)))
            filters: dict[str, Any] = {
                "observer_id": cfg.user_peer,
                "observed_id": cfg.user_peer,
            }
            if args.get("session_id"):
                filters["session_id"] = str(args["session_id"])
            res = client._request(
                "POST",
                f"/v3/workspaces/{ws}/conclusions/list",
                body={"filters": filters},
                query={"page": 1, "size": size},
                timeout=15.0,
            )
            return _text_result(res)

        if name == "create_conclusions":
            raw_items = args.get("conclusions") or []
            if not isinstance(raw_items, list) or not raw_items:
                return _text_result("A lista 'conclusions' não pode ser vazia.", is_error=True)

            # Garante que o peer do usuário existe antes de criar conclusões
            client._request("POST", f"/v3/workspaces/{ws}/peers", body={"id": cfg.user_peer}, timeout=10.0)

            session_id = str(args["session_id"]).strip() if args.get("session_id") else None
            items_payload: list[dict[str, Any]] = []
            for item in raw_items:
                text = redact_secrets(str(item).strip())
                if not text:
                    continue
                entry: dict[str, Any] = {
                    "observer_id": cfg.user_peer,
                    "observed_id": cfg.user_peer,
                    "content": text,
                }
                if session_id:
                    entry["session_id"] = session_id
                items_payload.append(entry)

            res = client._request(
                "POST",
                f"/v3/workspaces/{ws}/conclusions",
                body={"conclusions": items_payload},
                timeout=20.0,
            )
            return _text_result(res)

        return _text_result(f"Ferramenta desconhecida: {name}", is_error=True)

    except urllib.error.HTTPError as http_err:
        detail = ""
        try:
            detail = http_err.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return _text_result(
            f"Erro HTTP {http_err.code} do Honcho ({cfg.base_url}): {detail or http_err.reason}",
            is_error=True,
        )
    except Exception as exc:
        return _text_result(
            f"Não foi possível conectar ao Honcho em {cfg.base_url}. "
            f"Verifique se o servidor está rodando. Detalhe: {exc}",
            is_error=True,
        )


def handle_rpc(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

    # Notificações JSON-RPC não possuem "id" e não devem gerar resposta
    if req_id is None:
        return None

    if method == "initialize":
        client_proto = str(params.get("protocolVersion") or "")
        proto = client_proto if client_proto in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": proto,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "honcho", "version": PLUGIN_VERSION},
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = str(params.get("name") or "")
        tool_args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": dispatch_tool(tool_name, tool_args),
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    in_buf = sys.stdin.buffer
    out_buf = sys.stdout.buffer

    while True:
        line = in_buf.readline()
        if not line:
            break

        stripped = line.strip()
        if not stripped:
            continue

        # Suporta tanto JSON-lines (padrão MCP Stdio) quanto framing Content-Length
        use_content_length = False
        if stripped.lower().startswith(b"content-length:"):
            use_content_length = True
            length = int(stripped.split(b":", 1)[1].strip())
            while True:
                hdr = in_buf.readline()
                if not hdr or hdr in (b"\r\n", b"\n"):
                    break
            raw_body = in_buf.read(length)
        else:
            raw_body = stripped

        try:
            msg = json.loads(raw_body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue

        if not isinstance(msg, dict):
            continue

        resp = handle_rpc(msg)
        if resp is not None:
            encoded = json.dumps(resp, ensure_ascii=False).encode("utf-8")
            if use_content_length:
                out_buf.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii") + encoded)
            else:
                out_buf.write(encoded + b"\n")
            out_buf.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
