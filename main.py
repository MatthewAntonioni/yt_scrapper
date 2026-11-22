import json
import tempfile
import textwrap
import time
from pathlib import Path

import yt_dlp

# ---------- SETTINGS ----------
KEYWORD = "landslide"        # English; translations below are written for this word
RESULTS_PER_COUNTRY = 3
GET_TRANSCRIPTS = True
USE_TRANSLATIONS = True
COUNTRY_LIMIT = None            # test with a few first; set to None for all
DELAY_SECONDS = 3            # pause between requests

OUTPUT_FILE = Path(__file__).resolve().parent / "results2T.txt"

# Optional: real per-country proxies, e.g. {"DE": "http://user:pass@host:port"}
PROXIES = {}

# ---------- COUNTRIES (code: name) ----------
COUNTRIES = {
    "DZ": "Algeria", "AR": "Argentina", "AU": "Australia", "AT": "Austria",
    "AZ": "Azerbaijan", "BH": "Bahrain", "BD": "Bangladesh", "BY": "Belarus",
    "BE": "Belgium", "BO": "Bolivia", "BA": "Bosnia and Herzegovina",
    "BR": "Brazil", "BG": "Bulgaria", "CA": "Canada", "CL": "Chile",
    "CO": "Colombia", "CR": "Costa Rica", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czechia", "DK": "Denmark", "DO": "Dominican Republic",
    "EC": "Ecuador", "EG": "Egypt", "SV": "El Salvador", "EE": "Estonia",
    "FI": "Finland", "FR": "France", "GE": "Georgia", "DE": "Germany",
    "GH": "Ghana", "GR": "Greece", "GT": "Guatemala", "HN": "Honduras",
    "HK": "Hong Kong", "HU": "Hungary", "IS": "Iceland", "IN": "India",
    "ID": "Indonesia", "IQ": "Iraq", "IE": "Ireland", "IL": "Israel",
    "IT": "Italy", "JM": "Jamaica", "JP": "Japan", "JO": "Jordan",
    "KZ": "Kazakhstan", "KE": "Kenya", "KW": "Kuwait", "LV": "Latvia",
    "LB": "Lebanon", "LY": "Libya", "LI": "Liechtenstein", "LT": "Lithuania",
    "LU": "Luxembourg", "MY": "Malaysia", "MT": "Malta", "MX": "Mexico",
    "ME": "Montenegro", "MA": "Morocco", "NP": "Nepal", "NL": "Netherlands",
    "NZ": "New Zealand", "NI": "Nicaragua", "NG": "Nigeria",
    "MK": "North Macedonia", "NO": "Norway", "OM": "Oman", "PK": "Pakistan",
    "PA": "Panama", "PG": "Papua New Guinea", "PY": "Paraguay", "PE": "Peru",
    "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "PR": "Puerto Rico",
    "QA": "Qatar", "RO": "Romania", "RU": "Russia", "SA": "Saudi Arabia",
    "SN": "Senegal", "RS": "Serbia", "SG": "Singapore", "SK": "Slovakia",
    "SI": "Slovenia", "ZA": "South Africa", "KR": "South Korea", "ES": "Spain",
    "LK": "Sri Lanka", "SE": "Sweden", "CH": "Switzerland", "TW": "Taiwan",
    "TZ": "Tanzania", "TH": "Thailand", "TN": "Tunisia", "TR": "Turkey",
    "UG": "Uganda", "UA": "Ukraine", "AE": "United Arab Emirates",
    "GB": "United Kingdom", "US": "United States", "UY": "Uruguay",
    "VE": "Venezuela", "VN": "Vietnam", "YE": "Yemen", "ZW": "Zimbabwe",
}

# ---------- MAIN LANGUAGE PER COUNTRY ----------
LANGUAGES = {
    "DZ": "ar", "AR": "es", "AU": "en", "AT": "de", "AZ": "az", "BH": "ar",
    "BD": "bn", "BY": "be", "BE": "nl", "BO": "es", "BA": "bs", "BR": "pt",
    "BG": "bg", "CA": "en", "CL": "es", "CO": "es", "CR": "es", "HR": "hr",
    "CY": "el", "CZ": "cs", "DK": "da", "DO": "es", "EC": "es", "EG": "ar",
    "SV": "es", "EE": "et", "FI": "fi", "FR": "fr", "GE": "ka", "DE": "de",
    "GH": "en", "GR": "el", "GT": "es", "HN": "es", "HK": "zh-TW", "HU": "hu",
    "IS": "is", "IN": "hi", "ID": "id", "IQ": "ar", "IE": "en", "IL": "iw",
    "IT": "it", "JM": "en", "JP": "ja", "JO": "ar", "KZ": "kk", "KE": "sw",
    "KW": "ar", "LV": "lv", "LB": "ar", "LY": "ar", "LI": "de", "LT": "lt",
    "LU": "fr", "MY": "ms", "MT": "mt", "MX": "es", "ME": "sr", "MA": "ar",
    "NP": "ne", "NL": "nl", "NZ": "en", "NI": "es", "NG": "en", "MK": "mk",
    "NO": "no", "OM": "ar", "PK": "ur", "PA": "es", "PG": "en", "PY": "es",
    "PE": "es", "PH": "tl", "PL": "pl", "PT": "pt", "PR": "es", "QA": "ar",
    "RO": "ro", "RU": "ru", "SA": "ar", "SN": "fr", "RS": "sr", "SG": "en",
    "SK": "sk", "SI": "sl", "ZA": "en", "KR": "ko", "ES": "es", "LK": "si",
    "SE": "sv", "CH": "de", "TW": "zh-TW", "TZ": "sw", "TH": "th", "TN": "ar",
    "TR": "tr", "UG": "en", "UA": "uk", "AE": "ar", "GB": "en", "US": "en",
    "UY": "es", "VE": "es", "VN": "vi", "YE": "ar", "ZW": "en",
}

# ---------- HAND-WRITTEN TRANSLATIONS OF "landslide" ----------
MANUAL_TRANSLATIONS = {
    "ar": "انهيار أرضي", "es": "deslizamiento de tierra", "de": "Erdrutsch",
    "az": "torpaq sürüşməsi", "bn": "ভূমিধস", "be": "апалзень",
    "nl": "aardverschuiving", "bs": "klizište", "pt": "deslizamento de terra",
    "bg": "свлачище", "hr": "klizište", "el": "κατολίσθηση", "cs": "sesuv půdy",
    "da": "jordskred", "et": "maalihe", "fi": "maanvyörymä",
    "fr": "glissement de terrain", "ka": "მეწყერი", "hu": "földcsuszamlás",
    "is": "aurskriða", "hi": "भूस्खलन", "id": "tanah longsor",
    "iw": "מפולת אדמה", "it": "frana", "ja": "地すべり", "kk": "жер көшкіні",
    "sw": "maporomoko ya ardhi", "lv": "zemes nogruvums", "lt": "nuošliauža",
    "ms": "tanah runtuh", "mt": "frana", "sr": "клизиште", "ne": "पहिरो",
    "mk": "свлечиште", "no": "jordskred", "ur": "لینڈ سلائیڈ",
    "tl": "pagguho ng lupa", "pl": "osuwisko", "ro": "alunecare de teren",
    "ru": "оползень", "sk": "zosuv pôdy", "sl": "plaz", "ko": "산사태",
    "si": "නායයෑම", "sv": "jordskred", "th": "ดินถล่ม", "tr": "heyelan",
    "uk": "зсув", "vi": "sạt lở đất", "zh-TW": "山崩",
}

if COUNTRY_LIMIT:
    COUNTRIES = dict(list(COUNTRIES.items())[:COUNTRY_LIMIT])

video_cache = {}  # video id -> details


def get_term(code):
    lang = LANGUAGES.get(code, "en")
    if not USE_TRANSLATIONS or lang == "en":
        return KEYWORD
    return MANUAL_TRANSLATIONS.get(lang, KEYWORD)


def make_opts(code, flat=False):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "geo_bypass_country": code,
        "sleep_interval_requests": 2,
        "retries": 5,
    }
    if code in PROXIES:
        opts["proxy"] = PROXIES[code]
    if flat:
        opts["extract_flat"] = True
    return opts


def search_ids(code, term):
    query = f"ytsearch{RESULTS_PER_COUNTRY}:{term}"
    with yt_dlp.YoutubeDL(make_opts(code, flat=True)) as ydl:
        info = ydl.extract_info(query, download=False)
    time.sleep(DELAY_SECONDS)
    return [e["id"] for e in info.get("entries", []) if e.get("id")]


def read_transcript(folder, preferred_langs):
    """Read a downloaded subtitle file (json3) from the temp folder."""
    files = list(Path(folder).glob("*.json3"))
    if not files:
        return None

    def file_lang(p):
        return p.name.split(".")[-2]  # e.g. "abc123.en.json3" -> "en"

    chosen = None
    for lang in preferred_langs:
        chosen = next((p for p in files
                       if file_lang(p) == lang or file_lang(p).startswith(lang + "-")), None)
        if chosen:
            break
    chosen = chosen or files[0]

    try:
        data = json.loads(chosen.read_text(encoding="utf-8"))
        text = " ".join(
            seg.get("utf8", "")
            for ev in data.get("events", [])
            for seg in ev.get("segs", [])
        ).replace("\n", " ")
        return " ".join(text.split()) or None
    except Exception as e:
        print(f"  Could not read transcript: {e}")
        return None


def get_video(code, vid):
    if vid in video_cache:
        return video_cache[vid]
    url = f"https://www.youtube.com/watch?v={vid}"

    country_lang = LANGUAGES.get(code, "en").split("-")[0]
    wanted = list(dict.fromkeys([country_lang, "en"]))

    with tempfile.TemporaryDirectory() as tmp:
        opts = make_opts(code)
        if GET_TRANSCRIPTS:
            opts.update({
                "writesubtitles": True,        # manual captions
                "writeautomaticsub": True,     # auto-generated captions
                "subtitleslangs": [f"{l}.*" for l in wanted],
                "subtitlesformat": "json3",
                "sleep_interval_subtitles": DELAY_SECONDS,
                "outtmpl": str(Path(tmp) / "%(id)s.%(ext)s"),
            })
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=GET_TRANSCRIPTS)
        video_lang = info.get("language")
        langs = ([video_lang] if video_lang else []) + wanted
        transcript = read_transcript(tmp, langs) if GET_TRANSCRIPTS else None

    details = {
        "title": info.get("title"),
        "channel": info.get("uploader"),
        "url": url,
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "comments": info.get("comment_count"),
        "transcript": transcript,
    }
    video_cache[vid] = details
    return details


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else "N/A"


def main():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'YouTube search results for: "{KEYWORD}"\n')
        f.write("=" * 70 + "\n\n")

        for code, country in COUNTRIES.items():
            term = get_term(code)
            print(f"Searching {country} ({code})...")
            f.write(f"{'#' * 70}\n# {country} ({code})\n{'#' * 70}\n")
            f.write(f"  Search term: {term}\n\n")

            try:
                ids = search_ids(code, term)
            except Exception as e:
                f.write(f"  Search failed: {e}\n\n")
                continue

            for i, vid in enumerate(ids, 1):
                try:
                    v = get_video(code, vid)
                except Exception as e:
                    f.write(f"  {i}. [{vid}] failed: {e}\n\n")
                    continue
                f.write(f"  {i}. {v['title']}\n")
                f.write(f"     Channel:  {v['channel']}\n")
                f.write(f"     URL:      {v['url']}\n")
                f.write(f"     Views:    {fmt(v['views'])}\n")
                f.write(f"     Likes:    {fmt(v['likes'])}\n")
                f.write(f"     Comments: {fmt(v['comments'])}\n")
                if GET_TRANSCRIPTS:
                    f.write("     Transcript:\n")
                    if v["transcript"]:
                        f.write(textwrap.fill(v["transcript"], width=90,
                                              initial_indent="       ",
                                              subsequent_indent="       ") + "\n")
                    else:
                        f.write("       (not available)\n")
                f.write("\n")
                time.sleep(DELAY_SECONDS)
            f.flush()

    print(f"Done. Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()