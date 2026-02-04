#!/usr/bin/env python3
"""
Ground Truth vs. System Result Data Validation Script

Compares pension fund data from a Hebrew PDF report (Ground Truth) against
raw data from XML files (System Result) to identify discrepancies.

Categories:
- Pension Funds (PensiaNet.xml): מקיפה (Comprehensive), כללית (General)
- Executive Insurance (hevrot.xml): By issuance year (2004+, 1992-2003, 1990-1991)

Usage:
    python validate_pension_data.py [--pdf PATH] [--xml-pension PATH] [--xml-insurance PATH]

Requirements:
    pip install pdfplumber pandas beautifulsoup4 lxml thefuzz python-Levenshtein
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Required libraries
import pandas as pd
from bs4 import BeautifulSoup

# Optional: thefuzz for fuzzy matching (falls back to exact matching)
try:
    from thefuzz import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("⚠️  thefuzz not available - using exact matching only")

# PDF handling: try pdfplumber first, fallback to PyPDF2
PDF_LIBRARY = None
pdfplumber = None
pypdf = None
PyPDF2 = None

try:
    import pdfplumber as _pdfplumber
    pdfplumber = _pdfplumber
    PDF_LIBRARY = 'pdfplumber'
except (ImportError, Exception):
    try:
        import pypdf as _pypdf
        pypdf = _pypdf
        PDF_LIBRARY = 'pypdf'
    except (ImportError, Exception):
        try:
            import PyPDF2 as _PyPDF2
            PyPDF2 = _PyPDF2
            PDF_LIBRARY = 'pypdf2'
        except (ImportError, Exception):
            print("⚠️  No PDF library available. Install: pip install pdfplumber")
            print("    Fallback options: pip install pypdf or pip install PyPDF2")


# =============================================================================
# CONFIGURATION
# =============================================================================

FUZZY_MATCH_THRESHOLD = 85  # Minimum similarity score for name matching
VALUE_TOLERANCE = 0.05  # Tolerance for numeric comparison (handles rounding)

# Category definitions
PENSION_CATEGORIES = {
    'comprehensive': {
        'hebrew': 'קרן פנסיה מקיפה',
        'keywords': ['מקיפה'],
        'xml_tag': 'SUG_KRN'
    },
    'general': {
        'hebrew': 'קרן פנסיה כללית',
        'keywords': ['כללית'],
        'xml_tag': 'SUG_KRN'
    }
}

INSURANCE_CATEGORIES = {
    '2004_onwards': {
        'hebrew': 'משנת 2004 ואילך',
        'patterns': [r'2004', r'מ[-\s]*2004'],
        'years': (2004, 9999)
    },
    '1992_2003': {
        'hebrew': 'משנת 1992 - 2003',
        'patterns': [r'1992.*2003', r'1992[-\s]+2003'],
        'years': (1992, 2003)
    },
    '1990_1991': {
        'hebrew': 'משנת 1990 - 1991',
        'patterns': [r'1990.*1991', r'1990[-\s]+1991'],
        'years': (1990, 1991)
    }
}

# XML field mappings for different sources
PENSION_XML_FIELDS = {
    'name': ['SHM_KRN', 'SHEM_GUF', 'FUND_NAME'],
    'category_tag': ['SUG_KRN', 'SIVUG'],
    'yield_12m': ['TSUA_MITZ_LE_TKUFA', 'TSUA_NOMINALIT_BRUTO_12_HODASHIM', 'YEAR_TO_DATE_YIELD'],
    'yield_3y': ['TSUA_SHNATIT_MEMUZAAT_3_SHANIM', 'AVG_ANNUAL_YIELD_3_YRS'],
    'yield_5y': ['TSUA_SHNATIT_MEMUZAAT_5_SHANIM', 'AVG_ANNUAL_YIELD_5_YRS'],
}

INSURANCE_XML_FIELDS = {
    'name': ['SHEM_GUF', 'SHM_KRN', 'FUND_NAME'],
    'issuance_period': ['TKUFAT_HAKAMA', 'TKUFA'],
    'yield_12m': ['TSUA_NOMINALIT_BRUTO_12_HODASHIM', 'TSUA_MITZ_LE_TKUFA', 'YEAR_TO_DATE_YIELD'],
    'yield_3y': ['TSUA_SHNATIT_MEMUZAAT_3_SHANIM', 'AVG_ANNUAL_YIELD_3_YRS'],
    'yield_5y': ['TSUA_SHNATIT_MEMUZAAT_5_SHANIM', 'AVG_ANNUAL_YIELD_5_YRS'],
}

# PDF column patterns (Hebrew)
PDF_COLUMN_PATTERNS = {
    'name': [r'שם\s*קרן', r'שם\s*הקרן', r'שם\s*המוצר', r'קרן', r'מוצר'],
    'yield_12m': [r'תשואה\s*12', r'תשואה\s*שנתית', r'12\s*חודשים', r'שנה\s*אחרונה'],
    'yield_3y': [r'תשואה\s*3', r'3\s*שנים', r'ממוצע\s*3'],
    'yield_5y': [r'תשואה\s*5', r'5\s*שנים', r'ממוצע\s*5'],
}


# =============================================================================
# HEBREW TEXT UTILITIES
# =============================================================================

def is_hebrew(text: str) -> bool:
    """Check if text contains Hebrew characters."""
    if not text:
        return False
    hebrew_pattern = re.compile(r'[\u0590-\u05FF]')
    return bool(hebrew_pattern.search(text))


def reverse_hebrew_word(word: str) -> str:
    """Reverse a Hebrew word that was extracted backwards."""
    if not word or not is_hebrew(word):
        return word
    return word[::-1]


def fix_hebrew_text(text: str) -> str:
    """
    Fix Hebrew text that may have been extracted in reverse order.
    """
    if not text or not is_hebrew(text):
        return text

    # Common Hebrew pension fund keywords (correct orientation)
    known_words = [
        'מנורה', 'מבטחים', 'פנסיה', 'הראל', 'מיטב', 'אלטשולר', 'שחם',
        'כלל', 'הפניקס', 'מגדל', 'איילון', 'ביטוח', 'גמל', 'קרן',
        'מניות', 'אג"ח', 'כללי', 'משולב', 'סחיר', 'חיסכון',
        'מקיפה', 'כללית', 'משנת', 'ואילך'
    ]

    text_lower = text.strip()
    reversed_text = text_lower[::-1]

    # Count matches in original vs reversed
    original_matches = sum(1 for word in known_words if word in text_lower)
    reversed_matches = sum(1 for word in known_words if word in reversed_text)

    if reversed_matches > original_matches:
        return reversed_text

    return text


def clean_hebrew_string(text: str) -> str:
    """Clean and normalize Hebrew string for comparison."""
    if not text:
        return ""

    text = fix_hebrew_text(str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*(בע"מ|בעמ|ltd\.?|inc\.?)\s*', '', text, flags=re.IGNORECASE)

    return text


# =============================================================================
# NUMERIC UTILITIES
# =============================================================================

def parse_numeric_value(value) -> Optional[float]:
    """Parse numeric value from various formats."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    text = text.replace('%', '').strip()
    text = re.sub(r'[^\d.\-,]', '', text)

    if ',' in text and '.' not in text:
        text = text.replace(',', '.')

    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def normalize_percentage(value: Optional[float]) -> Optional[float]:
    """Normalize percentage values for comparison."""
    if value is None:
        return None

    # If value is very small (< 1), it's likely in decimal form
    if abs(value) < 1 and value != 0:
        return value * 100

    return value


def values_match(val1: Optional[float], val2: Optional[float], tolerance: float = VALUE_TOLERANCE) -> bool:
    """Check if two values match within tolerance."""
    if val1 is None and val2 is None:
        return True
    if val1 is None or val2 is None:
        return False

    norm1 = normalize_percentage(val1)
    norm2 = normalize_percentage(val2)

    if norm1 is None or norm2 is None:
        return False

    return abs(norm1 - norm2) <= tolerance


# =============================================================================
# CATEGORY CLASSIFICATION
# =============================================================================

def classify_pension_fund(name: str, category_value: str = None) -> str:
    """
    Classify a pension fund as comprehensive (מקיפה) or general (כללית).

    Args:
        name: Fund name
        category_value: Value from SUG_KRN tag if available

    Returns:
        Category key ('comprehensive', 'general', or 'unknown')
    """
    text_to_check = f"{name} {category_value or ''}".lower()

    # Check for comprehensive (מקיפה)
    if 'מקיפה' in text_to_check:
        return 'comprehensive'

    # Check for general (כללית)
    if 'כללית' in text_to_check:
        return 'general'

    return 'unknown'


def classify_insurance_period(tkufat_hakama: str) -> str:
    """
    Classify insurance fund by issuance period.

    Args:
        tkufat_hakama: Value from TKUFAT_HAKAMA tag

    Returns:
        Category key ('2004_onwards', '1992_2003', '1990_1991', or 'unknown')
    """
    if not tkufat_hakama:
        return 'unknown'

    text = str(tkufat_hakama)

    # Check for 2004 onwards
    if '2004' in text:
        return '2004_onwards'

    # Check for 1992-2003
    if '1992' in text and '2003' in text:
        return '1992_2003'

    # Check for 1990-1991
    if '1990' in text and '1991' in text:
        return '1990_1991'

    # Try to extract year and classify
    year_match = re.search(r'(\d{4})', text)
    if year_match:
        year = int(year_match.group(1))
        if year >= 2004:
            return '2004_onwards'
        elif 1992 <= year <= 2003:
            return '1992_2003'
        elif 1990 <= year <= 1991:
            return '1990_1991'

    return 'unknown'


def get_category_hebrew(category_type: str, category_key: str) -> str:
    """Get Hebrew label for a category."""
    if category_type == 'pension':
        return PENSION_CATEGORIES.get(category_key, {}).get('hebrew', category_key)
    elif category_type == 'insurance':
        return INSURANCE_CATEGORIES.get(category_key, {}).get('hebrew', category_key)
    return category_key


# =============================================================================
# XML PARSING
# =============================================================================

def extract_xml_field(record, field_names: List[str]) -> Optional[str]:
    """Extract value from XML record trying multiple possible tag names."""
    for field in field_names:
        element = record.find(field)
        if element and element.text:
            return element.text.strip()
    return None


def parse_pension_xml(filepath: Path) -> pd.DataFrame:
    """
    Parse PensiaNet.xml and extract pension fund data with categories.

    Args:
        filepath: Path to PensiaNet.xml

    Returns:
        DataFrame with columns: Fund_Name, Category, Category_Hebrew, Yield_12M, Yield_3Y, Yield_5Y
    """
    print(f"  Parsing pension funds: {filepath.name}")

    if not filepath.exists():
        print(f"    ⚠️  File not found: {filepath}")
        return pd.DataFrame()

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'lxml-xml')

    # Find all fund records
    records = soup.find_all(['FUND', 'KEREN', 'RECORD', 'ROW', 'ITEM'])
    if not records:
        # Try to find repeating elements
        all_tags = [tag.name for tag in soup.find_all()]
        tag_counts = pd.Series(all_tags).value_counts()
        for tag_name in tag_counts[tag_counts > 5].index:
            records = soup.find_all(tag_name)
            if len(records) > 5:
                break

    data = []
    for record in records:
        # Extract name
        name = extract_xml_field(record, PENSION_XML_FIELDS['name'])
        if not name:
            continue

        name = clean_hebrew_string(name)

        # Get category tag value
        category_value = extract_xml_field(record, PENSION_XML_FIELDS['category_tag'])

        # Classify the fund
        category = classify_pension_fund(name, category_value)

        # Skip unknown categories
        if category == 'unknown':
            continue

        # Extract yields
        yield_12m = parse_numeric_value(extract_xml_field(record, PENSION_XML_FIELDS['yield_12m']))
        yield_3y = parse_numeric_value(extract_xml_field(record, PENSION_XML_FIELDS['yield_3y']))
        yield_5y = parse_numeric_value(extract_xml_field(record, PENSION_XML_FIELDS['yield_5y']))

        data.append({
            'Fund_Name': name,
            'Fund_Type': 'pension',
            'Category': category,
            'Category_Hebrew': get_category_hebrew('pension', category),
            'Yield_12M': yield_12m,
            'Yield_3Y': yield_3y,
            'Yield_5Y': yield_5y,
            'Source': filepath.name
        })

    df = pd.DataFrame(data)

    if not df.empty:
        # Count by category
        category_counts = df['Category_Hebrew'].value_counts()
        for cat, count in category_counts.items():
            print(f"    {cat}: {count} funds")

    print(f"    ✓ Found {len(df)} pension funds")
    return df


def parse_insurance_xml(filepath: Path) -> pd.DataFrame:
    """
    Parse hevrot.xml and extract insurance fund data with categories.

    Args:
        filepath: Path to hevrot.xml

    Returns:
        DataFrame with columns: Fund_Name, Category, Category_Hebrew, Yield_12M, Yield_3Y, Yield_5Y
    """
    print(f"  Parsing insurance funds: {filepath.name}")

    if not filepath.exists():
        print(f"    ⚠️  File not found: {filepath}")
        return pd.DataFrame()

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'lxml-xml')

    # Find all fund records
    records = soup.find_all(['FUND', 'HEVRA', 'RECORD', 'ROW', 'ITEM'])
    if not records:
        all_tags = [tag.name for tag in soup.find_all()]
        tag_counts = pd.Series(all_tags).value_counts()
        for tag_name in tag_counts[tag_counts > 5].index:
            records = soup.find_all(tag_name)
            if len(records) > 5:
                break

    data = []
    for record in records:
        # Extract name
        name = extract_xml_field(record, INSURANCE_XML_FIELDS['name'])
        if not name:
            continue

        name = clean_hebrew_string(name)

        # Get issuance period
        tkufat_hakama = extract_xml_field(record, INSURANCE_XML_FIELDS['issuance_period'])

        # Classify by period
        category = classify_insurance_period(tkufat_hakama)

        # Skip unknown categories
        if category == 'unknown':
            continue

        # Extract yields
        yield_12m = parse_numeric_value(extract_xml_field(record, INSURANCE_XML_FIELDS['yield_12m']))
        yield_3y = parse_numeric_value(extract_xml_field(record, INSURANCE_XML_FIELDS['yield_3y']))
        yield_5y = parse_numeric_value(extract_xml_field(record, INSURANCE_XML_FIELDS['yield_5y']))

        data.append({
            'Fund_Name': name,
            'Fund_Type': 'insurance',
            'Category': category,
            'Category_Hebrew': get_category_hebrew('insurance', category),
            'Yield_12M': yield_12m,
            'Yield_3Y': yield_3y,
            'Yield_5Y': yield_5y,
            'Source': filepath.name
        })

    df = pd.DataFrame(data)

    if not df.empty:
        category_counts = df['Category_Hebrew'].value_counts()
        for cat, count in category_counts.items():
            print(f"    {cat}: {count} funds")

    print(f"    ✓ Found {len(df)} insurance funds")
    return df


def load_all_xml_data(pension_path: Path, insurance_path: Path) -> pd.DataFrame:
    """Load and combine data from both XML files."""
    print("\n📄 Step 1: Parsing XML files...")

    pension_df = parse_pension_xml(pension_path)
    insurance_df = parse_insurance_xml(insurance_path)

    # Combine
    combined = pd.concat([pension_df, insurance_df], ignore_index=True)

    if combined.empty:
        print("  ❌ No XML data found!")
    else:
        print(f"\n  ✓ Total funds loaded: {len(combined)}")

    return combined


# =============================================================================
# PDF PARSING
# =============================================================================

def extract_table_from_page(page) -> list:
    """Extract tables from a PDF page."""
    tables = page.extract_tables()
    all_rows = []
    for table in tables:
        if table:
            all_rows.extend(table)
    return all_rows


def identify_columns(header_row: list) -> dict:
    """Identify which columns contain which data based on header text."""
    column_map = {}

    for idx, cell in enumerate(header_row):
        if not cell:
            continue

        cell_text = clean_hebrew_string(str(cell)).lower()

        for field_name, patterns in PDF_COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, cell_text):
                    column_map[field_name] = idx
                    break

    return column_map


def detect_category_from_header(text: str) -> tuple:
    """
    Detect category from PDF section header.

    Returns:
        Tuple of (fund_type, category) or (None, None)
    """
    text = clean_hebrew_string(text)

    # Check for pension categories
    if 'מקיפה' in text or 'פנסיה מקיפה' in text:
        return ('pension', 'comprehensive')
    if 'כללית' in text or 'פנסיה כללית' in text:
        return ('pension', 'general')

    # Check for insurance categories
    if '2004' in text:
        return ('insurance', '2004_onwards')
    if '1992' in text and '2003' in text:
        return ('insurance', '1992_2003')
    if '1990' in text and '1991' in text:
        return ('insurance', '1990_1991')

    return (None, None)


def parse_pdf_file(filepath: Path) -> pd.DataFrame:
    """Parse PDF and extract fund data with categories."""
    print("\n📑 Step 2: Parsing PDF file...")
    print(f"  File: {filepath.name}")

    if not filepath.exists():
        print(f"  ❌ File not found: {filepath}")
        return pd.DataFrame()

    if not PDF_LIBRARY:
        print("  ❌ No PDF library available. Cannot parse PDF.")
        return pd.DataFrame()

    if PDF_LIBRARY == 'pdfplumber':
        return parse_pdf_with_pdfplumber(filepath)
    elif PDF_LIBRARY == 'pypdf':
        return parse_pdf_with_pypdf(filepath)
    elif PDF_LIBRARY == 'pypdf2':
        return parse_pdf_with_pypdf2(filepath)

    return pd.DataFrame()


def parse_pdf_with_pdfplumber(filepath: Path) -> pd.DataFrame:
    """Parse PDF using pdfplumber (best for tables)."""
    data = []
    current_category = (None, None)  # (fund_type, category)
    column_map = {}

    with pdfplumber.open(filepath) as pdf:
        print(f"  Pages: {len(pdf.pages)} (using pdfplumber)")

        for page_num, page in enumerate(pdf.pages, 1):
            # First check for category headers in text
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    detected = detect_category_from_header(line)
                    if detected[0]:
                        current_category = detected
                        print(f"    Page {page_num}: Detected category - {get_category_hebrew(detected[0], detected[1])}")

            # Extract tables
            tables = extract_table_from_page(page)

            if not tables:
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # Check first row for header or category
                first_row_text = ' '.join(str(cell) for cell in table[0] if cell)
                detected = detect_category_from_header(first_row_text)
                if detected[0]:
                    current_category = detected

                # Try to identify columns
                if not column_map:
                    column_map = identify_columns(table[0])
                    if column_map:
                        table = table[1:]

                # Parse data rows
                for row in table:
                    if not row or all(not cell for cell in row):
                        continue

                    parsed_row = parse_table_row_with_category(row, column_map, current_category)
                    if parsed_row and parsed_row.get('Fund_Name'):
                        data.append(parsed_row)

    df = pd.DataFrame(data)

    if not df.empty:
        df['Fund_Name'] = df['Fund_Name'].apply(clean_hebrew_string)
        df = df.drop_duplicates(subset=['Fund_Name', 'Category'], keep='first')

    print(f"  ✓ Extracted {len(df)} fund records from PDF")
    return df


def parse_pdf_with_pypdf(filepath: Path) -> pd.DataFrame:
    """Parse PDF using pypdf (text extraction only)."""
    data = []
    current_category = (None, None)

    reader = pypdf.PdfReader(str(filepath))
    print(f"  Pages: {len(reader.pages)} (using pypdf)")

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text:
            lines = text.split('\n')
            for line in lines:
                # Check for category header
                detected = detect_category_from_header(line)
                if detected[0]:
                    current_category = detected
                    continue

                # Try to parse as data row
                parts = line.split()
                if len(parts) >= 3:
                    has_hebrew = any(is_hebrew(p) for p in parts)
                    has_numbers = any(re.match(r'^-?\d+\.?\d*%?$', p) for p in parts)
                    if has_hebrew and has_numbers:
                        row = parse_text_row_with_category(parts, current_category)
                        if row:
                            data.append(row)

    df = pd.DataFrame(data)
    if not df.empty:
        df['Fund_Name'] = df['Fund_Name'].apply(clean_hebrew_string)
        df = df.drop_duplicates(subset=['Fund_Name', 'Category'], keep='first')

    print(f"  ✓ Extracted {len(df)} fund records from PDF")
    return df


def parse_pdf_with_pypdf2(filepath: Path) -> pd.DataFrame:
    """Parse PDF using PyPDF2 (text extraction only)."""
    data = []
    current_category = (None, None)

    reader = PyPDF2.PdfReader(str(filepath))
    print(f"  Pages: {len(reader.pages)} (using PyPDF2)")

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text:
            lines = text.split('\n')
            for line in lines:
                detected = detect_category_from_header(line)
                if detected[0]:
                    current_category = detected
                    continue

                parts = line.split()
                if len(parts) >= 3:
                    has_hebrew = any(is_hebrew(p) for p in parts)
                    has_numbers = any(re.match(r'^-?\d+\.?\d*%?$', p) for p in parts)
                    if has_hebrew and has_numbers:
                        row = parse_text_row_with_category(parts, current_category)
                        if row:
                            data.append(row)

    df = pd.DataFrame(data)
    if not df.empty:
        df['Fund_Name'] = df['Fund_Name'].apply(clean_hebrew_string)
        df = df.drop_duplicates(subset=['Fund_Name', 'Category'], keep='first')

    print(f"  ✓ Extracted {len(df)} fund records from PDF")
    return df


def parse_table_row_with_category(row: list, column_map: dict, category: tuple) -> dict:
    """Parse a table row including category information."""
    parsed = {
        'Fund_Type': category[0],
        'Category': category[1],
        'Category_Hebrew': get_category_hebrew(category[0], category[1]) if category[0] else 'Unknown'
    }

    if column_map:
        for field_name, col_idx in column_map.items():
            if col_idx < len(row) and row[col_idx]:
                cell_value = row[col_idx]
                if field_name == 'name':
                    parsed['Fund_Name'] = clean_hebrew_string(str(cell_value))
                elif field_name == 'yield_12m':
                    parsed['Yield_12M'] = parse_numeric_value(cell_value)
                elif field_name == 'yield_3y':
                    parsed['Yield_3Y'] = parse_numeric_value(cell_value)
                elif field_name == 'yield_5y':
                    parsed['Yield_5Y'] = parse_numeric_value(cell_value)
    else:
        # Heuristic: find Hebrew text for name, numbers for yields
        for cell in row:
            if cell and is_hebrew(str(cell)):
                parsed['Fund_Name'] = clean_hebrew_string(str(cell))
                break

        numeric_values = []
        for cell in row:
            num = parse_numeric_value(cell)
            if num is not None:
                numeric_values.append(num)

        if len(numeric_values) >= 1:
            parsed['Yield_12M'] = numeric_values[0]
        if len(numeric_values) >= 2:
            parsed['Yield_3Y'] = numeric_values[1]
        if len(numeric_values) >= 3:
            parsed['Yield_5Y'] = numeric_values[2]

    return parsed if parsed.get('Fund_Name') else None


def parse_text_row_with_category(parts: list, category: tuple) -> dict:
    """Parse a text row with category information."""
    parsed = {
        'Fund_Type': category[0],
        'Category': category[1],
        'Category_Hebrew': get_category_hebrew(category[0], category[1]) if category[0] else 'Unknown'
    }

    hebrew_parts = []
    numeric_values = []

    for part in parts:
        if is_hebrew(part):
            hebrew_parts.append(fix_hebrew_text(part))
        else:
            num = parse_numeric_value(part)
            if num is not None:
                numeric_values.append(num)

    if hebrew_parts:
        parsed['Fund_Name'] = clean_hebrew_string(' '.join(hebrew_parts))

    if len(numeric_values) >= 1:
        parsed['Yield_12M'] = numeric_values[0]
    if len(numeric_values) >= 2:
        parsed['Yield_3Y'] = numeric_values[1]
    if len(numeric_values) >= 3:
        parsed['Yield_5Y'] = numeric_values[2]

    return parsed if parsed.get('Fund_Name') else None


# =============================================================================
# MATCHING AND COMPARISON
# =============================================================================

def find_best_match(name: str, candidates: list, threshold: int = FUZZY_MATCH_THRESHOLD) -> tuple:
    """Find the best matching name from candidates using fuzzy matching."""
    if not name or not candidates:
        return None, 0

    clean_name = clean_hebrew_string(name)

    # Exact match
    for candidate in candidates:
        if clean_hebrew_string(candidate) == clean_name:
            return candidate, 100

    # Partial match
    for candidate in candidates:
        clean_candidate = clean_hebrew_string(candidate)
        if clean_name in clean_candidate or clean_candidate in clean_name:
            return candidate, 90

    # Fuzzy match
    if FUZZY_AVAILABLE:
        result = process.extractOne(
            clean_name,
            candidates,
            scorer=fuzz.token_sort_ratio
        )
        if result and result[1] >= threshold:
            return result[0], result[1]

    return None, 0


def compare_funds_by_category(pdf_df: pd.DataFrame, xml_df: pd.DataFrame,
                               match_threshold: int = FUZZY_MATCH_THRESHOLD,
                               value_tolerance: float = VALUE_TOLERANCE) -> pd.DataFrame:
    """
    Compare PDF data against XML data, matching within the same category.
    """
    print("\n🔍 Step 3: Matching and Comparing...")

    if pdf_df.empty or xml_df.empty:
        print("  ❌ Cannot compare: one or both datasets are empty")
        return pd.DataFrame()

    results = []
    fields_to_compare = [
        ('Yield_12M', 'תשואה 12 חודשים'),
        ('Yield_3Y', 'תשואה ממוצעת 3 שנים'),
        ('Yield_5Y', 'תשואה ממוצעת 5 שנים')
    ]

    # Group by category
    categories = pdf_df['Category'].unique()

    for category in categories:
        if not category:
            continue

        pdf_cat = pdf_df[pdf_df['Category'] == category]
        xml_cat = xml_df[xml_df['Category'] == category]

        if xml_cat.empty:
            print(f"  ⚠️  No XML data for category: {get_category_hebrew(pdf_cat.iloc[0]['Fund_Type'], category)}")
            continue

        xml_names = xml_cat['Fund_Name'].tolist()
        category_hebrew = pdf_cat.iloc[0]['Category_Hebrew']

        print(f"  Comparing {len(pdf_cat)} PDF funds in '{category_hebrew}'...")

        matched_count = 0
        for _, pdf_row in pdf_cat.iterrows():
            pdf_name = pdf_row.get('Fund_Name', '')

            matched_name, match_score = find_best_match(pdf_name, xml_names, match_threshold)

            if not matched_name:
                results.append({
                    'Category': category_hebrew,
                    'Fund_Name': pdf_name,
                    'Field': 'ALL',
                    'PDF_Value': 'Found in PDF',
                    'XML_Value': 'NOT FOUND IN XML',
                    'Diff': 'N/A',
                    'Status': 'NO_MATCH',
                    'Match_Score': 0
                })
                continue

            matched_count += 1
            xml_row = xml_cat[xml_cat['Fund_Name'] == matched_name].iloc[0]

            for field, field_label in fields_to_compare:
                pdf_val = pdf_row.get(field)
                xml_val = xml_row.get(field)

                pdf_norm = normalize_percentage(pdf_val)
                xml_norm = normalize_percentage(xml_val)

                if pdf_norm is not None and xml_norm is not None:
                    diff = round(abs(pdf_norm - xml_norm), 4)
                    is_match = diff <= value_tolerance
                else:
                    diff = 'N/A'
                    is_match = (pdf_norm is None and xml_norm is None)

                results.append({
                    'Category': category_hebrew,
                    'Fund_Name': pdf_name,
                    'Field': field_label,
                    'PDF_Value': f"{pdf_norm:.2f}" if pdf_norm is not None else 'N/A',
                    'XML_Value': f"{xml_norm:.2f}" if xml_norm is not None else 'N/A',
                    'Diff': diff if isinstance(diff, str) else f"{diff:.4f}",
                    'Status': 'Match' if is_match else 'Mismatch',
                    'Match_Score': match_score
                })

        print(f"    ✓ Matched {matched_count}/{len(pdf_cat)} funds")

    return pd.DataFrame(results)


# =============================================================================
# OUTPUT AND REPORTING
# =============================================================================

def generate_report(comparison_df: pd.DataFrame, output_path: Path) -> None:
    """Generate comparison report and save to CSV."""
    print("\n📊 Step 4: Generating Report...")

    if comparison_df.empty:
        print("  ❌ No comparison data to report")
        return

    # Save full results
    comparison_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved: {output_path}")

    # Summary statistics
    total_comparisons = len(comparison_df)
    mismatches = comparison_df[comparison_df['Status'] == 'Mismatch']
    no_matches = comparison_df[comparison_df['Status'] == 'NO_MATCH']
    matches = comparison_df[comparison_df['Status'] == 'Match']

    unique_funds = comparison_df['Fund_Name'].nunique()
    funds_with_issues = comparison_df[comparison_df['Status'].isin(['Mismatch', 'NO_MATCH'])]['Fund_Name'].nunique()

    print("\n" + "=" * 70)
    print("                    VALIDATION SUMMARY")
    print("=" * 70)
    print(f"  Total Funds Analyzed:     {unique_funds}")
    print(f"  Total Comparisons:        {total_comparisons}")
    print(f"  Matches:                  {len(matches)}")
    print(f"  Mismatches:               {len(mismatches)}")
    print(f"  Not Found in XML:         {len(no_matches)}")
    print(f"  Funds with Issues:        {funds_with_issues}")

    # Summary by category
    if 'Category' in comparison_df.columns:
        print("\n  BY CATEGORY:")
        for category in comparison_df['Category'].unique():
            cat_df = comparison_df[comparison_df['Category'] == category]
            cat_mismatches = len(cat_df[cat_df['Status'] == 'Mismatch'])
            cat_total = len(cat_df)
            print(f"    {category}: {cat_mismatches} mismatches / {cat_total} comparisons")

    print("=" * 70)

    if len(mismatches) > 0:
        print("\n⚠️  DISCREPANCIES FOUND:")
        print("-" * 70)

        for _, row in mismatches.head(15).iterrows():
            print(f"  [{row['Category']}] {row['Fund_Name']}")
            print(f"    {row['Field']}: PDF={row['PDF_Value']} | XML={row['XML_Value']} | Diff={row['Diff']}")
            print()

        if len(mismatches) > 15:
            print(f"  ... and {len(mismatches) - 15} more discrepancies")
            print(f"  See full report in: {output_path}")
    else:
        print("\n✅ All matched values are within tolerance!")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the validation script."""
    parser = argparse.ArgumentParser(
        description='Validate pension fund data: PDF (Ground Truth) vs XML (System Result)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories:
  Pension (PensiaNet.xml):
    - קרן פנסיה מקיפה (Comprehensive)
    - קרן פנסיה כללית (General)

  Insurance (hevrot.xml):
    - משנת 2004 ואילך (2004 onwards)
    - משנת 1992 - 2003
    - משנת 1990 - 1991

Examples:
  python validate_pension_data.py
  python validate_pension_data.py --pdf report.pdf --xml-pension PensiaNet.xml --xml-insurance hevrot.xml
        """
    )

    parser.add_argument(
        '--pdf',
        default='צילום מסך 2026-02-04 113024-combined.pdf',
        help='Path to the PDF report'
    )
    parser.add_argument(
        '--xml-pension',
        default='PensiaNet.xml',
        dest='xml_pension',
        help='Path to pension XML file (default: PensiaNet.xml)'
    )
    parser.add_argument(
        '--xml-insurance',
        default='hevrot.xml',
        dest='xml_insurance',
        help='Path to insurance XML file (default: hevrot.xml)'
    )
    parser.add_argument(
        '--output',
        default='comparison_discrepancies.csv',
        help='Output CSV file path'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=FUZZY_MATCH_THRESHOLD,
        help=f'Fuzzy match threshold (default: {FUZZY_MATCH_THRESHOLD})'
    )
    parser.add_argument(
        '--tolerance',
        type=float,
        default=VALUE_TOLERANCE,
        help=f'Numeric comparison tolerance (default: {VALUE_TOLERANCE})'
    )

    args = parser.parse_args()

    match_threshold = args.threshold
    value_tolerance = args.tolerance

    print("=" * 70)
    print("   PENSION FUND DATA VALIDATION")
    print("   Ground Truth (PDF) vs System Result (XML)")
    print("=" * 70)
    print(f"  PDF File:        {args.pdf}")
    print(f"  Pension XML:     {args.xml_pension}")
    print(f"  Insurance XML:   {args.xml_insurance}")
    print(f"  Output:          {args.output}")
    print(f"  Match Threshold: {match_threshold}%")
    print(f"  Value Tolerance: {value_tolerance}")
    print("=" * 70)

    # Step 1: Load XML data
    xml_df = load_all_xml_data(
        Path(args.xml_pension),
        Path(args.xml_insurance)
    )

    # Step 2: Parse PDF
    pdf_df = parse_pdf_file(Path(args.pdf))

    # Step 3: Compare by category
    comparison_df = compare_funds_by_category(
        pdf_df, xml_df, match_threshold, value_tolerance
    )

    # Step 4: Generate report
    generate_report(comparison_df, Path(args.output))

    # Exit code
    if comparison_df.empty:
        return 1

    mismatch_count = len(comparison_df[comparison_df['Status'] == 'Mismatch'])
    return 0 if mismatch_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
