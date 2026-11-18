"""finished - any AI agent tells you it is done.

Shows a Windows notification and speaks a short message aloud: local Kokoro voices
(VOICEVOX anime characters, Kokoro, ...) or online voices in 75 languages, with the
message's language detected offline. `finished help` lists the commands and
`finished mcp` runs the MCP server.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata

VERSION = "1.4.0"
HOME = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HOME, "cache")
MODEL = os.path.join(HOME, "models", "kokoro-v1.0.onnx")
VOICE_BIN = os.path.join(HOME, "models", "voices-v1.0.bin")
CONFIG = os.path.join(HOME, "config.json")
LANG_FILE = os.path.join(HOME, "languages.json")
ICON = os.path.join(HOME, "icon.png")
TOAST = os.path.join(HOME, "toast.ps1")
LOCK = os.path.join(CACHE, "speaking.lock")
LOG = os.path.join(CACHE, "finished.log")
PY = sys.executable
PYW = os.path.join(os.path.dirname(PY), "pythonw.exe")
NO_WINDOW = 0x08000000

DEFAULTS = {
    "voice": "metan-sexy",   # main voice (falls back to "heart" without VOICEVOX)
    "lang_voices": {},       # voice per other language, e.g. {"sr": "sr-nicholas"}
    "language": "auto",      # auto = detect each message; or one code, e.g. "en"
    "detect": "all",         # languages auto-detect chooses from: "all" or ["en", "sr"]
    "mode": "agent",         # preset | agent | both
    "phrase": "Finished",
    "volume": 100,           # percent, 0-200
    "toast": True,
    "sound": True,
    "max_words": 14,
    "speak": "all",          # all = every language in its own voice; main = only the main
                             # voice's language, other messages say the ready phrase
    "enabled": True,         # False after Quit in the tray: silent until the app is opened
}

PHRASES = [
    "Finished",
    "Finished, senpai!",
    "All done!",
    "Done. Come and check.",
    "Task complete.",
    "Mission complete!",
    "I'm finished. Your turn.",
    "Gotovo!",
    "おわったよ♡",
    "お疲れさま♡",
    "できたよ、ご主人様♡",
]

SAMPLES = {
    "en": "Finished! Your task is done.",
    "sr": "Gotovo! Tvoj zadatak je završen.", "hr": "Gotovo! Tvoj zadatak je završen.",
    "bs": "Gotovo! Tvoj zadatak je završen.", "sl": "Končano! Tvoja naloga je opravljena.",
    "mk": "Готово! Твојата задача е завршена.", "bg": "Готово! Задачата ти е изпълнена.",
    "ru": "Готово! Твоя задача выполнена.", "uk": "Готово! Твоє завдання виконано.",
    "pl": "Gotowe! Twoje zadanie jest zakończone.", "cs": "Hotovo! Tvůj úkol je dokončen.",
    "sk": "Hotovo! Tvoja úloha je dokončená.", "de": "Fertig! Deine Aufgabe ist erledigt.",
    "nl": "Klaar! Je taak is af.", "sv": "Klart! Din uppgift är färdig.",
    "da": "Færdig! Din opgave er løst.", "nb": "Ferdig! Oppgaven din er gjort.",
    "fi": "Valmis! Tehtäväsi on tehty.", "es": "¡Listo! Tu tarea está terminada.",
    "fr": "Terminé ! Ta tâche est finie.", "it": "Finito! Il tuo compito è completato.",
    "pt": "Pronto! Sua tarefa está concluída.", "ro": "Gata! Sarcina ta este terminată.",
    "hu": "Kész! A feladatod elkészült.", "el": "Τελείωσα! Η εργασία σου ολοκληρώθηκε.",
    "tr": "Bitti! Görevin tamamlandı.", "ja": "終わったよ！タスク完了です。",
    "zh": "完成了！你的任务已经完成。", "ko": "완료! 작업이 끝났어요.",
    "hi": "हो गया! आपका काम पूरा हो गया।", "ar": "انتهيت! مهمتك اكتملت.",
    "he": "סיימתי! המשימה שלך הושלמה.", "id": "Selesai! Tugasmu sudah beres.",
    "vi": "Xong rồi! Nhiệm vụ của bạn đã hoàn thành.", "th": "เสร็จแล้ว! งานของคุณเสร็จเรียบร้อย",
}

# Languages a short text cannot tell apart; their scores are added together.
ALIAS_GROUPS = [("sr", "hr", "bs"), ("nb", "nn")]

# Curated English voices. engine: kokoro = local model, edge = online, sapi = Windows.
# Kokoro voices may be blends: "jf_alpha*0.6+af_nicole*0.4".
EN_VOICES = {
    # Kokoro's Japanese voices speaking English (a Japanese accent, not real anime voices)
    "jp-soft": dict(engine="kokoro", id="jf_alpha*0.6+af_nicole*0.4", speed=0.88, g="f", d="soft and slow, Japanese accent"),
    "jp-whisper": dict(engine="kokoro", id="jf_tebukuro*0.5+af_nicole*0.5", speed=0.85, g="f", tag="sexy", d="whispering, Japanese accent"),
    "jp-girl": dict(engine="kokoro", id="jf_alpha", speed=1.0, g="f", d="girl, Japanese accent"),
    "jp-cute": dict(engine="kokoro", id="jf_nezumi", speed=1.05, g="f", d="cute and high, Japanese accent"),
    "jp-fox": dict(engine="kokoro", id="jf_gongitsune", speed=0.95, g="f", d="playful, Japanese accent"),
    "jp-gentle": dict(engine="kokoro", id="jf_tebukuro", speed=0.92, g="f", d="gentle, Japanese accent"),
    "jp-bella": dict(engine="kokoro", id="jf_alpha*0.5+af_bella*0.5", speed=0.95, g="f", d="lively, Japanese accent"),
    "jp-heart": dict(engine="kokoro", id="jf_alpha*0.4+af_heart*0.6", speed=0.9, g="f", d="warm, light Japanese accent"),
    # other women (local)
    "whisper": dict(engine="kokoro", id="af_nicole", speed=0.9, g="f", tag="sexy", d="breathy ASMR whisper"),
    "sultry": dict(engine="kokoro", id="af_nicole*0.5+af_bella*0.5", speed=0.86, g="f", tag="sexy", d="low, slow and sultry"),
    "bella": dict(engine="kokoro", id="af_bella", speed=0.95, g="f", tag="sexy", d="lively American girl"),
    "heart": dict(engine="kokoro", id="af_heart", speed=0.95, g="f", tag="sexy", d="warm American woman, best quality"),
    "sky": dict(engine="kokoro", id="af_sky", speed=0.95, g="f", d="light American girl"),
    "nova": dict(engine="kokoro", id="af_nova", speed=1.0, g="f", d="American woman"),
    "sarah": dict(engine="kokoro", id="af_sarah", speed=1.0, g="f", d="American woman"),
    "jessica": dict(engine="kokoro", id="af_jessica", speed=1.0, g="f", d="American woman"),
    "aoede": dict(engine="kokoro", id="af_aoede", speed=1.0, g="f", d="American woman"),
    "kore": dict(engine="kokoro", id="af_kore", speed=1.0, g="f", d="American woman"),
    "river": dict(engine="kokoro", id="af_river", speed=1.0, g="f", d="American woman"),
    "emma-uk": dict(engine="kokoro", id="bf_emma", speed=0.95, g="f", d="British woman"),
    "isabella-uk": dict(engine="kokoro", id="bf_isabella", speed=0.95, g="f", d="British woman"),
    "lily-uk": dict(engine="kokoro", id="bf_lily", speed=0.95, g="f", d="British girl"),
    "alice-uk": dict(engine="kokoro", id="bf_alice", speed=0.95, g="f", d="British woman"),
    # men (local)
    "deep": dict(engine="kokoro", id="am_onyx*0.6+am_fenrir*0.4", speed=0.88, g="m", d="deep, slow male voice"),
    "jp-boy": dict(engine="kokoro", id="jm_kumo", speed=0.95, g="m", d="man, Japanese accent"),
    "adam": dict(engine="kokoro", id="am_adam", speed=1.0, g="m", d="American man"),
    "michael": dict(engine="kokoro", id="am_michael", speed=1.0, g="m", d="American man, calm"),
    "fenrir": dict(engine="kokoro", id="am_fenrir", speed=1.0, g="m", d="American man, strong"),
    "puck": dict(engine="kokoro", id="am_puck", speed=1.0, g="m", d="American man, playful"),
    "onyx": dict(engine="kokoro", id="am_onyx", speed=0.95, g="m", d="American man, low"),
    "echo": dict(engine="kokoro", id="am_echo", speed=1.0, g="m", d="American man"),
    "eric": dict(engine="kokoro", id="am_eric", speed=1.0, g="m", d="American man"),
    "liam": dict(engine="kokoro", id="am_liam", speed=1.0, g="m", d="American man, young"),
    "santa": dict(engine="kokoro", id="am_santa", speed=0.95, g="m", d="jolly old man"),
    "george-uk": dict(engine="kokoro", id="bm_george", speed=0.95, g="m", d="British man"),
    "fable-uk": dict(engine="kokoro", id="bm_fable", speed=0.95, g="m", d="British man, storyteller"),
    "lewis-uk": dict(engine="kokoro", id="bm_lewis", speed=0.95, g="m", d="British man, deep"),
    "daniel-uk": dict(engine="kokoro", id="bm_daniel", speed=0.95, g="m", d="British man"),
    # online
    "ava": dict(engine="edge", id="en-US-AvaMultilingualNeural", g="f", d="online, natural woman"),
    "ava-sexy": dict(engine="edge", id="en-US-AvaMultilingualNeural", rate="-15%", pitch="-6Hz", g="f", tag="sexy", d="online, Ava slower and lower"),
    "emma": dict(engine="edge", id="en-US-EmmaMultilingualNeural", g="f", d="online, cheerful woman"),
    "jenny": dict(engine="edge", id="en-US-JennyNeural", g="f", d="online, friendly woman"),
    "aria": dict(engine="edge", id="en-US-AriaNeural", g="f", d="online, confident woman"),
    "sonia-uk": dict(engine="edge", id="en-GB-SoniaNeural", g="f", d="online, British woman"),
    "andrew": dict(engine="edge", id="en-US-AndrewMultilingualNeural", g="m", d="online, warm man"),
    "brian": dict(engine="edge", id="en-US-BrianMultilingualNeural", g="m", d="online, casual man"),
    "christopher": dict(engine="edge", id="en-US-ChristopherNeural", g="m", d="online, deep man"),
    "guy": dict(engine="edge", id="en-US-GuyNeural", g="m", d="online, man"),
    "ryan-uk": dict(engine="edge", id="en-GB-RyanNeural", g="m", d="online, British man"),
    # Windows built-in (always offline, robotic)
    "zira": dict(engine="sapi", id="Microsoft Zira Desktop", g="f", d="Windows built-in woman (robotic)"),
    "david": dict(engine="sapi", id="Microsoft David Desktop", g="m", d="Windows built-in man (robotic)"),
}
EN_DEFAULT = {"f": "heart", "m": "deep"}
# names from before 1.4, so old settings keep working
OLD_NAMES = {'anime-sexy': 'jp-soft', 'anime-whisper': 'jp-whisper', 'anime-cute': 'jp-cute', 'anime-fox': 'jp-fox', 'anime-soft': 'jp-gentle', 'anime-bella': 'jp-bella', 'anime-heart': 'jp-heart', 'anime-boy': 'jp-boy'}


# Kokoro's own voices for other languages: work offline (espeak-ng code in "k").
KOKORO_NATIVE = {
    "es-dora-local": ("ef_dora", "f", "es", "es"), "es-alex-local": ("em_alex", "m", "es", "es"),
    "fr-siwis-local": ("ff_siwis", "f", "fr", "fr-fr"),
    "it-sara-local": ("if_sara", "f", "it", "it"), "it-nicola-local": ("im_nicola", "m", "it", "it"),
    "pt-dora-local": ("pf_dora", "f", "pt", "pt-br"), "pt-alex-local": ("pm_alex", "m", "pt", "pt-br"),
    "hi-alpha-local": ("hf_alpha", "f", "hi", "hi"), "hi-beta-local": ("hf_beta", "f", "hi", "hi"),
    "hi-omega-local": ("hm_omega", "m", "hi", "hi"), "hi-psi-local": ("hm_psi", "m", "hi", "hi"),
}
# VOICEVOX: free Japanese anime character voices that run locally (`finished voicevox install`).
# They also read English words, with a Japanese accent. name: (character, style, gender, description)
VOICEVOX_DIR = os.path.join(HOME, "engines", "voicevox")
VOICEVOX_URL = "http://127.0.0.1:50021"
VOICEVOX_PKG = ("https://github.com/VOICEVOX/voicevox_engine/releases/download/0.26.2/"
                "voicevox_engine-windows-cpu-0.26.2.vvpp")
VOICEVOX_VOICES = {
    "metan-sexy": ("四国めたん", "セクシー", "f", "Shikoku Metan, sexy - anime"),
    "metan-whisper": ("四国めたん", "ささやき", "f", "Shikoku Metan, whispering in your ear - anime"),
    "metan-hush": ("四国めたん", "ヒソヒソ", "f", "Shikoku Metan, hushed - anime"),
    "metan-sweet": ("四国めたん", "あまあま", "f", "Shikoku Metan, sweet - anime"),
    "metan-tsun": ("四国めたん", "ツンツン", "f", "Shikoku Metan, tsundere - anime"),
    "sora-sexy": ("九州そら", "セクシー", "f", "Kyushu Sora, sexy - anime"),
    "sora-whisper": ("九州そら", "ささやき", "f", "Kyushu Sora, whispering - anime"),
    "sora-sweet": ("九州そら", "あまあま", "f", "Kyushu Sora, sweet - anime"),
    "zundamon-sexy": ("ずんだもん", "セクシー", "f", "Zundamon, sexy - anime"),
    "zundamon-whisper": ("ずんだもん", "ささやき", "f", "Zundamon, whispering - anime"),
    "zundamon-sweet": ("ずんだもん", "あまあま", "f", "Zundamon, sweet - anime"),
    "tsumugi": ("春日部つむぎ", "ノーマル", "f", "Kasukabe Tsumugi, cheerful gal - anime"),
    "himari": ("冥鳴ひまり", "ノーマル", "f", "Meimei Himari, calm and soft - anime"),
    "sayo": ("小夜/SAYO", "ノーマル", "f", "Sayo, cat girl - anime"),
    "nurse-secret": ("ナースロボ＿タイプＴ", "内緒話", "f", "Nurse Robot Type T, secret whisper - anime"),
    "ryusei": ("青山龍星", "ノーマル", "m", "Aoyama Ryusei, deep - anime"),
    "takehiro": ("玄野武宏", "ノーマル", "m", "Kurono Takehiro - anime"),
    "kotaro": ("白上虎太郎", "ふつう", "m", "Shirakami Kotaro - anime"),
}
ENGINE_LABEL = {"kokoro": "local", "edge": "online", "sapi": "windows", "voicevox": "anime"}


def load_languages():
    try:
        with open(LANG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"en": {"name": "English", "locale": "en-US", "detect": True, "lingua": "en", "voices": []}}


LANGS = load_languages()


def voicevox_installed():
    return os.path.exists(os.path.join(VOICEVOX_DIR, "run.exe"))


def build_voices():
    voices = {}
    if voicevox_installed():
        for name, (chara, style, g, d) in VOICEVOX_VOICES.items():
            voices[name] = dict(engine="voicevox", id=f"{chara}/{style}", g=g, lang="ja", latin=True,
                                tag="anime", d=d)
    for name, v in EN_VOICES.items():
        v = dict(v, lang="en")
        if v["engine"] == "kokoro":
            v["k"] = "en-gb" if all(p.strip().startswith("b") for p in v["id"].split("+")) else "en-us"
        voices[name] = v
    for name, (vid, g, lang, k) in KOKORO_NATIVE.items():
        lname = LANGS.get(lang, {}).get("name", lang)
        voices[name] = dict(engine="kokoro", id=vid, g=g, lang=lang, k=k, speed=1.0,
                            d=f"{lname} {'woman' if g == 'f' else 'man'}, local")
    for code, entry in LANGS.items():
        if code == "en":
            continue
        for v in entry["voices"]:
            voices[v["name"]] = dict(engine="edge", id=v["id"], g=v["g"], lang=code,
                                     d=f"{entry['name']} {'woman' if v['g'] == 'f' else 'man'}, online")
    return voices


VOICES = build_voices()


# ---------------------------------------------------------------- helpers

def log(msg):
    try:
        os.makedirs(CACHE, exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    cfg["voice"] = OLD_NAMES.get(cfg["voice"], cfg["voice"])
    if cfg["voice"] not in VOICES:
        cfg["voice"] = DEFAULTS["voice"] if DEFAULTS["voice"] in VOICES else "heart"
    return cfg


def save_cfg(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")


def lang_name(code):
    return LANGS.get(code, {}).get("name", code)


def short_text(text, max_words):
    """Plain, short text for speaking: no code, paths, links, markdown or emoji."""
    t = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"\S*[\\/]\S*\.\w+", " ", t)  # file paths
    t = re.sub(r"[*_#>|\[\]{}<>~^=+]", " ", t)
    # keep letters, combining marks, digits, punctuation and spaces; drop symbols/emoji
    t = "".join(ch for ch in t if unicodedata.category(ch)[0] in "LMNPZ")
    words = t.split()
    if len(words) == 1 and len(words[0]) > max_words * 4:  # scripts without spaces
        words = [words[0][:max_words * 3]]
    return " ".join(words[:max_words]).strip(" ,;:-")


# ---------------------------------------------------------------- language

def detect_candidates(cfg):
    if cfg["detect"] == "all" or not cfg["detect"]:
        return [c for c, e in LANGS.items() if e.get("detect")]
    return [c for c in cfg["detect"] if c in LANGS]


def detect(text, cfg, explain=False):
    """Best language for `text` among the user's candidates. Offline (Lingua)."""
    mv = VOICES[cfg["voice"]]
    primary = "en" if mv.get("latin") else mv["lang"]  # a Japanese voice that reads English: English
    cands = detect_candidates(cfg)
    for code in (primary, mv["lang"]):  # the main voice's own languages always count
        if code not in cands and code in LANGS:
            cands.append(code)
    if len(cands) == 1 or not re.search(r"[^\W\d_]", text):
        return (primary, {}) if explain else primary
    from lingua import IsoCode639_1, LanguageDetectorBuilder
    # Lingua code -> our code; aliases count for the candidate in their group.
    to_ours = {}
    for c in cands:
        to_ours[LANGS[c].get("lingua", c)] = c
    for group in ALIAS_GROUPS:
        owner = next((c for c in group if c in cands), None)
        if owner:
            for alias in group:
                to_ours.setdefault(alias, owner)
    isos = [getattr(IsoCode639_1, code.upper()) for code in to_ours if hasattr(IsoCode639_1, code.upper())]
    if len(isos) < 2:
        return (primary, {}) if explain else primary
    detector = LanguageDetectorBuilder.from_iso_codes_639_1(*isos).build()
    scores = {}
    for cv in detector.compute_language_confidence_values(text):
        ours = to_ours.get(cv.language.iso_code_639_1.name.lower())
        if ours:
            scores[ours] = scores.get(ours, 0.0) + cv.value
    best = max(scores, key=scores.get) if scores else primary
    # A single word is a guess ("Done", "OK"); keep the main language unless sure.
    # Two or three letters ("OK", "API") say almost nothing, so ask for more.
    if len(text.split()) <= 1 and best != primary:
        letters = sum(ch.isalpha() for ch in text)
        if scores.get(best, 0) < (0.95 if letters <= 3 else 0.65):
            best = primary
    return (best, scores) if explain else best


def voice_for(lang, cfg, main):
    """Voice that speaks `lang`: the main voice if it is in that language, else the chosen
    or default voice of that language, same gender as the main voice where possible."""
    mv = VOICES[main]
    if mv["lang"] == lang or (mv.get("latin") and lang == "en"):
        return main
    pick = cfg["lang_voices"].get(lang)
    if pick in VOICES and VOICES[pick]["lang"] == lang:
        return pick
    if lang == "en":
        return EN_DEFAULT[mv["g"]]
    same = [n for n, v in VOICES.items() if v["lang"] == lang and v["engine"] == "edge"]
    pref = [n for n in same if VOICES[n]["g"] == mv["g"]] or same
    if pref:
        return pref[0]
    local = [n for n, v in VOICES.items() if v["lang"] == lang]
    return local[0] if local else main


def fallback_chain(name, cfg):
    v = VOICES[name]
    chain = [name]
    if v["engine"] == "edge":  # offline: Kokoro voice of the same language, then main voice
        local = [n for n, x in VOICES.items() if x["lang"] == v["lang"] and x["engine"] == "kokoro"]
        local.sort(key=lambda n: VOICES[n]["g"] != v["g"])
        chain += local[:1]
        if v["lang"] == "en":
            chain.append(EN_DEFAULT[v["g"]])
        elif VOICES[cfg["voice"]]["engine"] == "kokoro":
            chain.append(cfg["voice"])
    if v["engine"] == "voicevox":  # engine missing or not starting: a Japanese, then English voice
        chain += [n for n in ("ja-keita" if v["g"] == "m" else "ja-nanami", EN_DEFAULT[v["g"]]) if n in VOICES]
    chain.append("david" if v["g"] == "m" else "zira")
    return list(dict.fromkeys(chain))


# ---------------------------------------------------------------- speech

_kokoro = None


def kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(MODEL, VOICE_BIN)
    return _kokoro


def write_wav(path, data, sr, volume):
    import numpy as np
    import soundfile as sf
    data = np.asarray(data, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    lead = np.zeros(int(sr * 0.12), dtype="float32")  # wake the speakers / headphones first
    data = np.clip(np.concatenate([lead, data]) * (volume / 100.0), -1.0, 1.0)
    tmp = path + ".tmp.wav"
    sf.write(tmp, data, sr, subtype="PCM_16")
    os.replace(tmp, path)


def synth_kokoro(text, v, path, volume):
    k = kokoro()
    style = None
    for part in v["id"].split("+"):
        name, _, w = part.partition("*")
        vec = k.get_voice_style(name.strip()) * float(w or 1)
        style = vec if style is None else style + vec
    samples, sr = k.create(text, voice=style, speed=v.get("speed", 1.0), lang=v.get("k", "en-us"))
    write_wav(path, samples, sr, volume)


def synth_edge(text, v, path, volume):
    import asyncio
    import edge_tts
    import soundfile as sf
    mp3 = path + ".mp3"
    comm = edge_tts.Communicate(text, v["id"], rate=v.get("rate", "+0%"), pitch=v.get("pitch", "+0Hz"))
    try:
        asyncio.run(asyncio.wait_for(comm.save(mp3), 12))
        data, sr = sf.read(mp3, dtype="float32")
    finally:
        try:
            os.remove(mp3)
        except OSError:
            pass
    write_wav(path, data, sr, volume)


def synth_sapi(text, v, path, volume):
    import soundfile as sf
    raw = path + ".sapi.wav"
    env = dict(os.environ, FIN_TEXT=text, FIN_VOICE=v["id"], FIN_OUT=raw)
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          "try{$s.SelectVoice($env:FIN_VOICE)}catch{};"
          "$s.SetOutputToWaveFile($env:FIN_OUT);$s.Speak($env:FIN_TEXT);$s.Dispose()")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps],
                   env=env, timeout=30, check=True, creationflags=NO_WINDOW,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        data, sr = sf.read(raw, dtype="float32")
    finally:
        try:
            os.remove(raw)
        except OSError:
            pass
    write_wav(path, data, sr, volume)


def _vv(path, data=None, params=None, timeout=30):
    import urllib.parse
    import urllib.request
    url = VOICEVOX_URL + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, data=data, method="GET" if data is None else "POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def voicevox_running():
    try:
        _vv("/version", timeout=1)
        return True
    except OSError:
        return False


def ensure_voicevox(wait=120):
    """Start the local VOICEVOX engine if it is not running (hidden, once for all callers)."""
    if voicevox_running():
        return
    exe = os.path.join(VOICEVOX_DIR, "run.exe")
    if not os.path.exists(exe):
        raise RuntimeError("VOICEVOX is not installed: finished voicevox install")
    os.makedirs(CACHE, exist_ok=True)
    lock = os.path.join(CACHE, "voicevox.starting")
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        proc = subprocess.Popen([exe, "--host", "127.0.0.1", "--port", "50021"], cwd=VOICEVOX_DIR,
                                creationflags=0x00000008 | 0x00000200, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        with open(os.path.join(CACHE, "voicevox.pid"), "w") as f:
            f.write(str(proc.pid))
    except FileExistsError:
        pass  # someone else is starting it
    try:
        end = time.time() + wait
        while time.time() < end:
            if voicevox_running():
                return
            time.sleep(0.5)
        raise RuntimeError("VOICEVOX did not start")
    finally:
        try:
            if time.time() - os.path.getmtime(lock) > 5 or voicevox_running():
                os.remove(lock)
        except OSError:
            pass


def stop_voicevox():
    pid_file = os.path.join(CACHE, "voicevox.pid")
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        os.remove(pid_file)
        return True
    except (OSError, ValueError):
        return False


def voicevox_speaker(key):
    """Speaker id for 'character/style', from the engine's own list (cached)."""
    path = os.path.join(CACHE, "voicevox_speakers.json")
    ids = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            ids = json.load(f)
    if key not in ids:
        for s in json.loads(_vv("/speakers")):
            for st in s["styles"]:
                ids[f"{s['name']}/{st['name']}"] = st["id"]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ids, f, ensure_ascii=False)
    if key not in ids:
        raise RuntimeError(f"VOICEVOX has no voice {key}")
    return ids[key]


def synth_voicevox(text, v, path, volume):
    import io
    import soundfile as sf
    ensure_voicevox()
    sid = voicevox_speaker(v["id"])
    query = json.loads(_vv("/audio_query", data=b"", params={"text": text, "speaker": sid}))
    query.update(speedScale=v.get("speed", 1.0), pitchScale=v.get("pitch", 0.0),
                 intonationScale=v.get("intonation", 1.0), prePhonemeLength=0.05, postPhonemeLength=0.2)
    wav = _vv("/synthesis", data=json.dumps(query).encode(), params={"speaker": sid}, timeout=90)
    data, sr = sf.read(io.BytesIO(wav), dtype="float32")
    write_wav(path, data, sr, volume)


def install_voicevox():
    """Download and unpack the VOICEVOX engine (CPU build, about 1.9 GB) into engines/voicevox."""
    import urllib.request
    import zipfile
    print("VOICEVOX is free software with Japanese anime character voices (https://voicevox.hiroshiba.jp).\n"
          "Each character has its own terms (https://voicevox.hiroshiba.jp/term/). If you publish audio made\n"
          "with it, credit the character, e.g. 'VOICEVOX:四国めたん'.\n")
    if voicevox_installed():
        print("Already installed:", VOICEVOX_DIR)
        return 0
    pkg = os.path.join(HOME, "engines", "voicevox.vvpp")
    os.makedirs(os.path.dirname(pkg), exist_ok=True)
    if not os.path.exists(pkg):
        print("Downloading (about 1.9 GB)...")
        tmp = pkg + ".part"
        with urllib.request.urlopen(VOICEVOX_PKG) as r, open(tmp, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1 << 20):
                out.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done * 100 // total}%", end="", flush=True)
        print()
        os.replace(tmp, pkg)
    print("Unpacking...")
    with zipfile.ZipFile(pkg) as z:
        names = z.namelist()
        run = next(n for n in names if n.endswith("run.exe"))
        prefix = run[: -len("run.exe")]
        for n in names:
            if not n.startswith(prefix) or n.endswith("/"):
                continue
            dest = os.path.join(VOICEVOX_DIR, *n[len(prefix):].split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(n) as src_f, open(dest, "wb") as out:
                shutil.copyfileobj(src_f, out, 1 << 20)
    os.remove(pkg)
    print("Starting it once to check...")
    ensure_voicevox()
    print("Installed. Voices: " + ", ".join(VOICEVOX_VOICES) + "\nPick one: finished set voice metan-sexy")
    return 0


ENGINES = {"kokoro": synth_kokoro, "edge": synth_edge, "sapi": synth_sapi, "voicevox": synth_voicevox}


def synth(text, name, cfg):
    """Cached WAV of `text` in voice `name`; falls back to other engines if one fails."""
    os.makedirs(CACHE, exist_ok=True)
    for cand in fallback_chain(name, cfg):
        v = VOICES[cand]
        key = hashlib.sha1(json.dumps([v, text, cfg["volume"]], sort_keys=True).encode()).hexdigest()[:20]
        path = os.path.join(CACHE, key + ".wav")
        if os.path.exists(path):
            os.utime(path)
            return path
        try:
            ENGINES[v["engine"]](text, v, path, cfg["volume"])
            prune_cache()
            return path
        except Exception as e:  # try the next voice in the chain
            log(f"{cand} ({v['engine']}) failed: {e!r}")
    return None


def prune_cache(keep=500):
    try:
        files = [os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.endswith(".wav")]
        if len(files) > keep:
            files.sort(key=os.path.getmtime)
            for f in files[:len(files) - keep]:
                os.remove(f)
    except OSError:
        pass


def lock_speaker(timeout=90):
    """One voice at a time, so agents finishing together take turns."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(LOCK) > 40:
                    os.remove(LOCK)
                    continue
            except OSError:
                pass
            time.sleep(0.15)
    return False


def play(paths):
    import winsound
    got = lock_speaker()
    try:
        for p in paths:
            winsound.PlaySound(p, winsound.SND_FILENAME)
    finally:
        if got:
            try:
                os.remove(LOCK)
            except OSError:
                pass


def speak(parts, cfg, main=None, phrase=None):
    """Speak each (text, language or None) in that language's voice, one after another.
    Language: the one given, else the fixed setting, else detected from the text.
    With speak = "main", a message in another language than the main voice's is replaced
    by the ready phrase (the notification still shows the message)."""
    main = main or cfg["voice"]
    main_lang = VOICES[main]["lang"]
    paths = []
    said_phrase = False
    for text, lang in parts:
        text = short_text(text, cfg["max_words"])
        if not text:
            continue
        is_phrase = phrase is not None and text == short_text(phrase, cfg["max_words"])
        code = lang or (cfg["language"] if cfg["language"] in LANGS else detect(text, cfg))
        reads_it = code == main_lang or (VOICES[main].get("latin") and code == "en")
        if not is_phrase and cfg.get("speak") == "main" and not reads_it:
            if said_phrase or not phrase:
                continue
            text = short_text(phrase, cfg["max_words"])
            code, is_phrase = detect(text, cfg), True
        said_phrase = said_phrase or is_phrase
        path = synth(text, voice_for(code, cfg, main), cfg)
        if path:
            paths.append(path)
        else:
            log("no voice could speak: " + text)
    if paths:
        play(paths)
    return bool(paths)


# ---------------------------------------------------------------- notification

def show_toast(title, body):
    if not os.path.exists(ICON):
        make_icon(ICON)
    env = dict(os.environ, FIN_TITLE=title, FIN_BODY=body, FIN_ICON=ICON)
    return subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-WindowStyle", "Hidden", "-File", TOAST],
        env=env, creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_icon(path, n=128):
    """Pink-to-violet circle with a white check mark, written as a PNG."""
    import math
    import struct
    import zlib
    cx = cy = n / 2
    r = n / 2 - 2
    p = [(0.28 * n, 0.53 * n), (0.44 * n, 0.68 * n), (0.73 * n, 0.36 * n)]

    def seg(px, py, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)

    rows = []
    for y in range(n):
        row = bytearray([0])
        for x in range(n):
            px, py = x + 0.5, y + 0.5
            alpha = max(0.0, min(1.0, r - math.hypot(px - cx, py - cy) + 0.5))
            t = (x + y) / (2 * n)
            rgb = [255 * (1 - t) + 123 * t, 95 * (1 - t) + 92 * t, 162 * (1 - t) + 255 * t]
            w = max(0.0, min(1.0, 0.065 * n - min(seg(px, py, p[0], p[1]), seg(px, py, p[1], p[2])) + 0.5))
            row += bytes([int(c * (1 - w) + 255 * w) for c in rgb] + [int(alpha * 255)])
        rows.append(bytes(row))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- jobs

def run_job(job):
    cfg = load_cfg()
    if not cfg.get("enabled", True) and not job.get("warm"):
        return  # the user quit finished; it stays silent until the app is opened again
    if job.get("warm"):
        for text in [cfg["phrase"]] + job.get("extra", []):
            t = short_text(text, cfg["max_words"])
            code = cfg["language"] if cfg["language"] in LANGS else detect(t, cfg)
            synth(t, voice_for(code, cfg, cfg["voice"]), cfg)
        return
    phrase = (job.get("phrase") or cfg["phrase"]).strip() or "Finished"
    message = (job.get("message") or "").strip()
    agent = (job.get("agent") or "").strip()
    lang = job.get("language") if job.get("language") in LANGS else None
    if cfg["mode"] == "preset" or not short_text(message, cfg["max_words"]):
        parts = [(phrase, None)]
    elif cfg["mode"] == "agent":
        parts = [(message, lang)]
    else:
        parts = [(phrase, None), (message, lang)]

    toast = None
    if cfg["toast"] and not job.get("no_toast"):
        title = f"{agent}: {phrase}" if agent else phrase
        try:
            toast = show_toast(title, message[:220] if message else "Task finished.")
        except OSError as e:
            log(f"toast failed: {e!r}")
    if cfg["sound"] and not job.get("no_voice"):
        main = job.get("voice") if job.get("voice") in VOICES else cfg["voice"]
        speak(parts, cfg, main, phrase)
    if toast:
        try:
            toast.wait(15)
        except subprocess.TimeoutExpired:
            pass


def spawn(job):
    """Run the job in the background so the calling agent is not held up."""
    env = dict(os.environ, FIN_JOB=json.dumps(job, ensure_ascii=False))
    exe = PYW if os.path.exists(PYW) else PY
    base = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    for flags in (base | 0x01000000, base):  # try to break away from the caller's job object
        try:
            subprocess.Popen([exe, os.path.abspath(__file__), "_job"], env=env, creationflags=flags,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True, cwd=HOME)
            return
        except OSError:
            continue
    run_job(job)


# ---------------------------------------------------------------- MCP server

def mcp_tools():
    cfg = load_cfg()
    if cfg.get("speak") == "main":  # only the main voice's language is read aloud
        mv = VOICES[cfg["voice"]]
        rule = "Write it in English." if mv.get("latin") else f"Write it in {lang_name(mv['lang'])}."
    elif cfg["language"] in LANGS:
        rule = f"Write it in {lang_name(cfg['language'])}."
    elif cfg["detect"] != "all" and cfg["detect"]:
        rule = "Write it in the user's language (" + ", ".join(lang_name(c) for c in detect_candidates(cfg)) + ")."
    else:
        rule = "Write it in the user's language."
    return [{
        "name": "notify_finished",
        "description": (
            "Tell the user you are done: shows a Windows notification and speaks a short message aloud "
            "in the voice the user picked. Call it once, when the whole task the user asked for is finished "
            "(not after each step), and also when you are stuck and need the user. Keep `message` very short "
            f"(max 12 words): what you finished, in plain words, no code, file paths or markdown. {rule} "
            "Set `language` to the ISO 639-1 code of the message so the right voice reads it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What you finished, max 12 words, e.g. 'Login page fixed and tests pass'."},
                "language": {"type": "string", "description": "ISO 639-1 code of the message language, e.g. en, sr, de, ja."},
                "agent": {"type": "string", "description": "Your name, e.g. Claude, Codex, Gemini, OpenCode."},
            },
            "required": ["message"],
        },
    }]


def mcp():
    out = sys.stdout.buffer

    def send(obj):
        out.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        out.flush()

    for line in sys.stdin.buffer:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if not isinstance(req, dict) or "id" not in req:
            continue  # notifications need no answer
        rid, method, params = req["id"], req.get("method"), req.get("params") or {}
        if method == "initialize":
            res = {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": "finished", "version": VERSION},
                   "instructions": "When you finish the user's task, call notify_finished once with a very short summary."}
        elif method == "ping":
            res = {}
        elif method == "tools/list":
            res = {"tools": mcp_tools()}
        elif method == "resources/list":
            res = {"resources": []}
        elif method == "prompts/list":
            res = {"prompts": []}
        elif method == "tools/call":
            if params.get("name") != "notify_finished":
                send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "unknown tool"}})
                continue
            args = params.get("arguments") or {}
            job = {"message": str(args.get("message") or "").strip(),
                   "agent": str(args.get("agent") or "").strip(),
                   "language": str(args.get("language") or "").strip().lower()[:3]}
            if not load_cfg().get("enabled", True):
                res = {"content": [{"type": "text", "text": "finished is turned off (the user quit it); nothing was shown."}], "isError": False}
                send({"jsonrpc": "2.0", "id": rid, "result": res})
                continue
            try:
                spawn(job)
                import agents
                agents.mark_mcp_call(job["agent"])  # so the end-of-turn hook does not repeat it
                res = {"content": [{"type": "text", "text": "The user was notified: " + (job["message"] or "finished")}], "isError": False}
            except Exception as e:
                res = {"content": [{"type": "text", "text": f"Could not notify: {e}"}], "isError": True}
        else:
            send({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}})
            continue
        send({"jsonrpc": "2.0", "id": rid, "result": res})


# ---------------------------------------------------------------- CLI

HELP = """finished - tell the user an agent is done (notification + voice)

  finished "Login page fixed"          notify and speak the message
  finished -a Codex "Tests pass"       with the agent's name
  finished                             only the chosen ready phrase (e.g. "Finished")
      -l CODE   message language (skip detection)   -v VOICE  another voice this time
      -p N|"text"  another phrase this time          -w        wait until it has spoken
      --no-voice / --no-toast

  finished voices [CODE|anime|sexy|female|male|local|online|all]
  finished preview [same filters or voice names] [--text "..."]
  finished languages                   supported languages (* = auto-detect picks from these)
  finished detect "text"               which language a text is detected as, with scores
  finished phrases                     ready phrases

  finished set voice NAME              main voice (speaks messages in its own language)
  finished set voice-for CODE NAME     voice for another language, e.g. voice-for sr sr-nicholas
  finished set language auto|CODE     auto = detect every message; CODE = always that language
  finished set detect all|en,sr,...    languages auto-detect picks from (fewer = more precise)
  finished set speak all|main         main = read aloud only the main voice's language;
                                       messages in other languages say the ready phrase
  finished set mode preset|agent|both  preset = always the phrase, agent = the agent's message,
                                       both = phrase, then message
  finished set phrase N|"text"         ready phrase by number, or your own
  finished set volume 0-200 | toast on|off | sound on|off | words 3-40

  finished app                         open the settings window (finished runs in the tray)
  finished quit                        quit the tray app: finished stays silent until opened again
  finished uninstall                   quit, disconnect all agents, remove shortcut and autostart
  finished setup                       text menu: try and pick voice, languages, phrase, mode
  finished config                      current settings
  finished register [all|claude|codex|grok|gemini|qwen|cursor|windsurf|opencode]
                                       connect installed agents: MCP tool, automatic
                                       notifications, one rule in their instructions
                                       (every changed file is backed up first)
  finished unregister [all|AGENT]      remove all of that again
  finished hook claude|codex|NAME      what agents run when a turn ends (--dry = print only)
  finished voicevox install|start|stop  anime voices (VOICEVOX, about 1.9 GB, runs locally)
  finished mcp                         MCP server (tool notify_finished)
"""


def describe(name, cur):
    v = VOICES[name]
    mark = "*" if name == cur else " "
    return f"  {mark} {name:<16} {'woman' if v['g'] == 'f' else 'man  '} {ENGINE_LABEL[v['engine']]:<7} {v['d']}"


def voice_filter(args):
    if not args:
        return [n for n, v in VOICES.items() if v["lang"] == "en" or v["engine"] == "voicevox"]
    picked = []
    for a in args:
        a = a.lower()
        if a in VOICES:
            picked.append(a)
        elif a == "all":
            picked += list(VOICES)
        elif a == "anime":
            picked += [n for n, v in VOICES.items() if v["engine"] == "voicevox"]
        elif a == "sexy":
            picked += [n for n, v in VOICES.items() if v.get("tag") in ("sexy", "anime") and v["g"] == "f"]
        elif a in ("female", "women"):
            picked += [n for n, v in VOICES.items() if v["g"] == "f" and v["lang"] == "en"]
        elif a in ("male", "men"):
            picked += [n for n, v in VOICES.items() if v["g"] == "m" and v["lang"] == "en"]
        elif a in ("local", "online", "windows"):
            picked += [n for n, v in VOICES.items() if ENGINE_LABEL[v["engine"]] == a]
        elif a in LANGS:
            picked += [n for n, v in VOICES.items() if v["lang"] == a]
        else:
            print(f"No voice or language '{a}'. See: finished voices, finished languages")
    return list(dict.fromkeys(picked))


def cmd_voices(args, cfg):
    names = voice_filter(args)
    cur = cfg["voice"]
    if not args:
        groups = [("Anime girls (VOICEVOX, local)", lambda v: v["engine"] == "voicevox" and v["g"] == "f"),
                  ("Anime men (VOICEVOX, local)", lambda v: v["engine"] == "voicevox" and v["g"] == "m"),
                  ("Women (Kokoro, local)", lambda v: v["g"] == "f" and v["engine"] == "kokoro"),
                  ("Men (Kokoro, local)", lambda v: v["g"] == "m" and v["engine"] == "kokoro"),
                  ("Online (internet)", lambda v: v["engine"] == "edge"),
                  ("Windows (offline, robotic)", lambda v: v["engine"] == "sapi")]
        for title, test in groups:
            print(f"\n{title}")
            for n in names:
                if test(VOICES[n]):
                    print(describe(n, cur))
        others = len(VOICES) - len(names)
        if not voicevox_installed():
            print("\nAnime voices (VOICEVOX): finished voicevox install")
        print(f"\n+ {others} voices in {len(LANGS) - 1} other languages: finished voices CODE (see finished languages)")
    else:
        lang = None
        for n in names:
            if VOICES[n]["lang"] != lang:
                lang = VOICES[n]["lang"]
                print(f"\n{lang_name(lang)} ({lang})")
            print(describe(n, cur))
    print(f"\nMain voice: {cur}.  Change: finished set voice NAME   Try: finished preview NAME")


def cmd_languages(cfg):
    cands = set(detect_candidates(cfg))
    print(f"Language: {cfg['language']}   Auto-detect picks from: "
          f"{'all' if cfg['detect'] == 'all' else ', '.join(sorted(cands))}\n")
    print("     code  language               auto  voices  speaks it")
    for code, e in sorted(LANGS.items(), key=lambda kv: kv[1]["name"]):
        n = sum(1 for v in VOICES.values() if v["lang"] == code)
        mark = "*" if code in cands else " "
        auto = "yes" if e.get("detect") else "no"
        print(f"  {mark}  {code:<5} {e['name']:<22} {auto:<5} {n:>4}    {voice_for(code, cfg, cfg['voice'])}")
    print("\nfinished set detect en,sr   (only these, most precise)   finished set detect all"
          "\nfinished set language sr    (always this language)       finished set language auto"
          "\n'auto no' languages are spoken when an agent passes the code (-l / language).")


def cmd_detect(args, cfg):
    text = " ".join(args)
    if not text:
        print('Usage: finished detect "text"')
        return 1
    code, scores = detect(short_text(text, 40), cfg, explain=True)
    top = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
    print(f"{lang_name(code)} ({code}) -> voice {voice_for(code, cfg, cfg['voice'])}")
    for c, s in top:
        print(f"  {c:<4} {lang_name(c):<20} {s:.2f}")
    return 0


def cmd_preview(args, cfg):
    text = None
    if "--text" in args:
        i = args.index("--text")
        text = " ".join(args[i + 1:]) or None
        args = args[:i]
    names = voice_filter(args or ["anime"])
    for name in names:
        v = VOICES[name]
        sample = text or SAMPLES.get(v["lang"], SAMPLES["en"])
        print(f"> {name:<16} {v['d']}", flush=True)
        path = synth(short_text(sample, 30), name, cfg)
        if path:
            play([path])
        else:
            print("  (failed, see cache/finished.log)")


def parse_codes(val):
    if val.strip().lower() == "all":
        return "all"
    codes = [c.strip().lower() for c in re.split(r"[,\s]+", val) if c.strip()]
    bad = [c for c in codes if c not in LANGS]
    if bad or not codes:
        return None
    return codes


def set_value(cfg, key, val):
    if key == "voice":
        if val not in VOICES:
            return f"No voice '{val}'. See: finished voices"
        cfg["voice"] = val
    elif key in ("voice-for", "lang-voice"):
        parts = val.split()
        if len(parts) != 2 or parts[0] not in LANGS:
            return "Usage: finished set voice-for CODE VOICE   e.g. voice-for sr sr-nicholas"
        code, name = parts
        if name in ("default", "auto"):
            cfg["lang_voices"].pop(code, None)
        elif name not in VOICES or VOICES[name]["lang"] != code:
            return f"'{name}' is not a {lang_name(code)} voice. See: finished voices {code}"
        else:
            cfg["lang_voices"] = dict(cfg["lang_voices"], **{code: name})
    elif key == "language":
        val = val.lower()
        if val != "auto" and val not in LANGS:
            return "language is auto or a code from: finished languages"
        cfg["language"] = val
    elif key == "detect":
        codes = parse_codes(val)
        if codes is None:
            return "detect is all or codes from finished languages, e.g. en,sr"
        cfg["detect"] = codes
    elif key == "speak":
        if val not in ("all", "main"):
            return "speak is all (every language in its own voice) or main (only the main voice's language)"
        cfg["speak"] = val
    elif key == "mode":
        if val not in ("preset", "agent", "both"):
            return "mode is preset, agent or both"
        cfg["mode"] = val
    elif key == "phrase":
        if val.isdigit() and 1 <= int(val) <= len(PHRASES):
            val = PHRASES[int(val) - 1]
        if not val.strip():
            return "The phrase cannot be empty"
        cfg["phrase"] = val.strip()
    elif key == "volume":
        if not val.isdigit() or not 0 <= int(val) <= 200:
            return "volume is 0-200"
        cfg["volume"] = int(val)
    elif key in ("toast", "sound"):
        if val not in ("on", "off"):
            return f"{key} is on or off"
        cfg[key] = val == "on"
    elif key in ("words", "max_words"):
        if not val.isdigit() or not 3 <= int(val) <= 40:
            return "words is 3-40"
        cfg["max_words"] = int(val)
    else:
        return f"Unknown setting '{key}'. See: finished help"
    return None


def cmd_set(args, cfg):
    if len(args) < 2:
        print("Example: finished set voice metan-sexy")
        return 1
    err = set_value(cfg, args[0], " ".join(args[1:]))
    if err:
        print(err)
        return 1
    save_cfg(cfg)
    print(f"OK: {args[0]} = {' '.join(args[1:])}")
    if args[0] in ("voice", "phrase", "volume", "voice-for", "language"):
        spawn({"warm": True})  # get the phrase ready so it plays instantly
    return 0


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def cmd_setup(cfg):
    names = [n for n, v in VOICES.items() if v["engine"] == "voicevox"] + [n for n, v in VOICES.items() if v["lang"] == "en"]
    print("1/4  Main voice")
    while True:
        for i, n in enumerate(names, 1):
            v = VOICES[n]
            print(f" {'*' if n == cfg['voice'] else ' '}{i:>3}. {n:<14} {ENGINE_LABEL[v['engine']]:<7} {v['d']}")
        ans = ask(f"\nNumber to hear it, or a voice name (Enter = keep '{cfg['voice']}'): ")
        if not ans:
            break
        name = names[int(ans) - 1] if ans.isdigit() and 1 <= int(ans) <= len(names) else ans
        if name not in VOICES:
            print(f"No voice '{ans}'.")
            continue
        path = synth(SAMPLES.get(VOICES[name]["lang"], SAMPLES["en"]), name, cfg)
        if path:
            play([path])
        if ask(f"Use '{name}'? [y/N]: ").lower() in ("y", "yes", "d", "da"):
            cfg["voice"] = name
            break
    print("\n2/4  Languages")
    print("  Which languages do your agents write in? Fewer = more precise detection.")
    ans = ask(f"  Codes like en,sr or 'all' (Enter = keep '{cfg['detect'] if cfg['detect'] == 'all' else ','.join(cfg['detect'])}'): ")
    if ans:
        codes = parse_codes(ans)
        if codes is None:
            print("  Unknown code, kept as it was. See: finished languages")
        else:
            cfg["detect"] = codes
            cfg["language"] = codes[0] if codes != "all" and len(codes) == 1 else "auto"
    print("\n3/4  Ready phrase")
    for i, p in enumerate(PHRASES, 1):
        print(f"  {i}. {p}")
    ans = ask(f"  Number or your own text (Enter = keep '{cfg['phrase']}'): ")
    if ans:
        set_value(cfg, "phrase", ans)
    print("\n4/4  What to say\n  1. preset - always the ready phrase\n  2. agent  - the agent's short message"
          "\n  3. both   - the phrase, then the message")
    ans = ask(f"  Choice (Enter = keep '{cfg['mode']}'): ")
    if ans in ("1", "2", "3"):
        cfg["mode"] = ["preset", "agent", "both"][int(ans) - 1]
    save_cfg(cfg)
    print(f"\nSaved: voice {cfg['voice']}, detect {cfg['detect']}, phrase '{cfg['phrase']}', mode {cfg['mode']}.")
    run_job({"message": "Setup finished", "agent": "finished", "language": "en"})


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    cfg = load_cfg()
    cmd = argv[0] if argv else ""
    rest = argv[1:]
    if cmd == "_job":
        try:
            run_job(json.loads(os.environ.get("FIN_JOB", "{}")))
        except Exception as e:
            log(f"job failed: {e!r}")
        return 0
    simple = {
        "mcp": lambda: mcp(),
        "help": lambda: print(HELP), "-h": lambda: print(HELP), "--help": lambda: print(HELP),
        "voices": lambda: cmd_voices(rest, cfg),
        "languages": lambda: cmd_languages(cfg),
        "preview": lambda: cmd_preview(rest, cfg),
        "config": lambda: print(json.dumps(cfg, indent=2, ensure_ascii=False)),
        "setup": lambda: cmd_setup(cfg),
        "--version": lambda: print(VERSION),
    }
    if cmd in simple:
        simple[cmd]()
        return 0
    if cmd in ("app", "tray", "quit", "on", "off", "uninstall"):
        import app
        return app.command(cmd, rest)
    if cmd in ("register", "unregister", "hook"):
        import agents
        if cmd == "hook":
            return agents.hook(rest)
        return agents.connect(rest, remove=cmd == "unregister")
    if cmd == "detect":
        return cmd_detect(rest, cfg)
    if cmd == "voicevox":
        sub = rest[0] if rest else "status"
        if sub == "install":
            return install_voicevox()
        if sub == "start":
            ensure_voicevox()
        elif sub == "stop":
            stop_voicevox()
        print(f"VOICEVOX: {'installed' if voicevox_installed() else 'not installed'}, "
              f"{'running' if voicevox_running() else 'not running'}")
        return 0
    if cmd == "set":
        return cmd_set(rest, cfg)
    if cmd == "phrases":
        for i, p in enumerate(PHRASES, 1):
            print(f"  {'*' if p == cfg['phrase'] else ' '} {i}. {p}")
        print('Pick: finished set phrase N   or your own: finished set phrase "Your text"')
        return 0

    job, words, wait, i = {}, [], False, 0
    while i < len(argv):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None
        if a in ("-a", "--agent") and nxt is not None:
            job["agent"] = nxt
            i += 1
        elif a in ("-l", "--language") and nxt is not None:
            if nxt.lower() not in LANGS:
                print(f"No language '{nxt}'. See: finished languages")
                return 1
            job["language"] = nxt.lower()
            i += 1
        elif a in ("-v", "--voice") and nxt is not None:
            if nxt not in VOICES:
                print(f"No voice '{nxt}'. See: finished voices")
                return 1
            job["voice"] = nxt
            i += 1
        elif a in ("-p", "--phrase") and nxt is not None:
            job["phrase"] = PHRASES[int(nxt) - 1] if nxt.isdigit() and 1 <= int(nxt) <= len(PHRASES) else nxt
            i += 1
        elif a in ("-m", "--message") and nxt is not None:
            words.append(nxt)
            i += 1
        elif a in ("-w", "--wait"):
            wait = True
        elif a == "--no-voice":
            job["no_voice"] = True
        elif a == "--no-toast":
            job["no_toast"] = True
        elif a == "--":
            words += argv[i + 1:]
            break
        else:
            words.append(a)
        i += 1
    job["message"] = " ".join(words).strip()
    if wait:
        run_job(job)
    else:
        spawn(job)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
