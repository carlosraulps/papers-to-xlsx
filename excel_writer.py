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
    # Clean up author/year
    first_author = "".join(x for x in first_author if x.isalnum())
    year = "".join(x for x in year if x.isalnum())
    
    # Include Short Title for better sorting/identification
    title = paper_data.get("Title", "")
    # Remove non-alphanumeric (keep spaces for readability then remove later? or just strict alnum)
    # The clean_sheet_name handles invalid chars, but let's be cleaner for the base
    short_title = "".join(x for x in title if x.isalnum())
    
    # Construct base: Author_Year_Title
    # We need to be careful with length. 31 limit.
    # heuristic: Author (max 10) + _ + Year (4) + _ + Title (remaining)
    # This ensures Author_Year is preserved.
    
    author_part = first_author[:10]
    year_part = year[:4]
    
    # Author_Year_ is roughly 10+1+4+1 = 16 chars. 
    # Remaining for title = 31 - 16 = 15 chars.
    
    base_name = f"{author_part}_{year_part}_{short_title}"
    
    # get_unique_sheet_name will truncate the whole thing to 31 if needed
    sheet_name = get_unique_sheet_name(wb, base_name)
    
    ws = wb.create_sheet(title=sheet_name)
    
    # Headers
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
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        else:
            val = str(val)
            
        ws.cell(row=row_idx, column=1, value=key)
        ws.cell(row=row_idx, column=2, value=val)
        row_idx += 1
        
    # Formatting
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 100
    
    for row in ws.iter_rows(min_row=1, max_row=row_idx-1, min_col=1, max_col=2):
        for cell in row:
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

def sort_sheets_alphabetically(wb):
    """Sorts all sheets in the workbook alphabetically."""
    # Get all sheet names
    sheet_names = wb.sheetnames
    # Sort them
    sheet_names.sort()
    # Reorder
    for i, name in enumerate(sheet_names):
        wb.move_sheet(wb[name], offset=i - wb.index(wb[name]))

def cleanup_empty_sheets(wb):
    """Removes 'Sheet' or 'Sheet1' if they are default/empty."""
    for default_name in ["Sheet", "Sheet1"]:
        if default_name in wb.sheetnames:
            ws = wb[default_name]
            if ws.max_row <= 1: # Empty or just header (if generated)?
                # Usually default sheet is empty (max_row=1 if accessed or 0)
                # Let's just delete it if we have other sheets
                if len(wb.sheetnames) > 1:
                    del wb[default_name]

def save_workbook(wb, filename):
    cleanup_empty_sheets(wb)
    sort_sheets_alphabetically(wb)
    wb.save(filename)
