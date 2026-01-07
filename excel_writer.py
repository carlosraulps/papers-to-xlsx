import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment
import re

def clean_sheet_name(raw_name):
    """
    Cleans the sheet name to ensure it's valid for Excel.
    Excel sheet names: max 31 chars, no [] : * ? / \
    """
    # Remove invalid characters
    invalid_chars = r'[\[\]:*?/\\]'
    name = re.sub(invalid_chars, '', raw_name)
    # Truncate to 31 chars
    return name[:31]

def get_unique_sheet_name(workbook, base_name):
    """
    Generates a unique sheet name by appending a counter if specific name exists.
    """
    name = clean_sheet_name(base_name)
    if name not in workbook.sheetnames:
        return name
    
    count = 2
    while True:
        new_name = f"{name}_{count}"
        if len(new_name) > 31:
            # If counting makes it too long, truncate base further
            truncated_len = 31 - len(str(count)) - 1
            new_name = f"{name[:truncated_len]}_{count}"
            
        if new_name not in workbook.sheetnames:
            return new_name
        count += 1

def load_or_create_workbook(filename):
    """Loads an existing workbook or creates a new one if it doesn't exist."""
    try:
        wb = openpyxl.load_workbook(filename)
        return wb
    except FileNotFoundError:
        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]
        return wb


def add_paper_to_workbook(wb, paper_data):
    """
    Adds a new sheet to the workbook for the given paper data.
    """
    # Construct base sheet name: Author_Year
    # Extract first author surname
    authors = paper_data.get("Authors", "Unknown")
    if isinstance(authors, list):
         first_author = authors[0].split()[-1] if authors else "Unknown"
    else:
         # simple heuristic if it's a string
         first_author = authors.split(',')[0].split()[-1] if ',' in authors else authors.split()[-1]
    
    year = str(paper_data.get("Year", "Unknown"))
    
    # Clean up author/year to be safe
    first_author = "".join(x for x in first_author if x.isalnum())
    year = "".join(x for x in year if x.isalnum())

    base_name = f"{first_author}_{year}"
    sheet_name = get_unique_sheet_name(wb, base_name)
    
    ws = wb.create_sheet(title=sheet_name)
    
    # Headers? The user requested Col A = Category, Col B = Answer.
    # We won't add a header row unless implicit, but the user description 
    # implies a key-value list structure directly in the cells.
    # Let's add a simple header for clarity anyway, or just start data. 
    # User said: "Sheet Layout: Column A: "Category/Question", Column B: "Extracted Answer""
    # I will put this as the first row.
    ws['A1'] = "Category/Question"
    ws['B1'] = "Extracted Answer"
    
    # Define the order of keys to write
    keys_order = [
        "Title", "Authors", "Journal", "Volume", "Pages", "Year", "DOI",
        "Central Problem", "Central Hypothesis", "Central Objective",
        "Central Independent Variables", "Central Dependent Variables",
        "Methodology & Tools", "Central Result", "Central Conclusion"
    ]
    
    row_idx = 2
    for key in keys_order:
        val = paper_data.get(key, "N/A")
        # Ensure list values are joined into string
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        else:
            val = str(val)
            
        ws.cell(row=row_idx, column=1, value=key)
        ws.cell(row=row_idx, column=2, value=val)
        row_idx += 1
        
    # Formatting
    # A width 30, B width 100
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 100
    
    # Text Wrap and Center Alignment for ALL cells used
    # Iterate over all rows we wrote
    for row in ws.iter_rows(min_row=1, max_row=row_idx-1, min_col=1, max_col=2):
        for cell in row:
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

def save_workbook(wb, filename):
    wb.save(filename)
