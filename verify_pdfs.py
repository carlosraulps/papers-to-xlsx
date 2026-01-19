import os
import hashlib
import logging
import shutil
import pypdf

def calculate_file_hash(filepath):
    """Calculates SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read encoded data in blocks
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def verify_pdf_integrity(filepath):
    """
    Checks if PDF is readable and contains text.
    Returns: (is_valid, reason)
    """
    try:
        reader = pypdf.PdfReader(filepath)
        if len(reader.pages) == 0:
             return False, "Empty PDF"
             
        # Check for text content specifically
        text_content = ""
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    text_content += text
            except:
                pass
        
        if len(text_content.strip()) < 50: # Arbitrary threshold for "scanned/image only"
             return False, "Scanned or Image-only (No Text Extracted)"
             
        return True, "Valid"
        
    except Exception as e:
        return False, f"Corrupt: {str(e)}"

def scan_and_deduplicate(db_dir, duplicates_dir_name="duplicates"):
    """
    Scans directory, moves duplicates, and returns list of valid files.
    """
    logging.info("Starting PDF verification and deduplication...")
    
    seen_hashes = {}
    valid_files = []
    
    duplicates_dir = os.path.join(db_dir, duplicates_dir_name)
    if not os.path.exists(duplicates_dir):
        os.makedirs(duplicates_dir)

    files = [f for f in os.listdir(db_dir) if f.strip().lower().endswith('.pdf')]
    
    for filename in files:
        filepath = os.path.join(db_dir, filename)
        
        # 1. Integrity Check
        is_valid, reason = verify_pdf_integrity(filepath)
        if not is_valid:
            logging.warning(f"File {filename} failed integrity check: {reason}")
            # Optionally move corrupt files too? User said "flag it... and log"
            # Maybe move to "corrupt" folder to keep main clean?
            # User request: "If it raises an error, flag it as Corrupt... If it opens but 0 text... flag as Scanned"
            # It implies skipping. 
            continue

        # 2. Hash & Deduplicate
        file_hash = calculate_file_hash(filepath)
        
        if file_hash in seen_hashes:
            original_file = seen_hashes[file_hash]
            logging.warning(f"Duplicate found: {filename} is same as {original_file}")
            
            # Move to duplicates
            try:
                shutil.move(filepath, os.path.join(duplicates_dir, filename))
                logging.info(f"Moved duplicate {filename} to {duplicates_dir}")
            except Exception as e:
                logging.error(f"Failed to move duplicate {filename}: {e}")
                
        else:
            seen_hashes[file_hash] = filename
            valid_files.append(filename)
            
    logging.info(f"Verification complete. Found {len(valid_files)} valid unique PDFs.")
    return valid_files
