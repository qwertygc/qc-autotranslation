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
