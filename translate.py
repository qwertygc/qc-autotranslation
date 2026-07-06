"""
Universal translation script for PO and TS files with DeepL and Argostranslate support
- Only translates entries with EMPTY target strings (msgstr="" or <translation></translation>)
- Automatically adds standard PO headers to ensure compatibility with Poedit
- Configuration via config.ini file

USAGE:
1. pip install -r requirements.txt
2. For Argostranslate: run once `argospm install translate-en_<LANG>` https://www.argosopentech.com/argospm/index/
3. Configure config.ini with your provider (argostranslate or deepl) and deepl_key if needed
4. Run: python translate.py --lang fr
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
args = parser.parse_args()

TARGET_LANG = args.lang
SLEEP_TIME = args.sleep
CONFIG_PATH = args.config
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

# ======================
# PROVIDER INITIALIZATION
# ======================
argos_from_lang = None
argos_to_lang = None
deepL_translator = None

def init_provider() -> None:
    """Initialize the selected translation provider"""
    global argos_from_lang, argos_to_lang, deepL_translator
    
    if PROVIDER == 'deepl':
        init_deepl()
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
        else:
            from argostranslate import translate
            return argos_from_lang.get_translation(argos_to_lang).translate(text)
    except Exception as e:
        print(f"\u26A0 Translation error: {e}")
        return text

# ======================
# PO FILE HEADERS
# ======================
def add_po_headers(po: polib.POFile, lang: str) -> None:
    """Add standard PO headers to ensure Poedit compatibility"""
    # Check if the header entry already exists
    header_entry = None
    for entry in po:
        if not entry.msgid:  # Header entry has empty msgid
            header_entry = entry
            break

    if header_entry is None:
        # Create a new header entry
        header_entry = polib.POEntry(
            msgid="",
            msgstr="",
            comment="",
            tcomment="",
            occurrences=[],
            flags=[],
        )
        po.insert(0, header_entry)

    # Add or update header fields
    # Ensure these fields are present in the header
    provider_name = "DeepL" if PROVIDER == 'deepl' else "Argostranslate"
    header_fields = {
        "Project-Id-Version": "PACKAGE VERSION",
        "POT-Creation-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "PO-Revision-Date": "YEAR-MO-DA HO:MI+ZONE",
        "Last-Translator": f"Auto-translated via {provider_name} (EN -> {lang.upper()})",
        "Language-Team": f"{lang.upper()} <LL@li.org>",
        "Language": lang,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "X-Generator": f"{provider_name} + Custom Script",
    }

    # Build the msgstr with all header fields
    header_lines = []
    for key, value in header_fields.items():
        header_lines.append(f"{key}: {value}")

    header_entry.msgstr = "\n".join(header_lines) + "\n"

# ======================
# PO FILE PROCESSING
# ======================
def process_po_file() -> int:
    """Clean, deduplicate, and translate empty strings in PO file"""
    if not PO_INPUT.exists():
        return 0

    po = polib.pofile(str(PO_INPUT))
    translated_count = 0
    seen = {}
    duplicates_merged = 0

    # First pass: clean and deduplicate
    for entry in po:
        # Normaliser msgid (supprimer \n inutiles en d	but/fin)
        if entry.msgid:
            entry.msgid = entry.msgid.strip()

        # Normaliser msgstr (supprimer \n inutiles)
        if entry.msgstr:
            entry.msgstr = entry.msgstr.strip()

        # Handle duplicates
        if entry.msgid in seen:
            existing = seen[entry.msgid]
            if not existing.msgstr and entry.msgstr:
                existing.msgstr = entry.msgstr
            duplicates_merged += 1
        else:
            seen[entry.msgid] = entry

    # Second pass: translate empty strings
    for entry in tqdm(seen.values(), desc=f"Processing {PO_INPUT.name}"):
        if entry.msgstr == "" and entry.msgid:
            text = entry.msgid
            if text:
                new_translation = translate_text(text)
                if new_translation and new_translation != text:
                    entry.msgstr = new_translation
                    entry.flags.append("fuzzy")
                    translated_count += 1
                time.sleep(SLEEP_TIME)

    # Create a new PO file with processed entries
    new_po = polib.POFile()
    for entry in seen.values():
        new_po.append(entry)

    # Add headers to ensure Poedit compatibility
    add_po_headers(new_po, TARGET_LANG)

    new_po.save(str(PO_OUTPUT))

    if duplicates_merged:
        print(f"  \u2713 Merged {duplicates_merged} duplicates")
    print(f"  \u2713 Translated {translated_count} empty strings (marked as fuzzy) -> {PO_OUTPUT.name}")
    return translated_count

# ======================
# TS FILE PROCESSING
# ======================
def process_ts_file() -> int:
    """Translate empty <translation> tags in TS file"""
    if not TS_INPUT.exists():
        return 0

    with open(TS_INPUT, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'xml')

    messages = soup.find_all('message')
    translated_count = 0

    for message in tqdm(messages, desc=f"Processing {TS_INPUT.name}"):
        source = message.find('source')
        translation = message.find('translation')

        if source and translation and (not translation.string or not translation.string.strip()):
            text = source.string
            if text and text.strip():
                new_translation = translate_text(text.strip())
                if new_translation and new_translation != text.strip():
                    translation.string = new_translation
                    message['type'] = 'unfinished'  # <-- MARQUE COMME UNFINISHED
                    translated_count += 1
                time.sleep(SLEEP_TIME)

    with open(TS_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    print(f"  \u2713 Translated {translated_count} empty strings (marked as unfinished) -> {TS_OUTPUT.name}")
    return translated_count

# ======================
# MAIN
# ======================
def main() -> None:
    print(f"\nTranslating empty strings to {TARGET_LANG.upper()} via {PROVIDER.upper()}")
    print("-" * 50)

    init_provider()
    total = process_po_file() + process_ts_file()
    print(f"\n\u2713 Done! {total} empty strings translated and marked for review.")

if __name__ == "__main__":
    main()
