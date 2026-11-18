<p align="center"><img src="icon.png" width="96" alt="finished"></p>

<h1 align="center">finished</h1>

<p align="center"><b>Your AI agents tell you when they're done, out loud.</b><br>
A Windows notification and a short spoken message, in the voice you pick.<br>
One command and one MCP tool, so any agent can call it: Claude Code, Codex, Gemini CLI, Cursor, OpenCode, Grok, Qwen, Windsurf, or anything that can run a shell command.</p>

```powershell
finished -a Claude "Login page fixed and tests pass"
```

> 🔔 **Claude: Finished** — *Login page fixed and tests pass* &nbsp;·&nbsp; 🔊 a soft anime voice reads it to you

---

## Why

You start an agent, switch to something else, and keep checking whether it is done. With `finished`, the agent tells you as soon as it stops. You see what it finished in the notification and hear it in one sentence, so you can stay away from the screen.

## Features

- **One call does both.** It shows a Windows notification and speaks the message. The call returns in about 0.15 s and the speech plays in the background, so the agent is never held up.
- **223 voices.** 49 local Kokoro voices: anime girls, whisper, sultry, deep male, British. Plus 172 online neural voices in 75 languages, and Windows' built-in voices as a last resort.
- **Local first.** The default voices run offline on your CPU with [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), and nothing leaves your computer.
- **Language detection.** The language is detected offline with [Lingua](https://github.com/pemistahl/lingua-py). A Serbian message is read by a Serbian voice, a German one by a German voice. Agents can also name the language themselves, which is exact.
- **Ready phrase, the agent's own words, or both.** `"Finished, senpai!"`, `"Login page fixed"`, or `"Finished. Login page fixed."`.
- **No talking over each other.** When several agents finish at the same time, they speak one after another.
- **Fast repeats.** Everything spoken is cached, so a phrase you hear often plays at once.
- **Fallbacks.** If the internet is down, a local voice speaks. If that fails, the Windows voice speaks.
- **Simple to wire up.** The MCP server is built in with no extra dependencies, and `finished register` adds it to every agent installed on your computer.

## Install

You need Windows 10 or 11, [Python](https://www.python.org/) 3.10–3.13 or [uv](https://docs.astral.sh/uv/), and about 400 MB of disk space.

```powershell
git clone https://github.com/spixyy7/agent-finished
cd agent-finished
powershell -ExecutionPolicy Bypass -File install.ps1 -Register
```

The installer:

1. creates `.venv` and installs the Python packages
2. downloads the Kokoro model (about 350 MB, once) into `models/`
3. puts a `finished` command in `%USERPROFILE%\.local\bin` for PowerShell, cmd and Git Bash, and adds that folder to your PATH
4. with `-Register`, adds the MCP tool to the agents it finds (see below)

When it is done, you hear *"finished is installed"*. Then run `finished setup` to choose your voice.

## Quick start

```powershell
finished setup                       # listen to voices, pick one, pick languages, phrase and mode
finished "Database migration done"   # what an agent runs
finished preview anime               # hear all anime voices
finished voices                      # list voices
```

## Connect your agents

### Automatic

```powershell
finished register            # every agent found on this computer
finished register codex      # just one
```

| Agent | Where it is added |
|---|---|
| Claude Code | `claude mcp add -s user finished ...` |
| Codex CLI | `~/.codex/config.toml` |
| Grok CLI | `~/.grok/config.toml` |
| Gemini CLI / Antigravity | `~/.gemini/settings.json` |
| Qwen Code | `~/.qwen/settings.json` |
| Cursor | `~/.cursor/mcp.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| OpenCode | `~/.config/opencode/opencode.json` |

Each config file is backed up next to itself (`*.bak-<time>`) before it is changed. Restart the agents afterwards so they load the tool.

### By hand

The server is `<folder>\.venv\Scripts\python.exe <folder>\finished.py mcp`, using stdio.

<details><summary>JSON config (Claude Desktop, Gemini, Cursor, Qwen, Windsurf)</summary>

```json
{
  "mcpServers": {
    "finished": {
      "command": "C:\\path\\to\\agent-finished\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\agent-finished\\finished.py", "mcp"]
    }
  }
}
```
</details>

<details><summary>TOML config (Codex, Grok)</summary>

```toml
[mcp_servers.finished]
command = 'C:\path\to\agent-finished\.venv\Scripts\python.exe'
args = ['C:\path\to\agent-finished\finished.py', "mcp"]
```
</details>

<details><summary>Agents without MCP</summary>

Any agent that can run a shell command can use the CLI:

```
finished -a Aider -l en "Refactor done, 42 tests green"
```
</details>

### The tool

`notify_finished(message, language?, agent?)`

| Field | Meaning |
|---|---|
| `message` | What the agent finished, at most 12 words, no code or paths. Example: `"Login page fixed and tests pass"` |
| `language` | ISO 639-1 code of the message, such as `en`, `sr` or `de`. Optional, but it makes the voice choice exact. |
| `agent` | Shown in the notification title, such as `Claude: Finished`. |

The tool description already tells agents to call it once, when the whole task is finished or when they need you. If you want every task to end with it, add this line to your `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`:

```
When you finish a task, call notify_finished with a very short summary (or run: finished "<summary>").
```

## Voices

```powershell
finished voices             # English voices, grouped
finished voices sr          # voices of one language
finished voices all         # all 223
finished preview sexy       # hear a group: anime | sexy | female | male | local | online | <code> | <name>
finished set voice anime-whisper
```

**Local voices** (offline, Kokoro):

| Group | Voices |
|---|---|
| Anime girls | `anime-sexy` (default: soft, slow), `anime-whisper`, `anime`, `anime-cute`, `anime-fox`, `anime-soft`, `anime-bella`, `anime-heart` |
| Sultry, whisper | `whisper`, `sultry`, `bella`, `heart` |
| Other women | `sky`, `nova`, `sarah`, `jessica`, `aoede`, `kore`, `river`, `emma-uk`, `isabella-uk`, `lily-uk`, `alice-uk` |
| Men | `deep`, `anime-boy`, `adam`, `michael`, `fenrir`, `puck`, `onyx`, `echo`, `eric`, `liam`, `santa`, `george-uk`, `fable-uk`, `lewis-uk`, `daniel-uk` |
| Other languages | `es-dora-local`, `es-alex-local`, `fr-siwis-local`, `it-sara-local`, `it-nicola-local`, `pt-dora-local`, `pt-alex-local`, `hi-alpha-local`, `hi-beta-local`, `hi-omega-local`, `hi-psi-local` |

The anime voices are Kokoro's Japanese voices speaking English. Some are blended with the whispering `af_nicole` voice (for example `jf_alpha*0.6+af_nicole*0.4`).

**Online voices** need internet and come from Microsoft Edge's neural voices: `ava`, `ava-sexy`, `emma`, `jenny`, `aria`, `sonia-uk`, `andrew`, `brian`, `christopher`, `guy`, `ryan-uk`, plus 2–6 native voices for each of 75 languages (`sr-sophie`, `de-tanja`, `ja-nanami`, ...).

**Windows voices** are `zira` and `david`. They are robotic but always there.

## Languages and auto-detect

```powershell
finished languages              # all 75 languages, which ones auto-detect covers, which voice speaks each
finished set detect en,sr       # auto-detect chooses only between these (most precise)
finished set detect all         # or among all 60 detectable languages
finished set language de        # or always one language
finished set voice-for sr sr-nicholas   # which voice reads Serbian
finished detect "Sredio sam bug u checkoutu"   # see what a text is detected as
```

The language is chosen in this order:

1. **The agent names it** (`language` in MCP, `-l` in the CLI). This is used as is and is always right.
2. **A fixed language** set with `finished set language <code>`.
3. **Offline detection** with Lingua, among the languages you allowed with `set detect`:
   - Fewer allowed languages means higher accuracy. Choosing between English and Serbian is much easier than choosing among 60.
   - Languages that short texts cannot tell apart count as one group: Serbian / Croatian / Bosnian, and Norwegian Bokmål / Nynorsk. So Latin-script Serbian is not read as Croatian.
   - A single word keeps your main voice's language unless the detector is sure. Two- or three-letter words like `OK` or `API` need 95% certainty.
   - In `both` mode, the phrase and the message are detected separately, so `"Finished"` + `"Završio sam login"` uses two voices.

Then the voice is chosen in this order: your main voice if it speaks that language, then your pick for that language (`voice-for`), then a native online voice of the same gender as your main voice, then a local Kokoro voice of that language, then your main voice.

The included tests check 23 short English and Serbian messages (including single words) and 21 sentences in 21 languages with all languages enabled. All pass.

## Settings

| Command | What it does |
|---|---|
| `finished set voice NAME` | Main voice. It reads every message in its own language. |
| `finished set voice-for CODE NAME` | Voice for another language (`default` resets it). |
| `finished set language auto\|CODE` | Detect each message, or always use one language. |
| `finished set detect all\|en,sr,...` | Languages auto-detect chooses from. |
| `finished set mode preset\|agent\|both` | Say the ready phrase, the agent's message, or both. |
| `finished set phrase N\|"text"` | Pick a ready phrase (`finished phrases`) or write your own. |
| `finished set volume 0-200` | Volume in percent. |
| `finished set toast on\|off` | Turn the notification on or off. |
| `finished set sound on\|off` | Turn the voice on or off. |
| `finished set words 3-40` | Most words spoken from a message (default 14). |
| `finished config` | Show the settings (stored in `config.json`). |

CLI options for a single call: `-a AGENT`, `-l CODE`, `-v VOICE`, `-p N|"phrase"`, `-w` (wait until spoken), `--no-voice`, `--no-toast`.

## How it works

```
agent ──► finished "msg"  ─┐
agent ──► notify_finished ─┴─► background worker ─┬─► notification (WinRT toast via Windows PowerShell)
                                                  └─► language → voice → speech ─► cache ─► speaker (one at a time)
                                                              Kokoro (local) · Edge neural (online) · SAPI (Windows)
```

- `finished.py` contains everything: the CLI, voices, language detection, speech and the MCP server.
- `toast.ps1` shows the notification. It registers its own app name, **Agents**, so you can mute it in Windows settings.
- `languages.json` lists the languages and online voices. Rebuild it with `python tools/build_languages.py`.
- `cache/` holds the spoken WAV files (the newest 500) and `finished.log`.

## Privacy

- With local voices (Kokoro, Windows), nothing leaves your computer.
- With **online voices**, the message text is sent to Microsoft's Edge read-aloud service through [edge-tts](https://github.com/rany2/edge-tts). Messages in languages without a local voice use an online voice. To stay fully offline, run `finished set language en` (or keep `detect` to languages that have local voices) and pick a local main voice.
- There is no telemetry and no account.

## Troubleshooting

| Problem | Try |
|---|---|
| No sound | Run `finished -w "test"` and read `cache/finished.log`. |
| No notification | Turn off Focus / Do Not Disturb, and check Settings → System → Notifications → **Agents**. |
| The first message takes about 3 s | That is the model loading. Phrases are cached, and later messages are faster. |
| A message is read in the wrong language | Narrow it down with `finished set detect en,xx`, or have the agent pass `language`. |
| The agent does not see the tool | Run `finished register` again and restart the agent. |
| Start over | Delete `config.json` and `cache/`. |

## Development

```powershell
.venv\Scripts\python.exe -m unittest discover tests     # detection, voices, text, MCP
.venv\Scripts\python.exe tools\build_languages.py        # refresh the language and voice list
```

## Credits

- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad (Apache-2.0), the local voices
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) by thewh1teagle (MIT), which runs Kokoro with ONNX Runtime
- [edge-tts](https://github.com/rany2/edge-tts) by rany2 (LGPL-3.0), the online voices
- [Lingua](https://github.com/pemistahl/lingua-py) by Peter M. Stahl (Apache-2.0), language detection
- [python-soundfile](https://github.com/bastibe/python-soundfile) (BSD-3-Clause)

This project is not affiliated with Microsoft, Anthropic, OpenAI, Google or any agent vendor.

## License

[MIT](LICENSE)
