import os
import shutil
import logging

def sanitize_filename(text):
    """Sanitizes text for use in filenames."""
    # Keep only alphanumerics, underscores, hyphens, periods (if needed, but usually stripped)
    # The original function allowed spaces but replaced them later.
    return "".join(c for c in text if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')

def generate_new_filename(data):
    """
    Generates a standard filename from extracted metadata.
    Format: FirstAuthor_Year_ShortTitle.pdf
    """
    authors = data.get("Authors", "Unknown")
    if isinstance(authors, list):
         first_author = authors[0].split()[-1] if authors else "Unknown"
    else:
         # Handle potential string format "Author 1, Author 2" or "Author 1"
         first_author = authors.split(',')[0].split()[-1] if ',' in authors else authors.split()[-1]

    year = str(data.get("Year", "Unknown"))
    title = data.get("Title", "Untitled")
    
    # Sanitize
    first_author = sanitize_filename(first_author)
    year = sanitize_filename(year)
    short_title = sanitize_filename(title)[:50] # Limit title length
    
    return f"{first_author}_{year}_{short_title}.pdf"

def get_unique_filename(folder, filename):
    """
    Returns a unique path for the filename in the given folder.
    If collision exists, appends _v2, _v3 etc.
    """
    base, ext = os.path.splitext(filename)
    full_path = os.path.join(folder, filename)
    
    if not os.path.exists(full_path):
        return full_path, filename
        
    counter = 2
    while True:
        new_name = f"{base}_v{counter}{ext}"
        new_path = os.path.join(folder, new_name)
        if not os.path.exists(new_path):
            return new_path, new_name
        counter += 1

def safe_rename(current_path, new_path):
    """
    Renames a file safely.
    Returns True if successful, False otherwise.
    Does NOT crash on errors.
    """
    try:
        # Strict usage of string paths
        os.rename(current_path, new_path)
        return True
    except Exception as e:
        logging.warning(f"Failed to rename {current_path} to {new_path}: {e}")
        return False

def safe_move_to_duplicates(src_path, duplicates_dir):
    """
    Safely moves a file to the duplicates directory with collision handling.
    """
    filename = os.path.basename(src_path)
    dest_path, dest_name = get_unique_filename(duplicates_dir, filename)
    
    try:
        shutil.move(src_path, dest_path)
        logging.info(f"Moved duplicate to {dest_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to move duplicate {filename}: {e}")
        return False
