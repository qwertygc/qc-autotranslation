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
    """Process Markdown content line by line, preserving structure while translating text"""

    FENCE_RE = re.compile(r'^(\s*)(`{3,}|~{3,}).*$')
    TAB_RE = re.compile(r'^(\s*===\s+)"([^"]*)"\s*$')
    ADMONITION_RE = re.compile(r'^(\s*(?:!!!|\?\?\?)[+\-]?\s*)(\S+)(\s+"([^"]*)")?\s*$')
    HEADER_RE = re.compile(r'^(#{1,6}\s+)(.*)$')
    PREFIX_RE = re.compile(r'^(\s*)((?:[-*+]|\d+\.)\s+)+(.*)$')
    QUOTE_RE = re.compile(r'^(\s*(?:>\s*)+)(.*)$')
    IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]*)\)')
    LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')
    INLINE_CODE_RE = re.compile(r'`[^`\n]+`')
    HTML_TAG_RE = re.compile(r'</?[^>]+>')
    MKDOCS_ATTRS_RE = re.compile(r'\{\s*[.:][^}]*\}')
    ICON_SHORTCODE_RE = re.compile(r':[\w-]+:')
    BARE_URL_RE = re.compile(r'https?://\S+')
    TOKEN_RE = re.compile(
        r'(?P<image>!\[[^\]]*\]\([^)]*\))'
        r'|(?P<link>\[[^\]]*\]\([^)]*\))'
        r'|(?P<code>`[^`\n]+`)'
        r'|(?P<html></?[^>]+>)'
        r'|(?P<attrs>\{\s*[.:][^}]*\})'
        r'|(?P<icon>:[\w-]+:)'
        r'|(?P<url>https?://\S+)'
    )

    def process_file(self, input_path: Path, output_path: Path) -> int:
        """Process a single Markdown file and return count of translated segments"""
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.read().split('\n')

        translated_count = 0
        in_frontmatter = lines and lines[0].strip() == '---'
        in_code_block = False
        code_fence = None

        result_lines = []
        for index, line in enumerate(lines):
            if in_frontmatter:
                result_lines.append(line)
                if index > 0 and line.strip() == '---':
                    in_frontmatter = False
                continue

            fence_match = self.FENCE_RE.match(line)
            if fence_match:
                fence = fence_match.group(2)
                if not in_code_block:
                    in_code_block = True
                    code_fence = fence[0] * 3
                elif fence.startswith(code_fence[0]):
                    in_code_block = False
                    code_fence = None
                result_lines.append(line)
                continue

            if in_code_block:
                result_lines.append(line)
                continue

            processed, count = self.process_line(line)
            translated_count += count
            result_lines.append(processed)

        translated_content = '\n'.join(result_lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_content)

        return translated_count

    def process_line(self, line: str):
        """Translate a single Markdown line, returns (new_line, translated_count)"""
        if not line.strip():
            return line, 0

        indent_match = re.match(r'^(\s*)\S', line)
        indent = indent_match.group(1) if indent_match else ''
        body = line[len(indent):]

        stripped = body.strip()

        if stripped in ('---', '***', '___'):
            return line, 0

        tab_match = self.TAB_RE.match(body)
        if tab_match:
            translated = self._single_line(translate_text(tab_match.group(2)))
            new_body = f'{tab_match.group(1)}"{translated}"'
            return indent + new_body, 0 if translated == tab_match.group(2) else 1

        admonition_match = self.ADMONITION_RE.match(body)
        if admonition_match:
            if admonition_match.group(4) is None:
                return line, 0
            original = admonition_match.group(4)
            translated = self._single_line(translate_text(original))
            new_body = f'{admonition_match.group(1)}{admonition_match.group(2)} "{translated}"'
            return indent + new_body, 0 if translated == original else 1

        header_match = self.HEADER_RE.match(body)
        if header_match:
            translated, count = self.translate_inline(header_match.group(2))
            return indent + header_match.group(1) + translated, count

        quote_match = self.QUOTE_RE.match(body)
        if quote_match:
            inner, count = self.process_line(indent + quote_match.group(2))
            return indent + quote_match.group(1) + inner.lstrip(), count

        prefix_match = self.PREFIX_RE.match(body)
        if prefix_match:
            translated, count = self.translate_inline(prefix_match.group(3))
            new_body = prefix_match.group(1) + prefix_match.group(2) + translated
            return indent + new_body, count

        translated, count = self.translate_inline(body)
        return indent + translated, count

    def translate_inline(self, text: str):
        """Translate inline text; URLs, code, images, HTML and mkdocs attributes never reach the engine"""
        parts = []
        translated_count = 0
        last_pos = 0

        for match in self.TOKEN_RE.finditer(text):
            fragment = text[last_pos:match.start()]
            processed, count = self.translate_fragment(fragment)
            translated_count += count
            parts.append(processed)

            token = match.group(0)
            kind = match.lastgroup
            if kind in ('link', 'image'):
                parsed = self.IMAGE_RE.match(token) if kind == 'image' else self.LINK_RE.match(token)
                label, url = parsed.group(1), parsed.group(2)
                if label.strip():
                    translated_label, count = self.translate_inline(label)
                    translated_count += count
                    prefix = '!' if kind == 'image' else ''
                    token = f'{prefix}[{translated_label}]({url})'
            parts.append(token)
            last_pos = match.end()

        fragment = text[last_pos:]
        processed, count = self.translate_fragment(fragment)
        translated_count += count
        parts.append(processed)

        return ''.join(parts), translated_count

    def translate_fragment(self, fragment: str):
        """Translate a pure-text fragment, preserving leading and trailing whitespace"""
        if not fragment or not fragment.strip():
            return fragment, 0

        leading = fragment[:len(fragment) - len(fragment.lstrip())]
        trailing = fragment[len(fragment.rstrip()):]
        core = fragment.strip()

        translated = self._single_line(translate_text(core))
        if translated == core:
            return fragment, 0
        return leading + translated + trailing, 1

    @staticmethod
    def _single_line(text: str) -> str:
        return re.sub(r'\s*\n\s*', ' ', text).strip()

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
