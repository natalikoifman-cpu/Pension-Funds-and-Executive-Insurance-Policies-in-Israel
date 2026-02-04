#!/usr/bin/env python3
"""
Ground Truth vs. System Result Data Validation Script

Compares pension fund data from a Hebrew PDF report (Ground Truth) against
raw data from XML files (System Result) to identify discrepancies.

Usage:
    python validate_pension_data.py [--pdf PATH] [--xml1 PATH] [--xml2 PATH] [--output PATH]

Requirements:
    pip install pdfplumber pandas beautifulsoup4 lxml thefuzz python-Levenshtein
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional
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

# XML field mappings
XML_FIELDS = {
    'name': ['SHEM_GUF', 'SHM_KRN', 'FUND_NAME', 'NAME'],
    'yearly_yield': ['TSUA_SHNATIT', 'YEAR_TO_DATE_YIELD', 'TSUA_MEMUZAAT_SHNATIT', 'ANNUAL_RETURN'],
    'yield_3_years': ['TSUA_SHNATIT_MEMUZAAT_3_SHANIM', 'YIELD_TRAILING_3_YRS', 'AVG_ANNUAL_YIELD_3_YRS'],
    'yield_5_years': ['TSUA_SHNATIT_MEMUZAAT_5_SHANIM', 'YIELD_TRAILING_5_YRS', 'AVG_ANNUAL_YIELD_5_YRS'],
    'management_fee': ['SHIUR_D_NIHUL_NECHASIM', 'AVG_ANNUAL_MANAGEMENT_FEE', 'MANAGEMENT_FEE', 'D_NIHUL'],
}

# Hebrew column name patterns for PDF extraction
PDF_COLUMN_PATTERNS = {
    'name': [r'שם\s*קרן', r'שם\s*הקרן', r'קרן', r'מוצר'],
    'yearly_yield': [r'תשואה\s*שנתית', r'תשואה\s*שנה', r'שנתית'],
    'yield_3_years': [r'תשואה\s*3\s*שנים', r'3\s*שנים', r'תשואה.*3'],
    'yield_5_years': [r'תשואה\s*5\s*שנים', r'5\s*שנים', r'תשואה.*5'],
    'management_fee': [r'דמי\s*ניהול', r'ניהול', r'עמלה'],
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

    PDF extractors often extract RTL text backwards. This function detects
    and corrects such issues by checking if reversing improves readability.
    """
    if not text or not is_hebrew(text):
        return text

    # Common Hebrew pension fund keywords (correct orientation)
    known_words = [
        'מנורה', 'מבטחים', 'פנסיה', 'הראל', 'מיטב', 'אלטשולר', 'שחם',
        'כלל', 'הפניקס', 'מגדל', 'איילון', 'ביטוח', 'גמל', 'קרן',
        'מניות', 'אג"ח', 'כללי', 'משולב', 'סחיר', 'חיסכון'
    ]

    # Check if text contains known words
    text_lower = text.strip()
    reversed_text = text_lower[::-1]

    # Count matches in original vs reversed
    original_matches = sum(1 for word in known_words if word in text_lower)
    reversed_matches = sum(1 for word in known_words if word in reversed_text)

    # If reversed has more matches, text was extracted backwards
    if reversed_matches > original_matches:
        return reversed_text

    return text


def clean_hebrew_string(text: str) -> str:
    """Clean and normalize Hebrew string for comparison."""
    if not text:
        return ""

    # Fix potential RTL issues
    text = fix_hebrew_text(str(text))

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove common suffixes/prefixes that vary
    text = re.sub(r'\s*(בע"מ|בעמ|ltd\.?|inc\.?)\s*', '', text, flags=re.IGNORECASE)

    return text


# =============================================================================
# NUMERIC UTILITIES
# =============================================================================

def parse_numeric_value(value) -> Optional[float]:
    """
    Parse numeric value from various formats.

    Handles:
    - Percentage strings: "12.5%", "12.5 %"
    - Decimal values: "0.125", "12.5"
    - Hebrew formatted numbers
    - None/empty values
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    # Convert to string and clean
    text = str(value).strip()

    # Remove percentage sign
    text = text.replace('%', '').strip()

    # Remove Hebrew characters if mixed with numbers
    text = re.sub(r'[^\d.\-,]', '', text)

    # Handle comma as decimal separator
    if ',' in text and '.' not in text:
        text = text.replace(',', '.')

    try:
        num = float(text)
        # If value looks like it's in percentage form (e.g., 0.125 meaning 12.5%)
        # We keep it as-is and normalize during comparison
        return num
    except (ValueError, TypeError):
        return None


def normalize_percentage(value: Optional[float]) -> Optional[float]:
    """
    Normalize percentage values for comparison.

    Converts values to percentage form (e.g., 12.5 not 0.125).
    """
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

    # Normalize both values
    norm1 = normalize_percentage(val1)
    norm2 = normalize_percentage(val2)

    if norm1 is None or norm2 is None:
        return False

    return abs(norm1 - norm2) <= tolerance


# =============================================================================
# XML PARSING
# =============================================================================

def parse_xml_file(filepath: Path) -> pd.DataFrame:
    """
    Parse a single XML file and extract pension fund data.

    Args:
        filepath: Path to the XML file

    Returns:
        DataFrame with extracted fund data
    """
    print(f"  Parsing: {filepath.name}")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'lxml-xml')

    # Find all fund records (try common parent tags)
    records = soup.find_all(['FUND', 'KEREN', 'RECORD', 'ROW', 'ITEM'])

    # If no structured records, try to find repeating patterns
    if not records:
        # Look for tags that appear multiple times
        all_tags = [tag.name for tag in soup.find_all()]
        tag_counts = pd.Series(all_tags).value_counts()
        potential_records = tag_counts[tag_counts > 1].index.tolist()

        for tag_name in potential_records:
            records = soup.find_all(tag_name)
            if len(records) > 5:  # Likely fund records
                break

    data = []
    for record in records:
        row = {}

        # Extract each field using the mapping
        for field_name, possible_tags in XML_FIELDS.items():
            for tag in possible_tags:
                element = record.find(tag)
                if element and element.text:
                    if field_name == 'name':
                        row[field_name] = clean_hebrew_string(element.text)
                    else:
                        row[field_name] = parse_numeric_value(element.text)
                    break

        # Only add if we found at least a name
        if row.get('name'):
            data.append(row)

    df = pd.DataFrame(data)
    print(f"    Found {len(df)} records")
    return df


def load_xml_data(xml_paths: list) -> pd.DataFrame:
    """
    Load and combine data from multiple XML files.

    Args:
        xml_paths: List of paths to XML files

    Returns:
        Combined DataFrame with all fund data
    """
    print("\n📄 Step 1: Parsing XML files...")

    dfs = []
    for path in xml_paths:
        filepath = Path(path)
        if filepath.exists():
            df = parse_xml_file(filepath)
            if not df.empty:
                df['source_file'] = filepath.name
                dfs.append(df)
        else:
            print(f"  ⚠️  File not found: {path}")

    if not dfs:
        print("  ❌ No XML data found!")
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)

    # Remove duplicates based on name (keep first occurrence)
    combined = combined.drop_duplicates(subset=['name'], keep='first')

    print(f"  ✓ Total unique funds from XML: {len(combined)}")
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
    """
    Identify which columns contain which data based on header text.

    Args:
        header_row: List of header cell values

    Returns:
        Dictionary mapping field names to column indices
    """
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


def parse_pdf_file(filepath: Path) -> pd.DataFrame:
    """
    Parse a PDF file and extract pension fund data from tables.

    Args:
        filepath: Path to the PDF file

    Returns:
        DataFrame with extracted fund data
    """
    print("\n📑 Step 2: Parsing PDF file...")
    print(f"  File: {filepath.name}")

    if not filepath.exists():
        print(f"  ❌ File not found: {filepath}")
        return pd.DataFrame()

    if not PDF_LIBRARY:
        print("  ❌ No PDF library available. Cannot parse PDF.")
        return pd.DataFrame()

    data = []
    column_map = {}

    # Use pdfplumber (preferred)
    if PDF_LIBRARY == 'pdfplumber':
        return parse_pdf_with_pdfplumber(filepath)
    # Fallback to pypdf
    elif PDF_LIBRARY == 'pypdf':
        return parse_pdf_with_pypdf(filepath)
    # Fallback to PyPDF2
    elif PDF_LIBRARY == 'pypdf2':
        return parse_pdf_with_pypdf2(filepath)

    return pd.DataFrame()


def parse_pdf_with_pdfplumber(filepath: Path) -> pd.DataFrame:
    """Parse PDF using pdfplumber (best for tables)."""
    data = []
    column_map = {}

    with pdfplumber.open(filepath) as pdf:
        print(f"  Pages: {len(pdf.pages)} (using pdfplumber)")

        for page_num, page in enumerate(pdf.pages, 1):
            # Extract tables
            tables = extract_table_from_page(page)

            if not tables:
                # Try extracting text if no tables found
                text = page.extract_text()
                if text:
                    # Parse text-based layout
                    lines = text.split('\n')
                    for line in lines:
                        # Try to identify data rows
                        parts = line.split()
                        if len(parts) >= 3:
                            # Check if line contains Hebrew text and numbers
                            has_hebrew = any(is_hebrew(p) for p in parts)
                            has_numbers = any(re.match(r'^-?\d+\.?\d*%?$', p) for p in parts)
                            if has_hebrew and has_numbers:
                                # Attempt to parse this line
                                row = parse_text_row(parts)
                                if row:
                                    data.append(row)
                continue

            for table in tables:
                if not table or len(table) < 2:
                    continue

                # First row might be header
                if not column_map:
                    column_map = identify_columns(table[0])
                    if column_map:
                        print(f"    Found columns: {list(column_map.keys())}")
                        table = table[1:]  # Skip header

                # Parse data rows
                for row in table:
                    if not row or all(not cell for cell in row):
                        continue

                    parsed_row = parse_table_row(row, column_map)
                    if parsed_row and parsed_row.get('name'):
                        data.append(parsed_row)

    df = pd.DataFrame(data)

    # Clean up the data
    if not df.empty:
        df['name'] = df['name'].apply(clean_hebrew_string)
        df = df.drop_duplicates(subset=['name'], keep='first')

    print(f"  ✓ Extracted {len(df)} fund records from PDF")
    return df


def parse_pdf_with_pypdf(filepath: Path) -> pd.DataFrame:
    """Parse PDF using pypdf (text extraction only)."""
    data = []

    reader = pypdf.PdfReader(str(filepath))
    print(f"  Pages: {len(reader.pages)} (using pypdf)")

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text:
            data.extend(parse_text_content(text))

    df = pd.DataFrame(data)
    if not df.empty:
        df['name'] = df['name'].apply(clean_hebrew_string)
        df = df.drop_duplicates(subset=['name'], keep='first')

    print(f"  ✓ Extracted {len(df)} fund records from PDF")
    return df


def parse_pdf_with_pypdf2(filepath: Path) -> pd.DataFrame:
    """Parse PDF using PyPDF2 (text extraction only)."""
    data = []

    reader = PyPDF2.PdfReader(str(filepath))
    print(f"  Pages: {len(reader.pages)} (using PyPDF2)")

    for page_num, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        if text:
            data.extend(parse_text_content(text))

    df = pd.DataFrame(data)
    if not df.empty:
        df['name'] = df['name'].apply(clean_hebrew_string)
        df = df.drop_duplicates(subset=['name'], keep='first')

    print(f"  ✓ Extracted {len(df)} fund records from PDF")
    return df


def parse_text_content(text: str) -> list:
    """Parse text content from PDF and extract fund data."""
    data = []
    lines = text.split('\n')

    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            has_hebrew = any(is_hebrew(p) for p in parts)
            has_numbers = any(re.match(r'^-?\d+\.?\d*%?$', p) for p in parts)
            if has_hebrew and has_numbers:
                row = parse_text_row(parts)
                if row:
                    data.append(row)

    return data


def parse_table_row(row: list, column_map: dict) -> dict:
    """Parse a single table row using the column mapping."""
    parsed = {}

    for field_name, col_idx in column_map.items():
        if col_idx < len(row) and row[col_idx]:
            cell_value = row[col_idx]
            if field_name == 'name':
                parsed[field_name] = clean_hebrew_string(str(cell_value))
            else:
                parsed[field_name] = parse_numeric_value(cell_value)

    # If no column map, try heuristic approach
    if not column_map and row:
        # Find Hebrew text (likely fund name)
        for cell in row:
            if cell and is_hebrew(str(cell)):
                parsed['name'] = clean_hebrew_string(str(cell))
                break

        # Find numeric values
        numeric_values = []
        for cell in row:
            num = parse_numeric_value(cell)
            if num is not None:
                numeric_values.append(num)

        # Assign numeric values to fields based on typical order
        field_order = ['yearly_yield', 'yield_3_years', 'yield_5_years', 'management_fee']
        for i, num in enumerate(numeric_values[:4]):
            if i < len(field_order):
                parsed[field_order[i]] = num

    return parsed


def parse_text_row(parts: list) -> dict:
    """Parse a row from text extraction (when tables fail)."""
    parsed = {}

    # Collect Hebrew parts for fund name
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
        parsed['name'] = clean_hebrew_string(' '.join(hebrew_parts))

    # Assign numeric values
    field_order = ['yearly_yield', 'yield_3_years', 'yield_5_years', 'management_fee']
    for i, num in enumerate(numeric_values[:4]):
        if i < len(field_order):
            parsed[field_order[i]] = num

    return parsed if parsed.get('name') else None


# =============================================================================
# MATCHING AND COMPARISON
# =============================================================================

def find_best_match(name: str, candidates: list, threshold: int = FUZZY_MATCH_THRESHOLD) -> tuple:
    """
    Find the best matching name from candidates using fuzzy matching.

    Args:
        name: Name to match
        candidates: List of candidate names
        threshold: Minimum similarity score

    Returns:
        Tuple of (matched_name, score) or (None, 0)
    """
    if not name or not candidates:
        return None, 0

    # Clean the input name
    clean_name = clean_hebrew_string(name)

    # Try exact match first
    for candidate in candidates:
        if clean_hebrew_string(candidate) == clean_name:
            return candidate, 100

    # Try partial match (substring)
    for candidate in candidates:
        clean_candidate = clean_hebrew_string(candidate)
        if clean_name in clean_candidate or clean_candidate in clean_name:
            return candidate, 90

    # Fuzzy match (if available)
    if FUZZY_AVAILABLE:
        result = process.extractOne(
            clean_name,
            candidates,
            scorer=fuzz.token_sort_ratio
        )

        if result and result[1] >= threshold:
            return result[0], result[1]

    return None, 0


def compare_funds(pdf_df: pd.DataFrame, xml_df: pd.DataFrame,
                  match_threshold: int = FUZZY_MATCH_THRESHOLD,
                  value_tolerance: float = VALUE_TOLERANCE) -> pd.DataFrame:
    """
    Compare PDF data against XML data and find discrepancies.

    Args:
        pdf_df: DataFrame from PDF extraction
        xml_df: DataFrame from XML parsing
        match_threshold: Minimum similarity score for fuzzy name matching
        value_tolerance: Tolerance for numeric value comparison

    Returns:
        DataFrame with comparison results
    """
    print("\n🔍 Step 3: Matching and Comparing...")

    if pdf_df.empty or xml_df.empty:
        print("  ❌ Cannot compare: one or both datasets are empty")
        return pd.DataFrame()

    xml_names = xml_df['name'].tolist()
    results = []

    matched_count = 0
    fields_to_compare = ['yearly_yield', 'yield_3_years', 'yield_5_years', 'management_fee']
    field_labels = {
        'yearly_yield': 'תשואה שנתית',
        'yield_3_years': 'תשואה 3 שנים',
        'yield_5_years': 'תשואה 5 שנים',
        'management_fee': 'דמי ניהול'
    }

    for _, pdf_row in pdf_df.iterrows():
        pdf_name = pdf_row.get('name', '')

        # Find matching XML record
        matched_name, match_score = find_best_match(pdf_name, xml_names, match_threshold)

        if not matched_name:
            # No match found
            results.append({
                'Fund_Name': pdf_name,
                'Field': 'ALL',
                'PDF_Value': 'Found in PDF',
                'XML_Value': 'NOT FOUND',
                'Diff': 'N/A',
                'Status': 'NO_MATCH',
                'Match_Score': 0
            })
            continue

        matched_count += 1
        xml_row = xml_df[xml_df['name'] == matched_name].iloc[0]

        # Compare each field
        for field in fields_to_compare:
            pdf_val = pdf_row.get(field)
            xml_val = xml_row.get(field) if field in xml_row else None

            # Normalize values for comparison
            pdf_norm = normalize_percentage(pdf_val)
            xml_norm = normalize_percentage(xml_val)

            # Calculate difference
            if pdf_norm is not None and xml_norm is not None:
                diff = round(abs(pdf_norm - xml_norm), 4)
                is_match = diff <= value_tolerance
            else:
                diff = 'N/A'
                is_match = (pdf_norm is None and xml_norm is None)

            results.append({
                'Fund_Name': pdf_name,
                'Field': field_labels.get(field, field),
                'PDF_Value': f"{pdf_norm:.2f}" if pdf_norm is not None else 'N/A',
                'XML_Value': f"{xml_norm:.2f}" if xml_norm is not None else 'N/A',
                'Diff': diff if isinstance(diff, str) else f"{diff:.4f}",
                'Status': 'Match' if is_match else 'Mismatch',
                'Match_Score': match_score
            })

    print(f"  ✓ Matched {matched_count}/{len(pdf_df)} funds from PDF")

    return pd.DataFrame(results)


# =============================================================================
# OUTPUT AND REPORTING
# =============================================================================

def generate_report(comparison_df: pd.DataFrame, output_path: Path) -> None:
    """
    Generate comparison report and save to CSV.

    Args:
        comparison_df: DataFrame with comparison results
        output_path: Path for output CSV file
    """
    print("\n📊 Step 4: Generating Report...")

    if comparison_df.empty:
        print("  ❌ No comparison data to report")
        return

    # Save full results to CSV
    comparison_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"  ✓ Saved: {output_path}")

    # Generate summary statistics
    total_comparisons = len(comparison_df)

    mismatches = comparison_df[comparison_df['Status'] == 'Mismatch']
    no_matches = comparison_df[comparison_df['Status'] == 'NO_MATCH']
    matches = comparison_df[comparison_df['Status'] == 'Match']

    unique_funds = comparison_df['Fund_Name'].nunique()
    funds_with_issues = comparison_df[comparison_df['Status'].isin(['Mismatch', 'NO_MATCH'])]['Fund_Name'].nunique()

    print("\n" + "=" * 60)
    print("                    VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Total Funds Analyzed:     {unique_funds}")
    print(f"  Total Comparisons:        {total_comparisons}")
    print(f"  Matches:                  {len(matches)}")
    print(f"  Mismatches:               {len(mismatches)}")
    print(f"  Not Found in XML:         {len(no_matches)}")
    print(f"  Funds with Issues:        {funds_with_issues}")
    print("=" * 60)

    if len(mismatches) > 0:
        print("\n⚠️  DISCREPANCIES FOUND:")
        print("-" * 60)

        for _, row in mismatches.head(10).iterrows():
            print(f"  Fund: {row['Fund_Name']}")
            print(f"    Field: {row['Field']}")
            print(f"    PDF: {row['PDF_Value']} | XML: {row['XML_Value']} | Diff: {row['Diff']}")
            print()

        if len(mismatches) > 10:
            print(f"  ... and {len(mismatches) - 10} more discrepancies")
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
Examples:
  python validate_pension_data.py
  python validate_pension_data.py --pdf report.pdf --xml1 hevrot.xml --xml2 PensiaNet.xml
  python validate_pension_data.py --output results.csv
        """
    )

    parser.add_argument(
        '--pdf',
        default='צילום מסך 2026-02-04 113024-combined.pdf',
        help='Path to the PDF report (default: צילום מסך 2026-02-04 113024-combined.pdf)'
    )
    parser.add_argument(
        '--xml1',
        default='hevrot.xml',
        help='Path to first XML file (default: hevrot.xml)'
    )
    parser.add_argument(
        '--xml2',
        default='PensiaNet.xml',
        help='Path to second XML file (default: PensiaNet.xml)'
    )
    parser.add_argument(
        '--output',
        default='comparison_discrepancies.csv',
        help='Output CSV file path (default: comparison_discrepancies.csv)'
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

    # Use args values for thresholds
    match_threshold = args.threshold
    value_tolerance = args.tolerance

    print("=" * 60)
    print("   PENSION FUND DATA VALIDATION")
    print("   Ground Truth (PDF) vs System Result (XML)")
    print("=" * 60)
    print(f"  PDF File:    {args.pdf}")
    print(f"  XML Files:   {args.xml1}, {args.xml2}")
    print(f"  Output:      {args.output}")
    print(f"  Match Threshold: {match_threshold}%")
    print(f"  Value Tolerance: {value_tolerance}")
    print("=" * 60)

    # Step 1: Load XML data
    xml_paths = [args.xml1, args.xml2]
    xml_df = load_xml_data(xml_paths)

    # Step 2: Parse PDF
    pdf_path = Path(args.pdf)
    pdf_df = parse_pdf_file(pdf_path)

    # Step 3: Compare data
    comparison_df = compare_funds(pdf_df, xml_df, match_threshold, value_tolerance)

    # Step 4: Generate report
    output_path = Path(args.output)
    generate_report(comparison_df, output_path)

    # Return appropriate exit code
    if comparison_df.empty:
        return 1

    mismatch_count = len(comparison_df[comparison_df['Status'] == 'Mismatch'])
    return 0 if mismatch_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
