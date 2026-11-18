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


if __name__ == "__main__":
    unittest.main()
