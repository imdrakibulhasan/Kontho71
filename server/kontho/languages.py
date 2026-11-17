"""Languages exposed in the UI / API, with NLLB-200 codes for translation."""

# iso code -> (English name, native name, NLLB code)
LANGUAGES: dict[str, tuple[str, str, str]] = {
    "en": ("English", "English", "eng_Latn"),
    "bn": ("Bengali", "বাংলা", "ben_Beng"),
    "fr": ("French", "Français", "fra_Latn"),
    "hi": ("Hindi", "हिन्दी", "hin_Deva"),
    "ur": ("Urdu", "اردو", "urd_Arab"),
    "ar": ("Arabic", "العربية", "arb_Arab"),
    "es": ("Spanish", "Español", "spa_Latn"),
    "pt": ("Portuguese", "Português", "por_Latn"),
    "de": ("German", "Deutsch", "deu_Latn"),
    "it": ("Italian", "Italiano", "ita_Latn"),
    "nl": ("Dutch", "Nederlands", "nld_Latn"),
    "pl": ("Polish", "Polski", "pol_Latn"),
    "ru": ("Russian", "Русский", "rus_Cyrl"),
    "uk": ("Ukrainian", "Українська", "ukr_Cyrl"),
    "tr": ("Turkish", "Türkçe", "tur_Latn"),
    "fa": ("Persian", "فارسی", "pes_Arab"),
    "zh": ("Chinese", "中文", "zho_Hans"),
    "ja": ("Japanese", "日本語", "jpn_Jpan"),
    "ko": ("Korean", "한국어", "kor_Hang"),
    "id": ("Indonesian", "Bahasa Indonesia", "ind_Latn"),
    "ms": ("Malay", "Bahasa Melayu", "zsm_Latn"),
    "vi": ("Vietnamese", "Tiếng Việt", "vie_Latn"),
    "th": ("Thai", "ไทย", "tha_Thai"),
    "ta": ("Tamil", "தமிழ்", "tam_Taml"),
    "te": ("Telugu", "తెలుగు", "tel_Telu"),
    "mr": ("Marathi", "मराठी", "mar_Deva"),
    "gu": ("Gujarati", "ગુજરાતી", "guj_Gujr"),
    "pa": ("Punjabi", "ਪੰਜਾਬੀ", "pan_Guru"),
    "ne": ("Nepali", "नेपाली", "npi_Deva"),
    "sw": ("Swahili", "Kiswahili", "swh_Latn"),
    "sv": ("Swedish", "Svenska", "swe_Latn"),
    "da": ("Danish", "Dansk", "dan_Latn"),
    "fi": ("Finnish", "Suomi", "fin_Latn"),
    "no": ("Norwegian", "Norsk", "nob_Latn"),
    "cs": ("Czech", "Čeština", "ces_Latn"),
    "el": ("Greek", "Ελληνικά", "ell_Grek"),
    "he": ("Hebrew", "עברית", "heb_Hebr"),
    "ro": ("Romanian", "Română", "ron_Latn"),
    "hu": ("Hungarian", "Magyar", "hun_Latn"),
    "fil": ("Filipino", "Filipino", "tgl_Latn"),
}


def language_list() -> list[dict]:
    return [{"language_id": k, "name": v[0], "native_name": v[1]} for k, v in LANGUAGES.items()]


def nllb_code(lang: str) -> str:
    lang = (lang or "en").lower()
    if lang in LANGUAGES:
        return LANGUAGES[lang][2]
    if "_" in lang and len(lang) == 8:  # already an NLLB code
        return lang
    raise ValueError(f"Unsupported language for translation: {lang}")


def language_name(lang: str) -> str:
    return LANGUAGES.get((lang or "").lower(), (lang, lang, ""))[0]
