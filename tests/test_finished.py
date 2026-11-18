"""Checks for language detection, voice choice, text cleaning and the MCP server.

    .venv\\Scripts\\python.exe -m unittest discover tests
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import finished as f  # noqa: E402


def cfg(**kw):
    c = dict(f.DEFAULTS)
    c.update(kw)
    return c


class DetectTwoLanguages(unittest.TestCase):
    """The usual setup: an English main voice, agents writing English or Serbian."""
    CASES = {
        "Login page fixed and tests pass": "en",
        "Done": "en",
        "OK": "en",
        "Build ok": "en",
        "Fixed the API": "en",
        "Deployed to production": "en",
        "Database migration finished": "en",
        "Gotovo": "sr",
        "Gotovo!": "sr",
        "Završio sam login stranicu": "sr",
        "Zavrsio sam login stranicu": "sr",
        "Napravio sam novu bazu": "sr",
        "Sredio sam bug u checkoutu": "sr",
        "Popravio API": "sr",
        "Deploy urađen": "sr",
        "Testovi prolaze": "sr",
        "Radi": "sr",
        "Spremno": "sr",
        "Urađeno": "sr",
        "Ready": "en",
        "Tested": "en",
        "API": "en",
        "Завршио сам страницу": "sr",
    }

    def test_cases(self):
        c = cfg(detect=["en", "sr"])
        wrong = {t: f.detect(t, c) for t, want in self.CASES.items() if f.detect(t, c) != want}
        self.assertEqual(wrong, {})


class DetectAllLanguages(unittest.TestCase):
    CASES = {
        "The login page is fixed and all tests pass": "en",
        "Die Datenbank-Migration ist fertig": "de",
        "La tarea está terminada y probada": "es",
        "La tâche est terminée et testée": "fr",
        "Il compito è finito e testato": "it",
        "A tarefa está pronta e testada": "pt",
        "De taak is klaar en getest": "nl",
        "Uppgiften är klar och testad": "sv",
        "Zadanie zostało zakończone": "pl",
        "Görev tamamlandı ve test edildi": "tr",
        "Tehtävä on valmis": "fi",
        "Задача выполнена, тесты проходят": "ru",
        "Завдання виконано, тести проходять": "uk",
        "Задачата е изпълнена": "bg",
        "Η εργασία ολοκληρώθηκε": "el",
        "タスクが完了しました": "ja",
        "任务已完成": "zh",
        "작업이 완료되었습니다": "ko",
        "اكتملت المهمة": "ar",
        "המשימה הושלמה": "he",
        "काम पूरा हो गया": "hi",
    }

    def test_cases(self):
        c = cfg(detect="all")
        wrong = {t: f.detect(t, c) for t, want in self.CASES.items() if f.detect(t, c) != want}
        self.assertEqual(wrong, {})

    def test_every_detectable_language_has_a_voice(self):
        for code, e in f.LANGS.items():
            self.assertTrue(any(v["lang"] == code for v in f.VOICES.values()), code)


class Voices(unittest.TestCase):
    def test_main_voice_for_its_language(self):
        self.assertEqual(f.voice_for("en", cfg(), "anime-sexy"), "anime-sexy")

    def test_native_voice_same_gender(self):
        self.assertEqual(f.VOICES[f.voice_for("sr", cfg(), "anime-sexy")]["g"], "f")
        self.assertEqual(f.VOICES[f.voice_for("sr", cfg(), "deep")]["g"], "m")
        self.assertEqual(f.VOICES[f.voice_for("de", cfg(), "deep")]["lang"], "de")

    def test_chosen_voice_for_language(self):
        self.assertEqual(f.voice_for("sr", cfg(lang_voices={"sr": "sr-nicholas"}), "anime-sexy"), "sr-nicholas")

    def test_english_when_main_voice_is_foreign(self):
        self.assertEqual(f.voice_for("en", cfg(voice="sr-sophie"), "sr-sophie"), "anime-sexy")

    def test_offline_fallback(self):
        chain = f.fallback_chain("es-elvira", cfg())
        self.assertEqual(chain[1], "es-dora-local")
        self.assertEqual(chain[-1], "zira")

    def test_blends_reference_real_kokoro_voices(self):
        names = {"af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova",
                 "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
                 "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
                 "bm_daniel", "bm_fable", "bm_george", "bm_lewis", "ef_dora", "em_alex", "ff_siwis", "hf_alpha",
                 "hf_beta", "hm_omega", "hm_psi", "if_sara", "im_nicola", "jf_alpha", "jf_gongitsune",
                 "jf_nezumi", "jf_tebukuro", "jm_kumo", "pf_dora", "pm_alex"}
        for n, v in f.VOICES.items():
            if v["engine"] == "kokoro":
                for part in v["id"].split("+"):
                    self.assertIn(part.split("*")[0], names, n)


class Text(unittest.TestCase):
    def test_strips_code_paths_links_markdown(self):
        t = f.short_text("**Fixed** `foo()` in src/app.py, see https://x.y 🎉 done", 14)
        self.assertEqual(t, "Fixed in , see done")

    def test_word_limit(self):
        self.assertEqual(len(f.short_text(" ".join(["word"] * 30), 14).split()), 14)

    def test_keeps_marks_of_other_scripts(self):
        self.assertEqual(f.short_text("काम पूरा हो गया", 14), "काम पूरा हो गया")


class Mcp(unittest.TestCase):
    def test_protocol(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "nope"},
        ]
        data = "".join(json.dumps(m) + "\n" for m in msgs).encode()
        out = subprocess.run([sys.executable, os.path.join(ROOT, "finished.py"), "mcp"], input=data,
                             capture_output=True, timeout=60).stdout.decode().splitlines()
        res = [json.loads(line) for line in out]
        self.assertEqual([r["id"] for r in res], [1, 2, 3])
        self.assertEqual(res[0]["result"]["serverInfo"]["name"], "finished")
        tool = res[1]["result"]["tools"][0]
        self.assertEqual(tool["name"], "notify_finished")
        self.assertIn("language", tool["inputSchema"]["properties"])
        self.assertEqual(res[2]["error"]["code"], -32601)


class Speaking(unittest.TestCase):
    """What is said, without making sound: synth and play are replaced."""

    def setUp(self):
        self.said = []
        self.old = f.synth, f.play
        f.synth = lambda text, voice, cfg: self.said.append((text, voice)) or "x.wav"
        f.play = lambda paths: None

    def tearDown(self):
        f.synth, f.play = self.old

    def test_english_only_says_phrase_for_other_languages(self):
        c = cfg(detect=["en", "sr"], speak="main", phrase="Finished, senpai!")
        f.speak([("Završio sam login stranicu", None)], c, "anime-sexy", c["phrase"])
        self.assertEqual(self.said, [("Finished, senpai!", "anime-sexy")])

    def test_english_only_reads_english(self):
        c = cfg(detect=["en", "sr"], speak="main")
        f.speak([("Login page fixed", None)], c, "anime-sexy", c["phrase"])
        self.assertEqual(self.said, [("Login page fixed", "anime-sexy")])

    def test_both_mode_does_not_repeat_phrase(self):
        c = cfg(detect=["en", "sr"], speak="main")
        f.speak([("Finished", None), ("Završio sam login", None)], c, "anime-sexy", "Finished")
        self.assertEqual(self.said, [("Finished", "anime-sexy")])

    def test_every_language_uses_native_voice(self):
        c = cfg(detect=["en", "sr"], speak="all")
        f.speak([("Završio sam login stranicu", None)], c, "anime-sexy", "Finished")
        self.assertEqual(self.said[0][1], "sr-sophie")

    def test_silent_when_quit(self):
        old = f.load_cfg
        f.load_cfg = lambda: cfg(enabled=False)
        try:
            f.run_job({"message": "Done", "no_toast": True})
        finally:
            f.load_cfg = old
        self.assertEqual(self.said, [])


class Agents(unittest.TestCase):
    """register / unregister on a made-up home folder: must add everything once and
    leave every file byte-for-byte as it was after unregister."""

    FILES = {
        ".claude/settings.json": '{\n  "hooks": {\n    "Stop": [\n      {"hooks": [{"type": "command", "command": "other"}]}\n    ]\n  }\n}\n',
        ".claude/CLAUDE.md": "# My rules\n\n- be brief\n",
        ".codex/config.toml": 'model = "x"\nnotify = [ "node", "old-hook.mjs" ]\n\n[mcp_servers.other]\ncommand = "a"\nargs = ["b"]\n',
        ".codex/AGENTS.md": "\nfirst line\r\nsecond line\r\n",  # mixed line endings
        ".gemini/settings.json": "{}\n",
        ".config/opencode/opencode.json": '{\n  "mcp": {\n    "servers": {}\n  }\n}\n',
    }

    def test_round_trip(self):
        import contextlib
        import io
        import tempfile
        import tomllib
        import agents
        with tempfile.TemporaryDirectory() as home:
            for rel, text in self.FILES.items():
                path = os.path.join(home, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
            old_home, old_claude = agents.HOME_DIR, agents.mcp_add_claude
            agents.HOME_DIR, agents.mcp_add_claude = home, (lambda remove=False: "skipped")
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    agents.connect(["all"])
                    agents.connect(["all"])  # twice: nothing doubled
                with open(os.path.join(home, ".codex/config.toml"), "rb") as fh:
                    codex = tomllib.load(fh)
                self.assertIn("finished.py", codex["notify"][1])
                self.assertEqual(json.loads(codex["notify"][codex["notify"].index("--previous-notify") + 1]),
                                 ["node", "old-hook.mjs"])
                self.assertIn("finished", codex["mcp_servers"])
                with open(os.path.join(home, ".claude/settings.json"), encoding="utf-8") as fh:
                    self.assertEqual(len(json.load(fh)["hooks"]["Stop"]), 2)
                with open(os.path.join(home, ".claude/CLAUDE.md"), encoding="utf-8") as fh:
                    self.assertEqual(fh.read().count(agents.MARK_START), 1)
                self.assertTrue(os.path.exists(os.path.join(home, ".gemini/GEMINI.md")))
                with contextlib.redirect_stdout(io.StringIO()):
                    agents.connect(["all"], remove=True)
            finally:
                agents.HOME_DIR, agents.mcp_add_claude = old_home, old_claude
            for rel, text in self.FILES.items():
                with open(os.path.join(home, rel), encoding="utf-8", newline="") as fh:
                    if rel.endswith(".json"):  # rewritten with standard indenting, same content
                        self.assertEqual(json.loads(fh.read()), json.loads(text), rel)
                    else:  # text files: byte for byte
                        self.assertEqual(fh.read(), text, rel)
            self.assertFalse(os.path.exists(os.path.join(home, ".gemini/GEMINI.md")))

    def test_first_sentence(self):
        import agents
        self.assertEqual(agents.first_sentence("## Done\n\n- Fixed the login bug. Then more.\n"), "Fixed the login bug.")
        self.assertEqual(agents.first_sentence("```\ncode\n```\n3 tests fixed!"), "3 tests fixed!")

    def test_claude_turn_sees_its_own_call(self):
        import tempfile
        import agents
        lines = [
            {"type": "user", "message": {"content": "old prompt"}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__finished__notify_finished"}]}},
            {"type": "user", "message": {"content": "new prompt"}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "All fixed."}]}},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(x) for x in lines))
        try:
            # the call belongs to the previous turn, so this turn still needs a notification
            self.assertEqual(agents.claude_turn(fh.name), ("All fixed.", False))
            with open(fh.name, "a", encoding="utf-8") as out:
                out.write("\n" + json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "mcp__finished__notify_finished"}]}}))
            self.assertEqual(agents.claude_turn(fh.name), ("All fixed.", True))
        finally:
            os.remove(fh.name)

    def test_shell_call_counts_as_notified(self):
        import agents
        yes = ['finished -a Claude "Done"', 'cd x && finished "ok"', "finished", 'finished.cmd -l sr "Gotovo"']
        no = ["finished register all", "finished set voice deep", "finished voices sr", "unfinished work",
              "git commit -m 'finished docs'x"]
        for c in yes:
            self.assertTrue(agents.SHELL_CALL.search(c), c)
        for c in no:
            self.assertFalse(agents.SHELL_CALL.search(c), c)


if __name__ == "__main__":
    unittest.main()
