"""
Markdown translation script using Argostranslate
- Translates text content in .md files while preserving structure (headers, links, code blocks, etc.)
- Configuration via config.ini file (same as translate.py)
- Outputs files in language-specific directories (e.g., pt/file.md)
- Preserves frontmatter YAML and metadata

USAGE:
1. pip install -r requirements.txt
2. For Argostranslate: run once `argospm install translate-en_<LANG>` https://www.argosopentech.com/argospm/index/
3. Configure config.ini with your provider (argostranslate recommended for offline use)
4. Run: python translate_md.py --input en/*.md --lang pt
"""

import argparse
import configparser
import logging
import re
from pathlib import Path
from typing import List, Optional

# Suppress Argostranslate warnings
logging.getLogger("argostranslate").setLevel(logging.ERROR)

# ======================
# LANGUAGE CODE MAPPING
# ======================
LANG_CODE_MAP = {
    'en': 'eng', 'es': 'spa', 'fr': 'fra', 'de': 'deu', 'it': 'ita', 'pt': 'por',
    'ca': 'cat', 'ru': 'rus', 'nl': 'nld', 'sv': 'swe', 'da': 'dan', 'no': 'nob',
    'pl': 'pol', 'uk': 'ukr', 'ro': 'ron', 'bg': 'bul', 'hr': 'hrv', 'sl': 'slv',
    'cs': 'ces', 'sk': 'slk', 'hu': 'hun', 'fi': 'fin', 'et': 'est', 'lv': 'lav',
    'lt': 'lit', 'el': 'ell', 'tr': 'tur', 'ar': 'ara', 'he': 'heb', 'hi': 'hin',
    'bn': 'ben', 'ja': 'jpn', 'ko': 'kor', 'zh': 'zho', 'th': 'tha', 'vi': 'vie'
}

# ======================
# CONFIGURATION
# ======================
parser = argparse.ArgumentParser(description='Translate Markdown files using configured provider')
parser.add_argument('--input', nargs='+', required=True, help='Input .md file(s) or pattern (e.g., en/*.md)')
parser.add_argument('--lang', required=True, help='Target language code (e.g., fr, es, pt)')
parser.add_argument('--output-dir', default=None, help='Output directory base (default: current directory)')
parser.add_argument('--config', default='config.ini', help='Path to configuration file (default: config.ini)')
parser.add_argument('--retranslate', action='store_true', help='Re-translate ALL text content')
args = parser.parse_args()

TARGET_LANG = args.lang
CONFIG_PATH = args.config
RETRANSLATE_ALL = args.retranslate
BASE_DIR = Path.cwd()

# Load configuration
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

# Get configuration values
PROVIDER = config.get('translation', 'provider', fallback='argostranslate').strip().lower()
DEEPL_KEY = config.get('translation', 'deepl_key', fallback='').strip()
DEEPL_ENDPOINT = config.get('translation', 'deepl_endpoint', fallback='https://api-free.deepl.com/v2/translate').strip()
LINDAT_ENDPOINT = config.get('translation', 'lindat_endpoint', fallback='https://lindat.mff.cuni.cz/services/translation/api/v2').strip()
APERTIUM_ENDPOINT = config.get('translation', 'apertium_endpoint', fallback='https://apertium.org/apy/translate').strip()

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

def init_argos():
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
            package.install_package_for_language_pair("en", TARGET_LANG)
            installed_languages = translate.get_installed_languages()
            from_lang = next(l for l in installed_languages if l.code == "en")
            to_lang = next(l for l in installed_languages if l.code == TARGET_LANG)

        argos_from_lang, argos_to_lang = from_lang, to_lang
        print(f"Argostranslate ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"Argostranslate init failed: {e}")
        exit(1)

def init_deepl():
    """Initialize DeepL translator"""
    global deepL_translator
    if not DEEPL_KEY or DEEPL_KEY == 'None' or DEEPL_KEY == '':
        print("DeepL API key is required in config.ini")
        exit(1)

    try:
        import deepl
        deepL_translator = deepl.Translator(DEEPL_KEY)
        print(f"DeepL ready (EN -> {TARGET_LANG.upper()})")
    except deepl.exceptions.AuthorizationException:
        print("DeepL API key is invalid")
        exit(1)
    except Exception as e:
        print(f"DeepL init failed: {e}")
        exit(1)

def init_lindat():
    """Initialize LINDAT translation service"""
    global lindat_session
    try:
        import requests
        lindat_session = requests.Session()
        models_url = f"{LINDAT_ENDPOINT}/models/"
        response = lindat_session.get(models_url)
        if response.status_code != 200:
            print(f"LINDAT API connection failed with status {response.status_code}")
            exit(1)
        print(f"LINDAT ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"LINDAT init failed: {e}")
        exit(1)

def init_apertium():
    """Initialize Apertium translation service"""
    global apertium_session
    try:
        import requests
        apertium_session = requests.Session()
        list_url = "https://apertium.org/apy/listPairs"
        response = apertium_session.get(list_url, verify=False, timeout=10)
        if response.status_code != 200:
            print(f"Apertium API connection failed with status {response.status_code}")
            exit(1)
        print(f"Apertium ready (EN -> {TARGET_LANG.upper()})")
    except Exception as e:
        print(f"Apertium init failed: {e}")
        exit(1)

def init_provider():
    """Initialize the selected translation provider"""
    if PROVIDER == 'deepl':
        init_deepl()
    elif PROVIDER == 'lindat':
        init_lindat()
    elif PROVIDER == 'apertium':
        init_apertium()
    else:
        init_argos()

# ======================
# TRANSLATION FUNCTIONS
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
        print(f"Translation error: {e}")
        return text

def translate_with_lindat(text: str) -> str:
    """Translate text using LINDAT API"""
    import requests
    model_name = f"en-{TARGET_LANG}"
    url = f"{LINDAT_ENDPOINT}/models/{model_name}"
    try:
        response = lindat_session.post(url, data={'input_text': text}, timeout=30)
        response.raise_for_status()
        return response.text.strip().encode('utf-8', 'ignore').decode('utf-8')
    except requests.exceptions.RequestException:
        try:
            url = f"{LINDAT_ENDPOINT}/languages/"
            response = lindat_session.post(url, data={'input_text': text, 'src': 'en', 'tgt': TARGET_LANG}, timeout=30)
            response.raise_for_status()
            return response.text.strip().encode('utf-8', 'ignore').decode('utf-8')
        except requests.exceptions.RequestException as e:
            print(f"LINDAT translation error: {e}")
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
        response = apertium_session.get(url, params={'langpair': langpair, 'q': text}, verify=False, timeout=30)
        response.raise_for_status()
        data = json.loads(response.text)
        if data.get('responseStatus') == 200:
            return data.get('responseData', {}).get('translatedText', text).strip()
        return text
    except Exception as e:
        print(f"Apertium translation error: {e}")
        return text

# ======================
# MARKDOWN PROCESSING
# ======================

class MarkdownProcessor:
    """Process Markdown content, preserving structure while translating text"""

    def __init__(self):
        # Compile all patterns once
        # Order matters: check for frontmatter first, then code blocks, then others
        self.patterns = [
            # Frontmatter YAML (between --- lines)
            (re.compile(r'^---\s*[\r\n]+(.*?)[\r\n]+---\s*[\r\n]+', re.MULTILINE | re.DOTALL), 'FRONTMATTER'),
            # Code blocks
            (re.compile(r'```[\s\S]*?```'), 'CODE_BLOCK'),
            # HTML tags
            (re.compile(r'<[^>]+>'), 'HTML'),
            # Horizontal rules
            (re.compile(r'^(---|\*\*\*|___)\s*$', re.MULTILINE), 'HR'),
            # Images
            (re.compile(r'!\[([^\]]+)\]\(([^)]+)\)'), 'IMAGE'),
            # Links
            (re.compile(r'\[([^\]]+)\]\(([^)]+)\)'), 'LINK'),
            # Headers (must be before inline code to avoid conflicts)
            (re.compile(r'^(#{1,6})\s*(.*)', re.MULTILINE), 'HEADER'),
            # Lists
            (re.compile(r'^(\s*[-*+]|\d+\.)\s+(.*)', re.MULTILINE), 'LIST'),
            # Blockquotes
            (re.compile(r'^(\s*>\s*)(.*)', re.MULTILINE), 'BLOCKQUOTE'),
            # Inline code (last to avoid conflicts with other patterns)
            (re.compile(r'`([^`\n]+)`'), 'INLINE_CODE'),
        ]

    def process_file(self, input_path: Path, output_path: Path) -> int:
        """Process a single Markdown file and return count of translated segments"""
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all matches for all patterns
        all_matches = []
        for pattern, elem_type in self.patterns:
            for match in pattern.finditer(content):
                all_matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'type': elem_type,
                    'full_match': match.group(0),
                    'groups': match.groups()
                })

        # Sort matches by position
        all_matches.sort(key=lambda x: x['start'])

        # Process the content in order
        result_parts = []
        last_pos = 0
        translated_count = 0

        for match in all_matches:
            # Add text before this match
            text_before = content[last_pos:match['start']]
            if text_before and text_before.strip():
                translated = translate_text(text_before)
                if translated != text_before:
                    translated_count += 1
                result_parts.append(translated)
            else:
                result_parts.append(text_before)

            # Process the matched element
            elem_type = match['type']
            if elem_type in ['CODE_BLOCK', 'INLINE_CODE', 'HTML', 'HR', 'FRONTMATTER']:
                # Don't translate these elements
                result_parts.append(match['full_match'])
            elif elem_type == 'LINK':
                link_text, url = match['groups']
                translated_text = translate_text(link_text)
                if translated_text != link_text:
                    translated_count += 1
                result_parts.append(f'[{translated_text}]({url})')
            elif elem_type == 'IMAGE':
                alt_text, url = match['groups']
                translated_alt = translate_text(alt_text)
                if translated_alt != alt_text:
                    translated_count += 1
                result_parts.append(f'![{translated_alt}]({url})')
            elif elem_type == 'HEADER':
                hashes, text = match['groups']
                # Preserve header structure and spacing
                translated_text = translate_text(text.strip())
                if translated_text != text.strip():
                    translated_count += 1
                # Add newline after header if it was followed by text
                result_parts.append(f'{hashes} {translated_text.strip()}')
            elif elem_type == 'LIST':
                prefix, text = match['groups']
                translated_text = translate_text(text)
                if translated_text != text:
                    translated_count += 1
                result_parts.append(f'{prefix} {translated_text}')
            elif elem_type == 'BLOCKQUOTE':
                prefix, text = match['groups']
                translated_text = translate_text(text)
                if translated_text != text:
                    translated_count += 1
                result_parts.append(f'{prefix}{translated_text}')

            last_pos = match['end']

        # Add remaining text after last match
        remaining_text = content[last_pos:]
        if remaining_text and remaining_text.strip():
            translated = translate_text(remaining_text)
            if translated != remaining_text:
                translated_count += 1
            result_parts.append(translated)
        else:
            result_parts.append(remaining_text)

        # Join all parts
        translated_content = ''.join(result_parts)

        # Write result
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)

        return translated_count

# ======================
# FILE PROCESSING
# ======================
def expand_file_patterns(patterns: List[str]) -> List[Path]:
    """Expand file patterns (like en/*.md) to actual file paths"""
    files = []
    for pattern in patterns:
        if '*' in pattern or '?' in pattern:
            matches = list(Path('.').glob(pattern))
            files.extend(matches)
        else:
            file_path = Path(pattern)
            if file_path.exists():
                files.append(file_path)
            else:
                print(f"Warning: File not found: {pattern}")
    return files

def get_output_path(input_file: Path, base_output_dir: Optional[Path] = None) -> Path:
    """Generate output path in language-specific directory structure"""
    if base_output_dir:
        lang_dir = base_output_dir / TARGET_LANG
    else:
        relative_path = input_file.parent.relative_to(BASE_DIR) if input_file.parent != BASE_DIR else Path('.')
        lang_dir = BASE_DIR / TARGET_LANG / relative_path

    lang_dir.mkdir(parents=True, exist_ok=True)
    return lang_dir / input_file.name

def process_files():
    """Process all input files"""
    input_files = expand_file_patterns(args.input)

    if not input_files:
        print("No input files found matching the specified patterns.")
        return

    base_output_dir = Path(args.output_dir) if args.output_dir else BASE_DIR

    init_provider()
    processor = MarkdownProcessor()
    total_translated = 0

    for input_file in input_files:
        if input_file.suffix.lower() != '.md':
            print(f"Skipping non-Markdown file: {input_file}")
            continue

        output_path = get_output_path(input_file, base_output_dir)

        print(f"Processing: {input_file} -> {output_path.relative_to(BASE_DIR)}")

        try:
            count = processor.process_file(input_file, output_path)
            total_translated += count
            print(f"  Translated {count} segments")
        except Exception as e:
            print(f"  Error processing {input_file.name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nDone! Translated {total_translated} segments across {len(input_files)} files.")
    print(f"Output directory: {base_output_dir / TARGET_LANG}")

if __name__ == "__main__":
    process_files()
