"""
Universal translation script for PO and TS files with DeepL and Argostranslate fallback
- Only translates entries with EMPTY target strings (msgstr="" or <translation></translation>)
- Automatically adds standard PO headers to ensure compatibility with Poedit

USAGE:
1. pip install requests polib beautifulsoup4 tqdm argostranslate
2. For Argostranslate: run once `argospm install translate-en_<LANG>` https://www.argosopentech.com/argospm/index/
3. Run: python translate.py --lang fr
"""

import argparse
import logging
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
parser = argparse.ArgumentParser(description='Translate PO/TS files using Argostranslate')
parser.add_argument('--lang', required=True, help='Target language code (e.g., fr, es, fa)')
parser.add_argument('--sleep', type=float, default=0.2, help='Delay between translations (seconds)')
args = parser.parse_args()

TARGET_LANG = args.lang
SLEEP_TIME = args.sleep
BASE_DIR = Path.cwd()

# File paths
PO_INPUT = BASE_DIR / f"{TARGET_LANG}.po"
PO_OUTPUT = BASE_DIR / f"{TARGET_LANG}_translated.po"
TS_INPUT = BASE_DIR / f"{TARGET_LANG}.ts"
TS_OUTPUT = BASE_DIR / f"{TARGET_LANG}_translated.ts"

# ======================
# ARGOSTRANSLATE SETUP
# ======================
argos_from_lang = None
argos_to_lang = None

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
            package.install_from_path(pkg.download)
            installed_languages = translate.get_installed_languages()
            from_lang = next(l for l in installed_languages if l.code == "en")
            to_lang = next(l for l in installed_languages if l.code == TARGET_LANG)

        argos_from_lang, argos_to_lang = from_lang, to_lang
        print(f"✓ Argostranslate ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"✗ Argostranslate init failed: {e}")
        exit(1)

# ======================
# TRANSLATION
# ======================
def translate_text(text: str) -> str:
    """Translate text using Argostranslate"""
    if not text or not text.strip():
        return text
    try:
        from argostranslate import translate
        return argos_from_lang.get_translation(argos_to_lang).translate(text)
    except Exception:
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
    header_fields = {
        "Project-Id-Version": "PACKAGE VERSION",
        "POT-Creation-Date": time.strftime("%Y-%m-%d %H:%M%z"),
        "PO-Revision-Date": "YEAR-MO-DA HO:MI+ZONE",
        "Last-Translator": f"Auto-translated via Argostranslate (EN -> {lang.upper()})",
        "Language-Team": f"{lang.upper()} <LL@li.org>",
        "Language": lang,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "X-Generator": "Argostranslate + Custom Script",
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
        # Normaliser msgid (supprimer \n inutiles en début/fin)
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
        print(f"  ✓ Merged {duplicates_merged} duplicates")
    print(f"  ✓ Translated {translated_count} empty strings (marked as fuzzy) -> {PO_OUTPUT.name}")
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

    print(f"  ✓ Translated {translated_count} empty strings (marked as unfinished) -> {TS_OUTPUT.name}")
    return translated_count

# ======================
# MAIN
# ======================
def main() -> None:
    print(f"\nTranslating empty strings to {TARGET_LANG.upper()} via Argostranslate")
    print("-" * 50)

    init_argos()
    total = process_po_file() + process_ts_file()
    print(f"\n✓ Done! {total} empty strings translated and marked for review.")

if __name__ == "__main__":
    main()
