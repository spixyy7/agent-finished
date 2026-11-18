"""Connect finished to the AI agents on this computer, and the hooks they call.

register   adds three things to every agent found (each changed file is backed up first):
           - the MCP tool notify_finished
           - automatic notifications where the agent supports them
             (Claude Code: Stop hook, Codex: notify program)
           - one rule in the agent's global instructions, so it writes the summary itself
unregister removes all of it again.
hook       what the agents run when a turn ends; speaks the first sentence of the reply
           unless the agent already called notify_finished itself.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time

import finished as fin

HOME_DIR = os.path.expanduser("~")
SCRIPT = os.path.abspath(fin.__file__)
PY = fin.PY
PYW = fin.PYW if os.path.exists(fin.PYW) else fin.PY
LAST_MCP = os.path.join(fin.CACHE, "last_notify.json")

MARK_START = "<!-- finished:start -->"
MARK_END = "<!-- finished:end -->"
RULE = (
    f"{MARK_START}\n"
    "## Spoken notification (finished)\n"
    "When you finish a task the user gave you, or you are blocked and need the user, call the "
    "`notify_finished` tool once with a very short summary (max 12 words, plain words, no code or "
    "paths) and `language` set to the summary's ISO 639-1 code. If the tool is not available, run: "
    'finished -a <your name> -l <code> "<summary>"\n'
    f"{MARK_END}\n"
)


def fwd(path):
    return path.replace("\\", "/")


CLAUDE_HOOK = f'"{fwd(PYW)}" "{fwd(SCRIPT)}" hook claude'


# ---------------------------------------------------------------- file helpers

def read_text(path):
    """File text exactly as it is (line endings untouched) and the line ending to add with."""
    if not os.path.exists(path):
        return "", "\n"
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    return text, ("\r\n" if "\r\n" in text else "\n")


def write_text(path, text, stamp=None):
    """Write `text` exactly, after a backup copy of the old file."""
    if os.path.exists(path):
        shutil.copy2(path, path + (stamp or time.strftime(".bak-%Y%m%d%H%M%S")))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def append_block(text, block, nl):
    """`block` after `text`, separated by one blank line."""
    block = block.replace("\n", nl)
    if not text.strip():
        return block
    return text + ("" if text.endswith("\n") else nl) + nl + block


def load_json(path):
    text, nl = read_text(path)
    return (json.loads(text) if text.strip() else {}), nl


def dump_json(data, nl):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").replace("\n", nl)


def toml_array(items):
    return "[" + ", ".join(json.dumps(x) for x in items) + "]"


def toml_top_key(lines, key):
    """(start, end, value) of a top-level `key = ...` that sits before the first table."""
    import tomllib
    for i, line in enumerate(lines):
        if re.match(r"\s*\[", line):
            return None
        if re.match(rf"\s*{re.escape(key)}\s*=", line):
            for j in range(i, len(lines)):
                try:
                    return i, j + 1, tomllib.loads("\n".join(lines[i:j + 1]))[key]
                except tomllib.TOMLDecodeError:
                    continue
            return None
    return None


# ---------------------------------------------------------------- the three parts

def mcp_add_claude(remove=False):
    exe = shutil.which("claude")
    if not exe:
        return "claude command not found"
    has = subprocess.run([exe, "mcp", "get", "finished"], capture_output=True).returncode == 0
    if remove:
        if not has:
            return "not there"
        r = subprocess.run([exe, "mcp", "remove", "finished", "-s", "user"], capture_output=True, text=True)
        return "removed" if r.returncode == 0 else "failed: " + (r.stderr or r.stdout).strip()[:100]
    if has:
        return "already there"
    r = subprocess.run([exe, "mcp", "add", "-s", "user", "finished", "--", PY, SCRIPT, "mcp"],
                       capture_output=True, text=True)
    return "added" if r.returncode == 0 else "failed: " + (r.stderr or r.stdout).strip()[:100]


def mcp_toml(path, stamp, remove=False):
    text, nl = read_text(path)
    if remove:
        # the blank line before it, the header, and every line up to the next table header
        m = re.search(r"(?:\r?\n)?^\[mcp_servers\.finished\][^\r\n]*(?:\r?\n|$)(?:(?!\[)[^\r\n]*(?:\r?\n|$))*",
                      text, re.M)
        if not m:
            return "not there"
        rest = text[m.end():]
        text = text[:m.start()] + (nl if rest and not text[:m.start()].endswith("\n") else "") + rest
        write_text(path, text, stamp)
        return "removed"
    if re.search(r"^\[mcp_servers\.finished\]", text, re.M):
        return "already there"
    block = f"[mcp_servers.finished]\ncommand = '{PY}'\nargs = ['{SCRIPT}', \"mcp\"]\nstartup_timeout_sec = 15\n"
    write_text(path, append_block(text, block, nl), stamp)
    return "added"


def mcp_json(path, stamp, kind="mcpServers", remove=False):
    data, nl = load_json(path)
    if kind == "opencode":
        mcp_cfg = data.setdefault("mcp", {})
        servers = mcp_cfg["servers"] if isinstance(mcp_cfg.get("servers"), dict) else mcp_cfg
        item = {"type": "local", "command": [PY, SCRIPT, "mcp"], "enabled": True}
    else:
        servers = data.setdefault(kind, {})
        item = {"command": PY, "args": [SCRIPT, "mcp"]}
    if remove:
        if "finished" not in servers:
            return "not there"
        del servers["finished"]
        if kind != "opencode" and not servers:  # an empty list we made means nothing
            del data[kind]
        write_text(path, dump_json(data, nl), stamp)
        return "removed"
    if "finished" in servers:
        return "already there"
    servers["finished"] = item
    write_text(path, dump_json(data, nl), stamp)
    return "added"


def auto_claude(stamp, remove=False):
    path = os.path.join(HOME_DIR, ".claude", "settings.json")
    data, nl = load_json(path)
    stop = data.setdefault("hooks", {}).setdefault("Stop", [])

    def ours(entry):
        return any("finished.py" in h.get("command", "") and "hook claude" in h.get("command", "")
                   for h in entry.get("hooks", []))

    has = any(ours(e) for e in stop)
    if remove:
        if not has:
            return "not there"
        data["hooks"]["Stop"] = [e for e in stop if not ours(e)]
        if not data["hooks"]["Stop"]:
            del data["hooks"]["Stop"]
        if not data["hooks"]:
            del data["hooks"]
        write_text(path, dump_json(data, nl), stamp)
        return "removed"
    if has:
        return "already there"
    stop.append({"hooks": [{"type": "command", "command": CLAUDE_HOOK, "timeout": 10}]})
    write_text(path, dump_json(data, nl), stamp)
    return "added (Stop hook)"


def auto_codex(stamp, remove=False):
    """Codex runs one `notify` program when a turn ends. Keep any program already there by
    putting ours in front of it (it is run first, with the same payload)."""
    path = os.path.join(HOME_DIR, ".codex", "config.toml")
    text, nl = read_text(path)
    lines = text.splitlines(keepends=True)
    found = toml_top_key([line.rstrip("\r\n") for line in lines], "notify")
    ours = [PYW, SCRIPT, "hook", "codex"]
    is_ours = bool(found) and any("finished.py" in str(x) for x in found[2])
    if found:
        start, end, old = found
        ending = lines[end - 1][len(lines[end - 1].rstrip("\r\n")):] or nl
    if remove:
        if not is_ours:
            return "not there"
        prev = old[old.index("--previous-notify") + 1] if "--previous-notify" in old else None
        line = old[old.index("--previous-line") + 1] if "--previous-line" in old else None
        if line:  # the exact text that was there
            lines[start:end] = [base64.b64decode(line).decode("utf-8")]
        else:
            lines[start:end] = ["notify = " + toml_array(json.loads(prev)) + ending] if prev else []
        write_text(path, "".join(lines), stamp)
        return "removed" + (" (earlier notify restored)" if prev else "")
    if is_ours:
        return "already there"
    if found:
        exact = base64.b64encode("".join(lines[start:end]).encode("utf-8")).decode("ascii")
        new = ours + ["--previous-notify", json.dumps(old), "--previous-line", exact]
        lines[start:end] = ["notify = " + toml_array(new) + ending]
        how = "added (notify, before the one you had)"
    else:
        idx = next((i for i, line in enumerate(lines) if re.match(r"\s*\[", line)), len(lines))
        if idx == len(lines) and lines and not lines[-1].endswith("\n"):
            lines[-1] += nl
        lines.insert(idx, "notify = " + toml_array(ours) + nl)
        how = "added (notify)"
    write_text(path, "".join(lines), stamp)
    return how


def rules(path, stamp, remove=False):
    text, nl = read_text(path)
    if remove:
        m = re.search(rf"(?:\r?\n)?{re.escape(MARK_START)}.*?{re.escape(MARK_END)}(?:\r?\n)?", text, re.S)
        if not m:
            return "not there"
        text = text[:m.start()] + text[m.end():]
        if text.strip():
            write_text(path, text, stamp)
        else:  # the file only held our rule: it was ours
            shutil.copy2(path, path + stamp)
            os.remove(path)
        return "removed"
    if MARK_START in text:
        return "already there"
    write_text(path, append_block(text, RULE, nl), stamp)
    return "added"


def h(*parts):
    return os.path.join(HOME_DIR, *parts)


# name: (installed?, [(part, function)])
def agent_table():
    return {
        "claude": (bool(shutil.which("claude")) or os.path.isdir(h(".claude")), [
            ("tool", lambda s, r: mcp_add_claude(r)),
            ("auto", lambda s, r: auto_claude(s, r)),
            ("rule", lambda s, r: rules(h(".claude", "CLAUDE.md"), s, r)),
        ]),
        "codex": (os.path.isdir(h(".codex")), [
            ("tool", lambda s, r: mcp_toml(h(".codex", "config.toml"), s, r)),
            ("auto", lambda s, r: auto_codex(s, r)),
            ("rule", lambda s, r: rules(h(".codex", "AGENTS.md"), s, r)),
        ]),
        "grok": (os.path.isdir(h(".grok")), [
            ("tool", lambda s, r: mcp_toml(h(".grok", "config.toml"), s, r)),
        ]),
        "gemini": (os.path.isdir(h(".gemini")), [
            ("tool", lambda s, r: mcp_json(h(".gemini", "settings.json"), s, remove=r)),
            ("rule", lambda s, r: rules(h(".gemini", "GEMINI.md"), s, r)),
        ]),
        "qwen": (os.path.isdir(h(".qwen")), [
            ("tool", lambda s, r: mcp_json(h(".qwen", "settings.json"), s, remove=r)),
            ("rule", lambda s, r: rules(h(".qwen", "QWEN.md"), s, r)),
        ]),
        "cursor": (os.path.isdir(h(".cursor")), [
            ("tool", lambda s, r: mcp_json(h(".cursor", "mcp.json"), s, remove=r)),
        ]),
        "windsurf": (os.path.isdir(h(".codeium", "windsurf")), [
            ("tool", lambda s, r: mcp_json(h(".codeium", "windsurf", "mcp_config.json"), s, remove=r)),
            ("rule", lambda s, r: rules(h(".codeium", "windsurf", "memories", "global_rules.md"), s, r)),
        ]),
        "opencode": (os.path.isdir(h(".config", "opencode")), [
            ("tool", lambda s, r: mcp_json(h(".config", "opencode", "opencode.json"), s, "opencode", r)),
            ("rule", lambda s, r: rules(h(".config", "opencode", "AGENTS.md"), s, r)),
        ]),
    }


def connect(targets, remove=False):
    table = agent_table()
    want = [t for t in targets if t != "all"] or list(table)
    unknown = [t for t in want if t not in table]
    if unknown:
        print("Unknown agent: " + ", ".join(unknown) + ". Known: " + ", ".join(table))
        return 1
    stamp = time.strftime(".bak-%Y%m%d%H%M%S")
    for name in want:
        installed, parts = table[name]
        if not installed:
            print(f"  {name:<9} not installed")
            continue
        results = []
        for part, func in parts:
            try:
                results.append(f"{part}: {func(stamp, remove)}")
            except Exception as e:
                results.append(f"{part}: failed ({e})")
        print(f"  {name:<9} " + " | ".join(results))
    if remove:
        print("Removed. Backups of every changed file are next to it (*.bak-<time>).")
    else:
        print("Backups of every changed file are next to it (*.bak-<time>). Undo: finished unregister"
              "\nRestart the agents to load the tool. Any agent with a shell can also run: finished \"message\"")
    return 0


# ---------------------------------------------------------------- hooks the agents run

def mark_mcp_call(agent):
    try:
        os.makedirs(fin.CACHE, exist_ok=True)
        data = {}
        if os.path.exists(LAST_MCP):
            with open(LAST_MCP, encoding="utf-8") as f:
                data = json.load(f)
        data[(agent or "").lower()] = time.time()
        with open(LAST_MCP, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except (OSError, ValueError):
        pass


def called_mcp_recently(agent, seconds=90):
    try:
        with open(LAST_MCP, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    now = time.time()
    return any(now - data.get(k, 0) < seconds for k in (agent.lower(), ""))


def first_sentence(text):
    """Opening sentence of the agent's last reply - usually what it did."""
    in_code = False
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line or line.startswith(("|", "#", ">", "<", "---")):
            continue
        line = re.sub(r"^([-*•]|\d+[.)])\s+", "", line)
        return re.split(r"(?<=[.!?])\s+", line)[0]
    return ""


def claude_turn(path, tail=4_000_000):
    """(last assistant text, whether notify_finished was called) for the turn that just ended."""
    if not path or not os.path.exists(path):
        return "", False
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - tail))
        lines = f.read().decode("utf-8", "replace").splitlines()
    text, notified = "", False
    for line in reversed(lines):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("isSidechain") or obj.get("isMeta"):
            continue
        content = (obj.get("message") or {}).get("content")
        if obj.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_use" and "notify_finished" in block.get("name", ""):
                    notified = True
            if not text:
                texts = [b.get("text", "") for b in content if b.get("type") == "text" and b.get("text", "").strip()]
                if texts:
                    text = texts[-1]
        elif obj.get("type") == "user":
            if isinstance(content, str) or (isinstance(content, list)
                                            and any(b.get("type") == "text" for b in content)):
                break  # the prompt that started this turn
    return text, notified


def hook(args):
    kind = (args[0] if args else "").lower()
    rest = args[1:]
    dry = "--dry" in rest
    job = None
    try:
        if kind == "claude":
            data = json.loads(sys.stdin.read() or "{}")
            text, notified = claude_turn(data.get("transcript_path", ""))
            text = data.get("last_assistant_message") or text
            if not notified:
                job = {"message": first_sentence(text), "agent": "Claude"}
        elif kind == "codex":
            payload = next((a for a in reversed(rest) if a.lstrip().startswith("{")), "{}")
            if "--previous-notify" in rest and not dry:
                prev = json.loads(rest[rest.index("--previous-notify") + 1])
                subprocess.Popen(prev + [payload], creationflags=0x00000008 | 0x00000200,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            data = json.loads(payload)
            if data.get("type") == "agent-turn-complete" and not called_mcp_recently("codex"):
                job = {"message": first_sentence(data.get("last-assistant-message") or ""), "agent": "Codex"}
        else:  # any other agent: optional JSON on stdin with the reply text
            data = {}
            if not sys.stdin.isatty():
                raw = sys.stdin.read()
                data = json.loads(raw) if raw.strip().startswith("{") else {"message": raw}
            text = next((data.get(k) for k in ("message", "last_assistant_message", "prompt_response",
                                                "last-assistant-message") if data.get(k)), "")
            if not called_mcp_recently(kind):
                job = {"message": first_sentence(text), "agent": kind.title() if kind else ""}
    except Exception as e:
        fin.log(f"hook {kind} failed: {e!r}")
    if job:
        if dry:
            print(json.dumps(job, ensure_ascii=False))
        else:
            fin.spawn(job)
    return 0
