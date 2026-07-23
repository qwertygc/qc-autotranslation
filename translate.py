"""
Universal translation script for PO and TS files with DeepL, Argostranslate, LINDAT, and Apertium support
- Translates entries with EMPTY target strings OR non-validated translations (fuzzy/unfinished)
- Automatically adds standard PO headers to ensure compatibility with Poedit
- Configuration via config.ini file

USAGE:
1. pip install -r requirements.txt
2. For Argostranslate: run once `argospm install translate-en_<LANG>` https://www.argosopentech.com/argospm/index/
3. Configure config.ini with your provider (argostranslate, deepl, lindat, or apertium) and deepl_key if needed
4. Run: python translate.py --lang fr
   Add --retranslate to force re-translation of ALL entries
   Add --skip-fuzzy to skip entries already marked as fuzzy
"""

import argparse
import configparser
import logging
import os
import time
from pathlib import Path
from typing import Optional

import polib
from bs4 import BeautifulSoup
from tqdm import tqdm

# Suppress Argostranslate warnings
logging.getLogger("argostranslate").setLevel(logging.ERROR)

# ======================
# CONFIGURATION
# ======================
parser = argparse.ArgumentParser(description='Translate PO/TS files using configured provider')
parser.add_argument('--lang', required=True, help='Target language code (e.g., fr, es, fa)')
parser.add_argument('--sleep', type=float, default=0.2, help='Delay between translations (seconds)')
parser.add_argument('--config', default='config.ini', help='Path to configuration file (default: config.ini)')
parser.add_argument('--retranslate', action='store_true', help='Re-translate ALL entries (including validated ones)')
parser.add_argument('--skip-fuzzy', action='store_true', help='Skip entries already marked as fuzzy')
args = parser.parse_args()

TARGET_LANG = args.lang
SLEEP_TIME = args.sleep
CONFIG_PATH = args.config
RETRANSLATE_ALL = args.retranslate
SKIP_FUZZY = args.skip_fuzzy
BASE_DIR = Path.cwd()

# File paths
PO_INPUT = BASE_DIR / f"{TARGET_LANG}.po"
PO_OUTPUT = BASE_DIR / f"{TARGET_LANG}_translated.po"
TS_INPUT = BASE_DIR / f"{TARGET_LANG}.ts"
TS_OUTPUT = BASE_DIR / f"{TARGET_LANG}_translated.ts"

# Load configuration
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Get configuration values with proper handling of empty strings
PROVIDER = config.get('translation', 'provider', fallback='argostranslate').strip().lower()
DEEPL_KEY = config.get('translation', 'deepl_key', fallback='').strip()
DEEPL_ENDPOINT = config.get('translation', 'deepl_endpoint', fallback='https://api-free.deepl.com/v2/translate').strip()
LINDAT_ENDPOINT = config.get('translation', 'lindat_endpoint', fallback='https://lindat.mff.cuni.cz/services/translation/api/v2').strip()
APERTIUM_ENDPOINT = config.get('translation', 'apertium_endpoint', fallback='https://apertium.org/apy/translate').strip()

# ======================
# LANGUAGE CODE MAPPING
# ======================
# Apertium uses 3-letter language codes, we need to map 2-letter codes
LANG_CODE_MAP = {
    'en': 'eng', 'es': 'spa', 'fr': 'fra', 'de': 'deu', 'it': 'ita', 'pt': 'por',
    'ca': 'cat', 'ru': 'rus', 'nl': 'nld', 'sv': 'swe', 'da': 'dan', 'no': 'nob',
    'pl': 'pol', 'uk': 'ukr', 'ro': 'ron', 'bg': 'bul', 'hr': 'hrv', 'sl': 'slv',
    'cs': 'ces', 'sk': 'slk', 'hu': 'hun', 'fi': 'fin', 'et': 'est', 'lv': 'lav',
    'lt': 'lit', 'el': 'ell', 'tr': 'tur', 'ar': 'ara', 'he': 'heb', 'hi': 'hin',
    'bn': 'ben', 'ja': 'jpn', 'ko': 'kor', 'zh': 'zho', 'th': 'tha', 'vi': 'vie'
}

def get_apertium_lang_code(lang_2letter: str) -> str:
    """Convert 2-letter language code to 3-letter Apertium code"""
    return LANG_CODE_MAP.get(lang_2letter.lower(), lang_2letter)

# ======================
# PROVIDER INITIALIZATION
# ======================
argos_from_lang = None
argos_to_lang = None
deepL_translator = None
lindat_session = None
apertium_session = None

def init_provider() -> None:
    """Initialize the selected translation provider"""
    global argos_from_lang, argos_to_lang, deepL_translator, lindat_session, apertium_session

    if PROVIDER == 'deepl':
        init_deepl()
    elif PROVIDER == 'lindat':
        init_lindat()
    elif PROVIDER == 'apertium':
        init_apertium()
    else:
        init_argos()

def init_argos() -> None:
    """Initialize Argostranslate with EN -> TARGET_LANG"""
    global argos_from_lang, argos_to_lang
    try:
        from argostranslate import package, translate

        installed_languages = translate.get_installed_languages()
        from_lang = next((l for l in installed_languages if l.code == "en"), None)
        to_lang = next((l for l in installed_languages if l.code == TARGET_LANG), None)

        if not from_lang or not to_lang:
            print(f"Installing EN -> {TARGET_LANG} models...")
            package.update_package_index()
            available = package.get_available_packages()
            pkg = next(p for p in available if p.from_code == "en" and p.to_code == TARGET_LANG)
            # Use install_package_for_language_pair which handles the download automatically
            package.install_package_for_language_pair("en", TARGET_LANG)
            # Reload installed languages
            installed_languages = translate.get_installed_languages()
            from_lang = next(l for l in installed_languages if l.code == "en")
            to_lang = next(l for l in installed_languages if l.code == TARGET_LANG)

        argos_from_lang, argos_to_lang = from_lang, to_lang
        print(f"\u2713 Argostranslate ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"\u2717 Argostranslate init failed: {e}")
        exit(1)

def init_deepl() -> None:
    """Initialize DeepL translator"""
    global deepL_translator
    if not DEEPL_KEY or DEEPL_KEY == 'None' or DEEPL_KEY == '':
        print("\u2717 DeepL API key is required in config.ini")
        exit(1)

    try:
        import deepl
        deepL_translator = deepl.Translator(DEEPL_KEY)
        print(f"\u2713 DeepL ready (EN -> {TARGET_LANG.upper()})")
    except deepl.exceptions.AuthorizationException:
        print("\u2717 DeepL API key is invalid")
        exit(1)
    except Exception as e:
        print(f"\u2717 DeepL init failed: {e}")
        exit(1)

def init_lindat() -> None:
    """Initialize LINDAT translation service"""
    global lindat_session
    try:
        import requests
        lindat_session = requests.Session()

        # Test the connection by getting available models
        models_url = f"{LINDAT_ENDPOINT}/models/"
        response = lindat_session.get(models_url)

        if response.status_code != 200:
            print(f"\u2717 LINDAT API connection failed with status {response.status_code}")
            exit(1)

        # Check if the model for EN -> TARGET_LANG exists
        model_name = f"en-{TARGET_LANG}"
        model_exists = model_name in response.text

        if not model_exists:
            print(f"\u26A0 Warning: Model {model_name} may not be available on LINDAT")
            print(f"   Available models: {response.text[:500]}...")

        print(f"\u2713 LINDAT ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"\u2717 LINDAT init failed: {e}")
        exit(1)

def init_apertium() -> None:
    """Initialize Apertium translation service"""
    global apertium_session
    try:
        import requests
        apertium_session = requests.Session()

        # Test the connection by listing available pairs
        list_url = "https://apertium.org/apy/listPairs"
        response = apertium_session.get(list_url, verify=False, timeout=10)

        if response.status_code != 200:
            print(f"\u2717 Apertium API connection failed with status {response.status_code}")
            exit(1)

        # Check if the pair for EN -> TARGET_LANG exists
        source_3letter = get_apertium_lang_code('en')
        target_3letter = get_apertium_lang_code(TARGET_LANG)
        pair_exists = f'"sourceLanguage": "{source_3letter}", "targetLanguage": "{target_3letter}"' in response.text

        if not pair_exists:
            print(f"\u26A0 Warning: Language pair {source_3letter}-{target_3letter} may not be available on Apertium")
            print(f"   You can check available pairs at: https://apertium.org/apy/listPairs")

        print(f"\u2713 Apertium ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"\u2717 Apertium init failed: {e}")
        exit(1)

# ======================
# TRANSLATION
# ======================
def translate_text(text: str) -> str:
    """Translate text using the configured provider"""
    if not text or not text.strip():
        return text

    try:
        if PROVIDER == 'deepl':
            result = deepL_translator.translate_text(text, target_lang=TARGET_LANG)
            return result.text
        elif PROVIDER == 'lindat':
            return translate_with_lindat(text)
        elif PROVIDER == 'apertium':
            return translate_with_apertium(text)
        else:
            from argostranslate import translate
            return argos_from_lang.get_translation(argos_to_lang).translate(text)
    except Exception as e:
        print(f"\u26A0 Translation error: {e}")
        return text

def translate_with_lindat(text: str) -> str:
    """Translate text using LINDAT API"""
    import requests

    model_name = f"en-{TARGET_LANG}"
    url = f"{LINDAT_ENDPOINT}/models/{model_name}"

    try:
        response = lindat_session.post(url, data={'input_text': text}, timeout=30)
        response.raise_for_status()
        # Strip whitespace and newlines from response
        result = response.text.strip()
        # Ensure proper UTF-8 encoding
        return result.encode('utf-8', 'ignore').decode('utf-8')
    except requests.exceptions.RequestException as e:
        # Try with source and target parameters as fallback
        try:
            url = f"{LINDAT_ENDPOINT}/languages/"
            response = lindat_session.post(url, data={
                'input_text': text,
                'src': 'en',
                'tgt': TARGET_LANG
            }, timeout=30)
            response.raise_for_status()
            result = response.text.strip()
            return result.encode('utf-8', 'ignore').decode('utf-8')
        except requests.exceptions.RequestException as e2:
            print(f"\u26A0 LINDAT translation error: {e2}")
            return text

def translate_with_apertium(text: str) -> str:
    """Translate text using Apertium API"""
    import requests
    import json

    source_3letter = get_apertium_lang_code('en')
    target_3letter = get_apertium_lang_code(TARGET_LANG)
    langpair = f"{source_3letter}|{target_3letter}"

    url = APERTIUM_ENDPOINT

    try:
        response = apertium_session.get(url, params={
            'langpair': langpair,
            'q': text
        }, verify=False, timeout=30)
        response.raise_for_status()

        # Parse JSON response
        data = json.loads(response.text)
        if data.get('responseStatus') == 200:
            translated_text = data.get('responseData', {}).get('translatedText', text)
            # Clean up the result
            return translated_text.strip()
        else:
            print(f"\u26A0 Apertium API error: {data.get('message', 'Unknown error')}")
            return text
    except requests.exceptions.RequestException as e:
        print(f"\u26A0 Apertium translation error: {e}")
        return text
    except json.JSONDecodeError as e:
        print(f"\u26A0 Apertium JSON decode error: {e}")
        return text

def should_translate_entry(entry) -> bool:
    """Check if an entry should be (re)translated"""
    if RETRANSLATE_ALL:
        return bool(entry.msgid and entry.msgid.strip())

    # Skip if entry is marked as fuzzy and we want to skip fuzzy entries
    if SKIP_FUZZY and "fuzzy" in entry.flags:
        return False

    # Translate if empty
    if not entry.msgstr or not entry.msgstr.strip():
        return bool(entry.msgid and entry.msgid.strip())

    # Re-translate if fuzzy (non-validated)
    if "fuzzy" in entry.flags:
        return bool(entry.msgid and entry.msgid.strip())

    return False

# ======================
# PO FILE PROCESSING
# ======================
def process_po_file() -> int:
    """Clean, deduplicate, and translate empty or non-validated strings in PO file"""
    if not PO_INPUT.exists():
        return 0

    po = polib.pofile(str(PO_INPUT))
    translated_count = 0
    duplicates_merged = 0

    # Separate header entry from regular entries
    regular_entries = []

    for entry in po:
        if entry.msgid == "":
            # Skip header entry - we'll recreate it properly
            continue
        regular_entries.append(entry)

    # Process regular entries for deduplication
    seen = {}
    for entry in regular_entries:
        # For msgid, we need to preserve the exact string including newlines
        # but strip leading/trailing whitespace for deduplication key
        original_msgid = entry.msgid

        # Create a normalized key for deduplication (strip whitespace)
        if original_msgid:
            norm_key = original_msgid.strip()
        else:
            norm_key = original_msgid

        # Keep the original msgid as-is (preserve formatting)
        cleaned_msgid = original_msgid

        # For msgstr, preserve the original as-is
        cleaned_msgstr = entry.msgstr

        # Handle duplicates - use the first occurrence and merge translations
        if norm_key in seen:
            existing = seen[norm_key]
            # If existing has no translation but current does, use current
            if not existing.msgstr and cleaned_msgstr:
                existing.msgstr = cleaned_msgstr
                existing.flags = entry.flags.copy()
                existing.occurrences = entry.occurrences.copy()
            duplicates_merged += 1
        else:
            # Create a new entry with original values (preserving formatting)
            new_entry = polib.POEntry(
                msgid=cleaned_msgid,
                msgstr=cleaned_msgstr,
                comment=entry.comment,
                tcomment=entry.tcomment,
                occurrences=entry.occurrences.copy(),
                flags=entry.flags.copy(),
            )
            seen[norm_key] = new_entry

    # Second pass: translate empty or non-validated strings
    entries_to_process = list(seen.values())
    for entry in tqdm(entries_to_process, desc=f"Processing {PO_INPUT.name}"):
        if entry.msgid and should_translate_entry(entry):
            # For translation, use the stripped msgid
            text = entry.msgid.strip() if entry.msgid else ""
            if text:
                new_translation = translate_text(text)
                if new_translation and new_translation != text:
                    entry.msgstr = new_translation
                    # Ensure fuzzy flag is set (but don't duplicate it)
                    if "fuzzy" not in entry.flags:
                        entry.flags.append("fuzzy")
                    translated_count += 1
                time.sleep(SLEEP_TIME)

    # Create a new PO file with processed entries
    new_po = polib.POFile()

    # Set metadata - this will create a proper header entry
    provider_name = "DeepL" if PROVIDER == 'deepl' else ("LINDAT" if PROVIDER == 'lindat' else ("Apertium" if PROVIDER == 'apertium' else "Argostranslate"))
    new_po.metadata = {
        "Project-Id-Version": "PACKAGE VERSION",
        "POT-Creation-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "PO-Revision-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "Last-Translator": f"Auto-translated via {provider_name} (EN -> {TARGET_LANG.upper()})",
        "Language-Team": f"{TARGET_LANG.upper()} <LL@li.org>",
        "Language": TARGET_LANG,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "X-Generator": f"{provider_name} + Custom Script",
    }

    # Add all processed entries
    for entry in entries_to_process:
        new_po.append(entry)

    new_po.save(str(PO_OUTPUT))

    if duplicates_merged:
        print(f"  \u2713 Merged {duplicates_merged} duplicates")
    print(f"  \u2713 Translated {translated_count} strings (marked as fuzzy) -> {PO_OUTPUT.name}")
    return translated_count

# ======================
# TS FILE PROCESSING
# ======================
def process_ts_file() -> int:
    """Translate empty or non-validated <translation> tags in TS file"""
    if not TS_INPUT.exists():
        return 0

    with open(TS_INPUT, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'xml')

    messages = soup.find_all('message')
    translated_count = 0

    for message in tqdm(messages, desc=f"Processing {TS_INPUT.name}"):
        source = message.find('source')
        translation = message.find('translation')

        if source and translation:
            source_text = source.string
            translation_text = translation.string if translation.string else ""

            # Check if we should (re)translate this entry
            should_translate = False

            if RETRANSLATE_ALL:
                should_translate = bool(source_text and source_text.strip())
            elif SKIP_FUZZY and message.get('type') == 'unfinished':
                # Skip if we want to skip unfinished entries
                should_translate = False
            else:
                # Translate if empty
                if not translation_text or not translation_text.strip():
                    should_translate = bool(source_text and source_text.strip())
                # Re-translate if unfinished (non-validated)
                elif message.get('type') == 'unfinished':
                    should_translate = bool(source_text and source_text.strip())

            if should_translate:
                text = source_text.strip()
                if text:
                    new_translation = translate_text(text)
                    if new_translation and new_translation != text:
                        translation.string = new_translation
                        message['type'] = 'unfinished'  # <-- MARQUE COMME UNFINISHED
                        translated_count += 1
                    time.sleep(SLEEP_TIME)

    with open(TS_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    print(f"  \u2713 Translated {translated_count} strings (marked as unfinished) -> {TS_OUTPUT.name}")
    return translated_count

# ======================
# MAIN
# ======================
def main() -> None:
    mode_description = "ALL entries" if RETRANSLATE_ALL else "empty and non-validated entries"
    print(f"\nTranslating {mode_description} to {TARGET_LANG.upper()} via {PROVIDER.upper()}")
    print("-" * 50)

    init_provider()
    total = process_po_file() + process_ts_file()
    print(f"\n\u2713 Done! {total} strings translated and marked for review.")

if __name__ == "__main__":
    main()
