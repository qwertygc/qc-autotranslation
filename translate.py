"""
Universal translation script for PO and TS files with DeepL and Argostranslate fallback

USAGE:
1. pip install requests polib beautifulsoup4 tqdm argostranslate
2. For Argostranslate: run once `argospm install translate-en_eu` (replace LANG with your target)
https://www.argosopentech.com/argospm/index/
3. Run: python translate.py --lang fa [--translator deepl|argos] [--deepl-key YOUR_KEY] [--fallback]

EXAMPLES:
python translate.py --lang fa --deepl-key YOUR_DEEPL_KEY
python translate.py --lang fr --translator argos
python translate.py --lang es --translator deepl --deepl-key YOUR_KEY --fallback
"""

import argparse
import os
import time
from tqdm import tqdm
import polib
from bs4 import BeautifulSoup

# Parse command line arguments
parser = argparse.ArgumentParser(description='Translate PO/TS files using DeepL or Argostranslate')
parser.add_argument('--lang', required=True, help='Target language code (e.g., fa, fr, es)')
parser.add_argument('--translator', default='deepl', choices=['deepl', 'argos'], help='Translator to use: deepl or argos (default: deepl)')
parser.add_argument('--deepl-key', help='DeepL API key (required if translator is deepl)')
parser.add_argument('--fallback', action='store_true', help='Enable automatic fallback to other translator if primary fails')
args = parser.parse_args()

# Configuration from arguments
TARGET_LANG = args.lang
TRANSLATOR = args.translator
DEEPL_API_KEY = args.deepl_key
FALLBACK_ENABLED = args.fallback

# Input/output filenames
PO_INPUT = f"{TARGET_LANG}.po"
PO_OUTPUT = f"{TARGET_LANG}_translated.po"
TS_INPUT = f"{TARGET_LANG}.ts"
TS_OUTPUT = f"{TARGET_LANG}_translated.ts"

# ======================
# ARGOSTRANSLATE INITIALIZATION
# ======================
argos_initialized = False
argos_from_lang = None
argos_to_lang = None

def init_argos():
    """Initialize Argostranslate for the target language"""
    global argos_initialized, argos_from_lang, argos_to_lang
    if argos_initialized:
        return

    try:
        from argostranslate import package, translate
        installed_languages = translate.get_installed_languages()
        from_lang = next((lang for lang in installed_languages if lang.code == "en"), None)
        to_lang = next((lang for lang in installed_languages if lang.code == TARGET_LANG), None)

        if not from_lang or not to_lang:
            print(f"Downloading Argostranslate models for English -> {TARGET_LANG}...")
            package.update_package_index()
            available_packages = package.get_available_packages()
            en_package = next(p for p in available_packages if p.from_code == "en" and p.to_code == TARGET_LANG)
            package.install_from_path(en_package.download_url)
            installed_languages = translate.get_installed_languages()
            from_lang = next(lang for lang in installed_languages if lang.code == "en")
            to_lang = next(lang for lang in installed_languages if lang.code == TARGET_LANG)

        argos_from_lang = from_lang
        argos_to_lang = to_lang
        argos_initialized = True
        print(f"Argostranslate ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"Failed to initialize Argostranslate: {e}")
        argos_initialized = False

# ======================
# TRANSLATION FUNCTIONS
# ======================

def translate_deepl(text: str) -> str:
    """Translate text using DeepL API"""
    if not text or not text.strip():
        return text

    if not DEEPL_API_KEY:
        print("DeepL API key is required for DeepL translator")
        return None

    import requests
    data = {
        "auth_key": DEEPL_API_KEY,
        "text": text,
        "target_lang": TARGET_LANG.upper(),
        "source_lang": "EN"
    }

    try:
        response = requests.post("https://api-free.deepl.com/v2/translate", data=data, timeout=10)
        response.raise_for_status()
        return response.json()["translations"][0]["text"]
    except Exception as e:
        print(f"DeepL failed for '{text[:30]}...': {str(e)[:50]}")
        return None

def translate_argos(text: str) -> str:
    """Translate text using Argostranslate (offline)"""
    if not text or not text.strip() or not argos_initialized:
        return text if text else ""

    try:
        from argostranslate import translate
        translation = argos_from_lang.get_translation(argos_to_lang)
        return translation.translate(text)
    except Exception as e:
        print(f"Argostranslate failed for '{text[:30]}...': {str(e)[:50]}")
        return None

def translate_text(text: str) -> str:
    """Main translation function with automatic fallback"""
    if not text or not text.strip():
        return text

    # Try primary translator
    if TRANSLATOR == "deepl":
        result = translate_deepl(text)
        if result is not None:
            return result
        if FALLBACK_ENABLED:
            print("   -> Falling back to Argostranslate...")
            init_argos()
            result = translate_argos(text)
            return result if result is not None else text
    elif TRANSLATOR == "argos":
        init_argos()
        result = translate_argos(text)
        if result is not None:
            return result
        if FALLBACK_ENABLED:
            print("   -> Falling back to DeepL...")
            result = translate_deepl(text)
            return result if result is not None else text

    return text

# ======================
# FILE PROCESSING FUNCTIONS
# ======================

def translate_po_file() -> int:
    """Translate a PO file"""
    if not os.path.exists(PO_INPUT):
        print(f"File not found: {PO_INPUT}")
        return 0

    po = polib.pofile(PO_INPUT)
    translated_count = 0

    for entry in tqdm(po, desc=f"Processing {PO_INPUT}"):
        if not entry.translated():
            new_translation = translate_text(entry.msgid)
            if new_translation != entry.msgid:
                entry.msgstr = new_translation
                translated_count += 1
            time.sleep(0.5)

    po.save(PO_OUTPUT)
    print(f"PO file translated: {translated_count} strings -> {PO_OUTPUT}")
    return translated_count

def translate_ts_file() -> int:
    """Translate a TS file"""
    if not os.path.exists(TS_INPUT):
        print(f"File not found: {TS_INPUT}")
        return 0

    with open(TS_INPUT, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'xml')

    messages = soup.find_all('message')
    translated_count = 0

    for message in tqdm(messages, desc=f"Processing {TS_INPUT}"):
        source = message.find('source')
        translation_tag = message.find('translation')

        if source and translation_tag and not translation_tag.string:
            text = source.string
            if text and text.strip():
                new_translation = translate_text(text)
                if new_translation != text:
                    translation_tag.string = new_translation
                    translated_count += 1
                time.sleep(0.5)

    with open(TS_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(str(soup))

    print(f"TS file translated: {translated_count} strings -> {TS_OUTPUT}")
    return translated_count

# ======================
# MAIN FUNCTION
# ======================

def main():
    print(f"\nTranslating to {TARGET_LANG.upper()} with {TRANSLATOR.upper()}")
    print(f"Input files: {PO_INPUT}, {TS_INPUT}")
    print(f"Output files: {PO_OUTPUT}, {TS_OUTPUT}")
    print(f"Fallback: {'ENABLED' if FALLBACK_ENABLED else 'DISABLED'}")
    print("="*50)

    # Initialize Argostranslate if needed
    if TRANSLATOR == "argos" or FALLBACK_ENABLED:
        init_argos()

    total_translated = 0

    # Translate PO file if exists
    total_translated += translate_po_file()

    # Translate TS file if exists
    total_translated += translate_ts_file()

    print(f"\nTranslation complete! {total_translated} strings translated.")

if __name__ == "__main__":
    main()
