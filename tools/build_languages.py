"""Rebuild languages.json: every language the online voices speak, with its voices,
and whether the offline detector (Lingua) can recognise it.

    .venv\\Scripts\\python.exe tools\\build_languages.py
"""
import asyncio
import json
import os

import edge_tts
from lingua import Language

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "languages.json")

# Locale used when a language is spoken in several countries.
PREFERRED = {
    "en": "en-US", "pt": "pt-BR", "zh": "zh-CN", "ar": "ar-SA", "sw": "sw-KE", "ta": "ta-IN",
    "ur": "ur-PK", "bn": "bn-BD", "ms": "ms-MY", "sv": "sv-SE", "da": "da-DK", "nb": "nb-NO",
    "ko": "ko-KR", "ja": "ja-JP", "he": "he-IL", "hi": "hi-IN", "el": "el-GR", "uk": "uk-UA",
    "cs": "cs-CZ", "sl": "sl-SI", "sq": "sq-AL", "ka": "ka-GE", "kk": "kk-KZ", "et": "et-EE",
    "ga": "ga-IE", "cy": "cy-GB", "ca": "ca-ES", "eu": "eu-ES", "gl": "gl-ES", "af": "af-ZA",
    "zu": "zu-ZA", "fa": "fa-IR", "vi": "vi-VN", "fil": "fil-PH", "hy": "hy-AM", "az": "az-AZ",
    "sr": "sr-RS", "bs": "bs-BA", "es": "es-ES", "fr": "fr-FR", "de": "de-DE", "it": "it-IT",
    "nl": "nl-NL", "ne": "ne-NP", "si": "si-LK", "km": "km-KH", "lo": "lo-LA", "my": "my-MM",
    "jv": "jv-ID", "su": "su-ID", "so": "so-SO", "ps": "ps-AF", "uz": "uz-UZ", "mt": "mt-MT",
    "am": "am-ET", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN", "mr": "mr-IN", "te": "te-IN",
    "pa": "pa-IN", "or": "or-IN", "as": "as-IN", "iu": "iu-CA",
}
# Edge code -> Lingua ISO 639-1 code, where they differ.
LINGUA_CODE = {"fil": "tl"}


def short_name(short):
    """'sr-RS-SophieNeural' -> 'sophie', 'de-DE-SeraphinaMultilingualNeural' -> 'seraphina'."""
    rest = short.split("-", 2)[2]
    return rest.replace("MultilingualNeural", "").replace("Neural", "").lower()


async def main():
    voices = await edge_tts.list_voices()
    lingua = {lang.iso_code_639_1.name.lower(): lang.name.title() for lang in Language.all()}
    by_lang = {}
    for v in voices:
        code = v["Locale"].split("-")[0]
        by_lang.setdefault(code, []).append(v)

    table = {}
    for code, vs in sorted(by_lang.items()):
        locales = sorted({v["Locale"] for v in vs})
        locale = PREFERRED.get(code)
        if locale not in locales:
            same = [loc for loc in locales if loc.split("-")[1].lower() == code]
            locale = same[0] if same else locales[0]
        picked = [v for v in vs if v["Locale"] == locale]
        # Multilingual voices are the newest and most natural; list them first.
        picked.sort(key=lambda v: ("Multilingual" not in v["ShortName"], v["ShortName"]))
        name = picked[0]["FriendlyName"].split(" - ")[-1].split(" (")[0]
        entry = {"name": name, "locale": locale, "detect": LINGUA_CODE.get(code, code) in lingua,
                 "lingua": LINGUA_CODE.get(code, code), "voices": []}
        seen = set()
        for v in picked:
            nick = f"{code}-{short_name(v['ShortName'])}"
            if nick in seen:  # the older, non-multilingual twin of a voice
                nick += "-classic"
            seen.add(nick)
            entry["voices"].append({"name": nick, "id": v["ShortName"],
                                    "g": "f" if v["Gender"] == "Female" else "m"})
        table[code] = entry

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(table, f, indent=1, ensure_ascii=False)
        f.write("\n")
    n = sum(len(e["voices"]) for e in table.values())
    print(f"{len(table)} languages, {n} voices, {sum(e['detect'] for e in table.values())} auto-detectable -> {OUT}")


asyncio.run(main())
