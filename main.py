import json
import textwrap
import time
from pathlib import Path

import yt_dlp
from deep_translator import GoogleTranslator  # pip install deep-translator

# ---------- SETTINGS ----------
KEYWORD = "landslide"        # write this in English
RESULTS_PER_COUNTRY = 3
GET_TRANSCRIPTS = True
TRANSLATE_KEYWORD = True
COUNTRY_LIMIT = 3            # test with a few countries first; set to None for all
DELAY_SECONDS = 3            # pause between video requests
TRANSLATE_DELAY = 1          # pause between translation requests

# Files are saved next to the script
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "results.txt"
CACHE_FILE = BASE_DIR / "translations.json"

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

if COUNTRY_LIMIT:
    COUNTRIES = dict(list(COUNTRIES.items())[:COUNTRY_LIMIT])

video_cache = {}  # video id -> details


# ---------- TRANSLATION (saved to translations.json) ----------
translation_cache = {}
if CACHE_FILE.exists():
    try:
        saved = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if saved.get("keyword") == KEYWORD:  # only reuse if keyword is unchanged
            translation_cache = saved.get("translations", {})
    except Exception:
        pass


def save_cache():
    CACHE_FILE.write_text(
        json.dumps({"keyword": KEYWORD, "translations": translation_cache},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def translate_keyword(lang):
    if not TRANSLATE_KEYWORD or lang == "en":
        return KEYWORD
    if lang in translation_cache:
        return translation_cache[lang]

    for attempt in range(3):
        try:
            result = GoogleTranslator(source="en", target=lang).translate(KEYWORD)
            translation_cache[lang] = result
            save_cache()
            time.sleep(TRANSLATE_DELAY)
            return result
        except Exception as e:
            print(f"  Translation to '{lang}' failed: {e}")
            time.sleep(10 * (attempt + 1))

    return KEYWORD  # not cached, so the next run retries this language


# ---------- YOUTUBE ----------
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


def fetch_transcript(info, ydl):
    """Manual subs first, then auto captions; video's language, then English."""
    langs = [l for l in (info.get("language"), "en") if l]
    for source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for lang in langs:
            key = next((k for k in source if k == lang or k.startswith(lang + "-")), None)
            if not key:
                continue
            fmt = next((f for f in source[key] if f.get("ext") == "json3"), None)
            if not fmt:
                continue
            try:
                data = json.loads(ydl.urlopen(fmt["url"]).read().decode("utf-8"))
                text = " ".join(
                    seg.get("utf8", "")
                    for ev in data.get("events", [])
                    for seg in ev.get("segs", [])
                ).replace("\n", " ")
                time.sleep(DELAY_SECONDS)
                return " ".join(text.split())
            except Exception as e:
                print(f"  Transcript fetch failed: {e}")
                continue
    return None


def get_video(code, vid):
    if vid in video_cache:
        return video_cache[vid]
    url = f"https://www.youtube.com/watch?v={vid}"
    with yt_dlp.YoutubeDL(make_opts(code)) as ydl:
        info = ydl.extract_info(url, download=False)
        transcript = fetch_transcript(info, ydl) if GET_TRANSCRIPTS else None
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


# ---------- MAIN ----------
def main():
    # Translate everything first, separate from the YouTube searches
    if TRANSLATE_KEYWORD:
        print("Translating keyword...")
        for lang in sorted({LANGUAGES.get(c, "en") for c in COUNTRIES}):
            translate_keyword(lang)
        print("Translations done.\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'YouTube search results for: "{KEYWORD}"\n')
        f.write("=" * 70 + "\n\n")

        for code, country in COUNTRIES.items():
            term = translate_keyword(LANGUAGES.get(code, "en"))
            print(f"Searching {country} ({code}) for '{term}'...")
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