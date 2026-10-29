#!/usr/bin/env python3
"""
Antigravity Lifecycle Hook para o Honcho (v3 API).

Captura automaticamente as mensagens trocadas no Antigravity (usuário e agente)
ao final de cada turno (`Stop`) e injeta a memória acumulada no início de novas
conversas (`SessionStart`).

Características:
- Zero dependências externas (usa apenas biblioteca padrão do Python 3.10+).
- Fail-open: se o Honcho estiver offline, encerra rapidamente sem travar o Antigravity.
- Cursor incremental por conversa (`~/.honcho/antigravity_state.json`) para não duplicar mensagens.
- Redação básica de segredos/tokens e colapso de blocos longos de código.
- Compatível com variáveis de ambiente (`HONCHO_*`) e `~/.honcho/config.json`.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HOST = "antigravity"
PLUGIN_NAME = "antigravity-honcho"
PLUGIN_VERSION = "0.1.0"

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_WORKSPACE = "antigravity"
DEFAULT_AI_PEER = "antigravity"

MAX_MESSAGE_CHARS = 6_000
MAX_CODE_BLOCK_LINES = 20
MAX_REPRESENTATION_CHARS = 3_000
MAX_SUMMARY_CHARS = 1_500
BATCH_SIZE = 100

USER_REQUEST_RE = re.compile(
    r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>",
    re.DOTALL,
)

SECRET_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(\w*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|API_?KEY|ACCESS_KEY|CREDENTIALS?)\w*)"
            r"\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s;|&\"']+)",
            re.IGNORECASE,
        ),
        r"\1=[redacted]",
    ),
    (
        re.compile(
            r"(--(?:password|passwd|pwd|token|api-?key|secret|auth)[= ])"
            r"(?:\"[^\"]*\"|'[^']*'|[^\s;|&\"']+)",
            re.IGNORECASE,
        ),
        r"\1[redacted]",
    ),
    (
        re.compile(
            r"(authorization:\s*(?:bearer|basic|token)\s+)[^\s\"']+",
            re.IGNORECASE,
        ),
        r"\1[redacted]",
    ),
    (
        re.compile(r"([a-z][a-z0-9+.-]*://[^/\s:@]+:)[^@\s]+@", re.IGNORECASE),
        r"\1[redacted]@",
    ),
    (
        re.compile(
            r"\b(?:hch[_-]?[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{16,}"
            r"|(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
            r"|xox[baprs]-[A-Za-z0-9-]{10,}|glpat-[A-Za-z0-9_-]{20,}|npm_[A-Za-z0-9]{36})\b"
        ),
        "[redacted]",
    ),
]

FENCED_CODE_RE = re.compile(r"```[^\n]*\n([\s\S]*?)```")


def log_debug(message: str) -> None:
    if os.environ.get("HONCHO_HOOK_DEBUG"):
        sys.stderr.write(f"[{PLUGIN_NAME}] {message}\n")


def sanitize_id(value: str, fallback: str = "default") -> str:
    cleaned = re.sub(r"[^a-z0-9_-]+", "-", value.lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")[:100]
    return cleaned or fallback


def redact_secrets(text: str) -> str:
    out = text
    for pattern, replacement in SECRET_RULES:
        out = pattern.sub(replacement, out)
    return out


def collapse_code_blocks(text: str, max_lines: int = MAX_CODE_BLOCK_LINES) -> str:
    def _replace(match: re.Match[str]) -> str:
        body = match.group(1)
        line_count = body.count("\n") + 1
        if line_count > max_lines:
            return f"[bloco de código omitido, {line_count} linhas]"
        return match.group(0)

    return FENCED_CODE_RE.sub(_replace, text)


def clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


class ResolvedConfig:
    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str,
        api_key: str | None,
        workspace: str,
        user_peer: str,
        ai_peer: str,
        session_strategy: str,
        timeout_sec: float,
    ) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.workspace = sanitize_id(workspace, DEFAULT_WORKSPACE)
        self.user_peer = sanitize_id(user_peer, "user")
        self.ai_peer = sanitize_id(ai_peer, DEFAULT_AI_PEER)
        self.session_strategy = session_strategy
        self.timeout_sec = timeout_sec


def load_config() -> ResolvedConfig:
    file_cfg: dict[str, Any] = {}
    cfg_path = Path.home() / ".honcho" / "config.json"
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                file_cfg = raw
        except Exception as exc:
            log_debug(f"Falha ao ler {cfg_path}: {exc}")

    hosts = file_cfg.get("hosts") if isinstance(file_cfg.get("hosts"), dict) else {}
    host_cfg = hosts.get(HOST) if isinstance(hosts.get(HOST), dict) else {}

    def pick_str(env_keys: list[str], key: str, default: str) -> str:
        for env_key in env_keys:
            val = os.environ.get(env_key)
            if val and val.strip():
                return val.strip()
        for block in (host_cfg, file_cfg):
            val = block.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return default

    enabled = True
    env_enabled = os.environ.get("HONCHO_ENABLED")
    if env_enabled is not None:
        enabled = env_enabled.strip().lower() not in ("0", "false", "no", "off")
    else:
        for block in (host_cfg, file_cfg):
            if isinstance(block.get("enabled"), bool):
                enabled = block["enabled"]
                break

    base_url = pick_str(["HONCHO_URL", "HONCHO_BASE_URL", "HONCHO_API_URL"], "baseUrl", DEFAULT_BASE_URL)
    if not base_url.startswith(("http://", "https://")):
        is_local = base_url.split("/")[0].split(":")[0].lower() in ("localhost", "127.0.0.1", "::1")
        base_url = f"{'http' if is_local else 'https'}://{base_url}"

    api_key = os.environ.get("HONCHO_API_KEY")
    if not api_key:
        for block in (host_cfg, file_cfg):
            auth = block.get("auth")
            if isinstance(auth, dict):
                if isinstance(auth.get("apiKey"), str) and auth["apiKey"].strip():
                    api_key = auth["apiKey"].strip()
                    break
                oauth = auth.get("oauth")
                if isinstance(oauth, dict) and isinstance(oauth.get("accessToken"), str):
                    api_key = oauth["accessToken"].strip()
                    break
            if isinstance(block.get("apiKey"), str) and block["apiKey"].strip():
                api_key = block["apiKey"].strip()
                break

    try:
        default_user = getpass.getuser()
    except Exception:
        default_user = "user"

    workspace = pick_str(["HONCHO_WORKSPACE_ID", "HONCHO_WORKSPACE"], "workspace", DEFAULT_WORKSPACE)
    user_peer = pick_str(["HONCHO_PEER_NAME", "HONCHO_USER_PEER"], "peerName", default_user)
    ai_peer = os.environ.get("HONCHO_AI_PEER", DEFAULT_AI_PEER).strip() or DEFAULT_AI_PEER
    session_strategy = os.environ.get("HONCHO_SESSION_STRATEGY", "project").strip().lower()

    timeout_sec = 4.0
    env_timeout = os.environ.get("HONCHO_TIMEOUT_SEC")
    if env_timeout:
        try:
            timeout_sec = max(0.5, float(env_timeout))
        except ValueError:
            pass

    return ResolvedConfig(
        enabled=enabled,
        base_url=base_url,
        api_key=api_key,
        workspace=workspace,
        user_peer=user_peer,
        ai_peer=ai_peer,
        session_strategy=session_strategy,
        timeout_sec=timeout_sec,
    )


def git_origin_slug(root: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", root, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        if proc.returncode != 0:
            return None
        url = proc.stdout.strip()
        match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url)
        if match:
            return f"{sanitize_id(match.group(1))}-{sanitize_id(match.group(2))}"
    except Exception:
        pass
    return None


def resolve_session_id(payload: dict[str, Any], cfg: ResolvedConfig) -> str:
    conv_id = str(payload.get("conversationId") or "").strip()
    if cfg.session_strategy == "conversation" and conv_id:
        return f"{HOST}-{sanitize_id(conv_id, 'session')}"

    workspaces = payload.get("workspacePaths")
    root = ""
    if isinstance(workspaces, list) and workspaces:
        root = str(workspaces[0] or "").strip()

    if root:
        slug = git_origin_slug(root) or sanitize_id(Path(root).name, "project")
        return f"{HOST}-{slug}"

    if conv_id:
        return f"{HOST}-{sanitize_id(conv_id[:16], 'session')}"
    return f"{HOST}-default"


class HonchoRestClient:
    def __init__(self, cfg: ResolvedConfig, model_name: str | None = None) -> None:
        self.cfg = cfg
        self.model_name = model_name

    def _request(
        self,
        method: str,
        path: str,
        body: Any | None = None,
        query: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        url = f"{self.cfg.base_url}{path}"
        if query:
            clean_q = {k: str(v) for k, v in query.items() if v is not None}
            if clean_q:
                url = f"{url}?{urllib.parse.urlencode(clean_q)}"

        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": f"{PLUGIN_NAME}/{PLUGIN_VERSION}",
            "X-Honcho-Host": HOST,
            "X-Honcho-Plugin": f"{PLUGIN_NAME}/{PLUGIN_VERSION}",
        }
        if self.model_name:
            headers["X-Honcho-Agent-Model"] = self.model_name
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"

        data: bytes | None = None
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout or self.cfg.timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else None

    def health(self) -> bool:
        try:
            self._request("GET", "/health", timeout=2.0)
            return True
        except Exception as exc:
            log_debug(f"Healthcheck falhou: {exc}")
            return False

    def ensure_session_and_peers(self, session_id: str) -> None:
        ws = urllib.parse.quote(self.cfg.workspace, safe="")
        sid = urllib.parse.quote(session_id, safe="")

        # 1. Garante que o workspace existe
        self._request("POST", "/v3/workspaces", body={"id": self.cfg.workspace})

        # 2. Garante a sessão com configuração de observação:
        #    observe_me=True apenas para o usuário humano, focando a memória nele.
        peers_cfg = {
            self.cfg.user_peer: {"observe_me": True, "observe_others": False},
            self.cfg.ai_peer: {"observe_me": False, "observe_others": False},
        }
        self._request(
            "POST",
            f"/v3/workspaces/{ws}/sessions",
            body={"id": session_id, "peers": peers_cfg},
        )
        # Garante vínculo mesmo se a sessão já existia antes sem os peers
        self._request(
            "POST",
            f"/v3/workspaces/{ws}/sessions/{sid}/peers",
            body=peers_cfg,
        )

    def add_messages(self, session_id: str, messages: list[dict[str, Any]]) -> int:
        if not messages:
            return 0
        ws = urllib.parse.quote(self.cfg.workspace, safe="")
        sid = urllib.parse.quote(session_id, safe="")
        total = 0
        for idx in range(0, len(messages), BATCH_SIZE):
            chunk = messages[idx : idx + BATCH_SIZE]
            self._request(
                "POST",
                f"/v3/workspaces/{ws}/sessions/{sid}/messages",
                body={"messages": chunk},
            )
            total += len(chunk)
        return total

    def get_peer_context(self, max_conclusions: int = 12) -> dict[str, Any] | None:
        ws = urllib.parse.quote(self.cfg.workspace, safe="")
        pid = urllib.parse.quote(self.cfg.user_peer, safe="")
        try:
            res = self._request(
                "GET",
                f"/v3/workspaces/{ws}/peers/{pid}/context",
                query={"max_conclusions": max_conclusions},
            )
            return res if isinstance(res, dict) else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def get_session_summaries(self, session_id: str) -> dict[str, Any] | None:
        ws = urllib.parse.quote(self.cfg.workspace, safe="")
        sid = urllib.parse.quote(session_id, safe="")
        try:
            res = self._request("GET", f"/v3/workspaces/{ws}/sessions/{sid}/summaries")
            return res if isinstance(res, dict) else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise


def state_file_path() -> Path:
    return Path.home() / ".honcho" / "antigravity_state.json"


def load_state() -> dict[str, Any]:
    path = state_file_path()
    if not path.is_file():
        return {"cursors": {}, "initialized_sessions": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("cursors", {})
            data.setdefault("initialized_sessions", [])
            return data
    except Exception as exc:
        log_debug(f"Erro ao carregar estado: {exc}")
    return {"cursors": {}, "initialized_sessions": []}


def save_state(state: dict[str, Any]) -> None:
    path = state_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Mantém o arquivo enxuto (últimas 500 conversas)
        cursors = state.get("cursors", {})
        if isinstance(cursors, dict) and len(cursors) > 500:
            keys = list(cursors.keys())[-500:]
            state["cursors"] = {k: cursors[k] for k in keys}
        init_sessions = state.get("initialized_sessions", [])
        if isinstance(init_sessions, list) and len(init_sessions) > 200:
            state["initialized_sessions"] = init_sessions[-200:]

        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)
    except Exception as exc:
        log_debug(f"Erro ao salvar estado: {exc}")


def extract_user_prompt(raw_content: str) -> str:
    match = USER_REQUEST_RE.search(raw_content)
    if match:
        return match.group(1).strip()
    return raw_content.strip()


def resolve_transcript_file(transcript_path_str: str) -> Path | None:
    if not transcript_path_str:
        return None
    p = Path(transcript_path_str)
    # Prefere transcript_full.jsonl quando disponível para evitar campos truncados
    full_candidate = p.with_name("transcript_full.jsonl")
    if full_candidate.is_file():
        return full_candidate
    if p.is_file():
        return p
    return None


def extract_new_messages(
    transcript_file: Path,
    last_step_index: int,
    cfg: ResolvedConfig,
    conversation_id: str,
    model_name: str | None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Lê o JSONL do Antigravity e extrai apenas mensagens novas (step_index > last_step_index)
    de entrada explícita do usuário e respostas finais do modelo ao usuário.
    """
    messages: list[dict[str, Any]] = []
    max_step = last_step_index

    with transcript_file.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(step, dict):
                continue
            if step.get("status") != "DONE":
                continue

            step_idx = step.get("step_index")
            if not isinstance(step_idx, int) or step_idx <= last_step_index:
                continue

            source = step.get("source")
            step_type = step.get("type")
            raw_content = step.get("content")
            created_at = step.get("created_at")

            if not isinstance(raw_content, str) or not raw_content.strip():
                max_step = max(max_step, step_idx)
                continue

            peer_id: str | None = None
            cleaned_text = ""

            if source == "USER_EXPLICIT" and step_type == "USER_INPUT":
                peer_id = cfg.user_peer
                cleaned_text = redact_secrets(extract_user_prompt(raw_content))
            elif source == "MODEL" and step_type == "PLANNER_RESPONSE":
                peer_id = cfg.ai_peer
                cleaned_text = redact_secrets(collapse_code_blocks(raw_content.strip()))

            if peer_id and cleaned_text:
                meta: dict[str, Any] = {
                    "source": PLUGIN_NAME,
                    "host": HOST,
                    "step_index": step_idx,
                }
                if conversation_id:
                    meta["conversation_id"] = conversation_id
                if model_name and peer_id == cfg.ai_peer:
                    meta["model"] = model_name

                msg_payload: dict[str, Any] = {
                    "peer_id": peer_id,
                    "content": clip(cleaned_text, MAX_MESSAGE_CHARS),
                    "metadata": meta,
                }
                if isinstance(created_at, str) and created_at.strip():
                    msg_payload["created_at"] = created_at.strip()

                messages.append(msg_payload)

            max_step = max(max_step, step_idx)

    return messages, max_step


def handle_session_start(payload: dict[str, Any], cfg: ResolvedConfig) -> dict[str, Any]:
    if not cfg.enabled:
        return {}

    session_id = resolve_session_id(payload, cfg)
    model_name = payload.get("modelName") if isinstance(payload.get("modelName"), str) else None
    client = HonchoRestClient(cfg, model_name=model_name)

    try:
        client.ensure_session_and_peers(session_id)
        state = load_state()
        session_key = f"{cfg.workspace}:{session_id}"
        if session_key not in state["initialized_sessions"]:
            state["initialized_sessions"].append(session_key)
            save_state(state)

        peer_ctx = client.get_peer_context(max_conclusions=12) or {}
        summaries = client.get_session_summaries(session_id) or {}
    except Exception as exc:
        log_debug(f"SessionStart ignorado (Honcho indisponível): {exc}")
        return {}

    card_items = [
        line for line in (peer_ctx.get("peer_card") or []) if isinstance(line, str) and line.strip()
    ]
    representation = str(peer_ctx.get("representation") or "").strip()

    long_sum = summaries.get("long_summary") if isinstance(summaries.get("long_summary"), dict) else None
    short_sum = summaries.get("short_summary") if isinstance(summaries.get("short_summary"), dict) else None
    summary_text = ""
    if long_sum and isinstance(long_sum.get("content"), str):
        summary_text = long_sum["content"].strip()
    elif short_sum and isinstance(short_sum.get("content"), str):
        summary_text = short_sum["content"].strip()

    if not (card_items or representation or summary_text):
        log_debug(f"Sem memória prévia para {cfg.user_peer} na sessão {session_id}.")
        return {}

    parts = [
        f"[Memória Honcho — usuário: {cfg.user_peer} | workspace: {cfg.workspace} | sessão: {session_id}]",
        "Considere as notas abaixo como contexto acumulado de sessões anteriores (verifique no código atual caso haja conflito).",
        "A captura automática via hook está ativa para esta conversa.",
    ]
    if card_items:
        parts.append("Peer Card:\n" + "\n".join(f"- {item}" for item in card_items))
    if representation:
        parts.append("Representação do Usuário:\n" + clip(representation, MAX_REPRESENTATION_CHARS))
    if summary_text:
        parts.append("Resumo recente neste projeto:\n" + clip(summary_text, MAX_SUMMARY_CHARS))

    return {
        "injectSteps": [
            {
                "systemMessage": {
                    "systemMessage": "\n\n".join(parts),
                }
            }
        ]
    }


def handle_stop(payload: dict[str, Any], cfg: ResolvedConfig) -> dict[str, Any]:
    # Resposta padrão para permitir que o Antigravity finalize o turno normalmente
    allow_stop = {"decision": "stop"}

    if not cfg.enabled:
        return allow_stop

    transcript_file = resolve_transcript_file(str(payload.get("transcriptPath") or ""))
    conversation_id = str(payload.get("conversationId") or "").strip()
    if not transcript_file or not conversation_id:
        log_debug("transcriptPath ou conversationId ausente no payload.")
        return allow_stop

    state = load_state()
    cursors: dict[str, int] = state.setdefault("cursors", {})
    last_step = int(cursors.get(conversation_id, -1))

    model_name = payload.get("modelName") if isinstance(payload.get("modelName"), str) else None
    messages, new_max_step = extract_new_messages(
        transcript_file=transcript_file,
        last_step_index=last_step,
        cfg=cfg,
        conversation_id=conversation_id,
        model_name=model_name,
    )

    if not messages:
        if new_max_step > last_step:
            cursors[conversation_id] = new_max_step
            save_state(state)
        return allow_stop

    session_id = resolve_session_id(payload, cfg)
    client = HonchoRestClient(cfg, model_name=model_name)
    session_key = f"{cfg.workspace}:{session_id}"

    try:
        if session_key not in state.get("initialized_sessions", []):
            client.ensure_session_and_peers(session_id)
            state.setdefault("initialized_sessions", []).append(session_key)

        try:
            sent = client.add_messages(session_id, messages)
        except urllib.error.HTTPError as http_err:
            if http_err.code == 404:
                client.ensure_session_and_peers(session_id)
                sent = client.add_messages(session_id, messages)
            else:
                raise

        cursors[conversation_id] = new_max_step
        save_state(state)
        log_debug(f"Sincronizadas {sent} mensagens na sessão '{session_id}' (até step {new_max_step}).")
    except Exception as exc:
        # Não avança o cursor em caso de falha de rede: na próxima execução ele recupera!
        log_debug(f"Falha ao enviar mensagens ao Honcho (será tentado novamente no próximo turno): {exc}")

    return allow_stop


def detect_event(payload: dict[str, Any], explicit_event: str | None) -> str:
    if explicit_event and explicit_event != "auto":
        return explicit_event
    if "terminationReason" in payload or "executionNum" in payload:
        return "stop"
    return "session-start"


def run_self_test(cfg: ResolvedConfig, sample_transcript: str | None) -> int:
    print("=== Diagnóstico Antigravity <-> Honcho ===")
    print(f"Ativo (enabled)   : {cfg.enabled}")
    print(f"Honcho Base URL   : {cfg.base_url}")
    print(f"Workspace ID      : {cfg.workspace}")
    print(f"Peer do Usuário   : {cfg.user_peer}")
    print(f"Peer do Agente    : {cfg.ai_peer}")
    print(f"Estratégia Sessão : {cfg.session_strategy}")
    print(f"Arquivo de Estado : {state_file_path()}")

    client = HonchoRestClient(cfg)
    healthy = client.health()
    print(f"Servidor Online   : {'SIM' if healthy else 'NÃO (verifique se o container/API está rodando)'}")

    if sample_transcript:
        t_file = resolve_transcript_file(sample_transcript)
        if not t_file:
            print(f"\nArquivo de transcript não encontrado: {sample_transcript}")
            return 1
        msgs, max_step = extract_new_messages(
            transcript_file=t_file,
            last_step_index=-1,
            cfg=cfg,
            conversation_id="test-conv",
            model_name="test-model",
        )
        print(f"\nLeitura de teste ({t_file.name}): {len(msgs)} mensagens extraídas (até step {max_step}).")
        for idx, m in enumerate(msgs[:4], 1):
            preview = m["content"].replace("\n", " ")[:90]
            print(f"  {idx}. [{m['peer_id']}] {preview}...")

    return 0


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Hook de memória Honcho para Antigravity")
    parser.add_argument(
        "--event",
        choices=["auto", "session-start", "stop"],
        default="auto",
        help="Tipo de evento do ciclo de vida do Antigravity (padrão: auto)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Executa diagnóstico de configuração e conectividade com o Honcho",
    )
    parser.add_argument(
        "--transcript",
        help="Caminho opcional de um transcript.jsonl para testar extração com --test",
    )
    args = parser.parse_args()

    cfg = load_config()

    if args.test:
        return run_self_test(cfg, args.transcript)

    raw_stdin = ""
    if not sys.stdin.isatty():
        try:
            raw_stdin = sys.stdin.read()
        except Exception:
            raw_stdin = ""

    payload: dict[str, Any] = {}
    if raw_stdin.strip():
        try:
            parsed = json.loads(raw_stdin)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass

    event = detect_event(payload, args.event)
    if event == "stop":
        result = handle_stop(payload, cfg)
    else:
        result = handle_session_start(payload, cfg)

    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
