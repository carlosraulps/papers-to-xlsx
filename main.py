import os
import sys
import argparse
import logging
import json
from dotenv import load_dotenv
from analyzer import analyze_pdf, upload_pdf, analyze_pdf_content
from excel_writer import load_or_create_workbook, add_paper_to_workbook, save_workbook
import graph_builder
import reference_manager
import unicodedata
import mimetypes

# Load env variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def load_processed_log(log_path):
    """Loads the processed log from JSON."""
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            return json.load(f)
    return {}

def save_processed_log(log_data, log_path):
    """Saves the processed log to JSON."""
    with open(log_path, 'w') as f:
        json.dump(log_data, f, indent=4, sort_keys=True)

def sanitize_filename(text):
    """Sanitizes text for use in filenames."""
    # Keep only alphanumerics, underscores, hyphens
    return "".join(c for c in text if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')

def rename_pdf(original_path, data):
    """Renames the PDF based on extracted data."""
    # Extract Author, Year, Title
    authors = data.get("Authors", "Unknown")
    if isinstance(authors, list):
         first_author = authors[0].split()[-1] if authors else "Unknown"
    else:
         first_author = authors.split(',')[0].split()[-1] if ',' in authors else authors.split()[-1]

    year = str(data.get("Year", "Unknown"))
    title = data.get("Title", "Untitled")
    
    # Sanitize
    first_author = sanitize_filename(first_author)
    year = sanitize_filename(year)
    short_title = sanitize_filename(title)[:50] # Limit title length
    
    new_filename = f"{first_author}_{year}_{short_title}.pdf"
    new_path = os.path.join(os.path.dirname(original_path), new_filename)
    
    # Handle duplicate names
    counter = 1
    while os.path.exists(new_path) and new_path != original_path:
        new_filename = f"{first_author}_{year}_{short_title}_{counter}.pdf"
        new_path = os.path.join(os.path.dirname(original_path), new_filename)
        counter += 1
        
    os.rename(original_path, new_path)
    return new_filename

from google import genai

def select_model():
    """
    Fetches available models from the API and asks the user to select one.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        sys.exit(1)
        
    client = genai.Client(api_key=api_key)
    
    print("\nFetching available Gemini models...")
    try:
        # List models and filter for generateContent support
        # genai SDK 0.x vs 1.x might differ, but list_models usually returns iter of Model objects
        # We need to check supported_generation_methods or similar if available, or just name filtering
        # The prompt instruction says "look for supported_generation_methods"
        
        all_models = list(client.models.list())
        valid_models = []
        
        exclude_terms = ["embedding", "image", "audio", "tts", "robotics", "computer-use", "gemma"]
        
        for m in all_models:
             # Heuristic filter: Only include Gemini models, exclude specialized/multimodal-only variants
             name = m.name.lower()
             if "gemini" in name and not any(term in name for term in exclude_terms):
                  valid_models.append(m.name)
        
        # Sort for consistency
        valid_models.sort()
        
        if not valid_models:
            print("No models found that support generateContent.")
            sys.exit(1)
            
        print("\nAvailable Models:")
        for idx, name in enumerate(valid_models):
            # name usually comes as "models/gemini-1.5-flash". 
            # We can display it as is.
            print(f"{idx + 1}. {name}")
            
        while True:
            try:
                selection = input("\nSelect a model number: ")
                idx = int(selection) - 1
                if 0 <= idx < len(valid_models):
                    selected_model = valid_models[idx]
                    print(f"Selected model: {selected_model}")
                    # If model name starts with "models/", genai might expect it or not. 
                    # Usually it handles it, but sometimes "gemini-..." is preferred.
                    # We will use the full name returned by API to be safe.
                    return selected_model
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a number.")
                
    except Exception as e:
        print(f"Error fetching models: {e}")
        # Fallback
        fallback = "gemini-2.5-flash"
        print(f"Defaulting to {fallback}")
        return fallback

import verify_pdfs

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF scientific papers using Gemini 2.5 Flash.")
    parser.add_argument("folder", help="Path to the folder containing PDF files")
    args = parser.parse_args()

    # Setup Encoding for Unicode Safety
    sys.stdout.reconfigure(encoding='utf-8')

    # Interactive Model Selection
    model_name = select_model()

    # Resolve paths (Dynamic Output Logic)
    input_folder = os.path.abspath(args.folder)
    output_dir = os.path.join(input_folder, "outputs")
    
    # Define File Paths
    log_file_path = os.path.join(output_dir, "processed_log.json")
    excel_file_path = os.path.join(output_dir, "Paper_Analysis_Results.xlsx")
    error_log_path = os.path.join(output_dir, "error_log.txt")

    if not os.path.exists(input_folder):
        logging.error(f"The directory {input_folder} does not exist.")
        sys.exit(1)

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Created output directory: {output_dir}")

    # Load Memor
    processed_log = load_processed_log(log_file_path)
    
    # --- Sync Step: Recover from Crash ---
    # Check if files in DB but missing from Log
    try:
        db = reference_manager.load_database(output_dir)
        logging.info(f"Syncing logs with {len(db)} database entries...")
        
        recovered_count = 0
        for entry in db:
            # Reconstruct expected filename from metadata
            # Matches logic in reference_manager.process
            authors = entry.get("Authors", "Unknown")
            if isinstance(authors, list):
                 first_author = authors[0].split()[-1] if authors else "Unknown"
            else:
                 first_author = authors.split(',')[0].split()[-1] if ',' in authors else authors.split()[-1]
            
            year = str(entry.get("Year", "0000"))
            title = entry.get("Title", "Untitled")
            
            # Sanitize parts
            first_author = "".join(x for x in first_author if x.isalnum())
            year = "".join(x for x in year if x.isalnum())[:4]
            title = "".join(x for x in title if x.isalnum() or x in " -_")
            title = title[:150]
            
            # Reconstruct Filename
            expected_name = f"{first_author}-{year}-{title}.pdf"
            expected_name = " ".join(expected_name.split()).replace(" ", "_")
            
            # Check if this file exists in input folder
            full_path = os.path.join(input_folder, expected_name)
            
            if os.path.exists(full_path):
                # If exists and NOT in log, add it
                if expected_name not in processed_log:
                    processed_log[expected_name] = "Processed (Recovered)"
                    recovered_count += 1
        
        if recovered_count > 0:
            logging.info(f"Recovered {recovered_count} files from database into processed log.")
            save_processed_log(processed_log, log_file_path)
            
    except Exception as e:
        logging.warning(f"Log sync warning: {e}")
        
    # --- Garbage Collection: Remove Zombies (Log entries not on disk) ---
    logging.info("Running Garbage Collection on logs...")
    zombies = []
    # Create copy of keys to iterate while modifying
    for processed_file in list(processed_log.keys()):
        # Check if file really exists in input_folder
        # Note: processed_log keys are filenames
        full_path = os.path.join(input_folder, processed_file)
        
        # Also check duplicates folder? No, if moved to duplicates, it's "gone" from main processing view.
        # But if we delete it from log, it might get re-processed if moved back?
        # User wants sync: "deleted papers in dir dont do that".
        # So if not in input_folder, remove from log.
        if not os.path.exists(full_path):
             # ZOMBIE RECOVERY logic for Unicode (Wójcik vs Wojcik)
             # The key in JSON might use one normalization, disk another.
             # Let's try normalizing the key to match disk.
             
             # 1. Check if the file is actually there but name is just slightly different encoding
             # List directory and fuzzy match?
             found_fuzzy = False
             
             # Try normalized NFC (standard for MacOS paths sometimes)
             # import unicodedata (Removed to avoid UnboundLocalError)
             norm_key = unicodedata.normalize('NFC', processed_file)
             if os.path.exists(os.path.join(input_folder, norm_key)):
                 found_fuzzy = True
             
             # Try NFD (MacOS often decomposes)
             norm_key_nfd = unicodedata.normalize('NFD', processed_file)
             if os.path.exists(os.path.join(input_folder, norm_key_nfd)):
                 found_fuzzy = True
                 
             if not found_fuzzy:
                 zombies.append(processed_file)
                 del processed_log[processed_file]
                 pass
             else:
                 # It exists, just encoding mismatch. Keep it.
                 pass

    if zombies:
        logging.info(f"Removed {len(zombies)} zombie entries from log (files deleted or moved): {zombies[:3]}...")
        save_processed_log(processed_log, log_file_path)
    else:
        logging.info("Logs are clean (no zombies found).")
        
    # Initialize Excel Workbook (Load existing or create new)
    wb = load_or_create_workbook(excel_file_path)

    # --- Sync Step 2: Excel Sheet Check (Truth) ---
    # Catch "Zombie" files that are in Excel but not in Log
    existing_sheets = set(wb.sheetnames)
    logging.info(f"Syncing logs with {len(existing_sheets)} Excel sheets...")
    
    excel_recovered = 0
    # Create a mapping of likely sheet names for files in input folder
    # This is tricky because sheet names are truncated. 
    # Better strategy: Filter list later based on if we "would" generate a name that exists.
    
    # Actually, let's do it in the loop or pre-calculate. 
    # Let's add the Registry fix here too.
    mimetypes.add_type("application/pdf", ".pdf")

    # --- Pre-processing: Sanitize Filenames ---
    logging.info("Sanitizing filenames...")
    for filename in os.listdir(input_folder):
        if not filename.lower().endswith(".pdf"):
             continue
             
        # Normalize unicode characters to ASCII equivalents (e.g. Wójcik -> Wojcik)
        # NFD decomposition splits characters from their accents
        normalized_name = unicodedata.normalize('NFD', filename)
        # Filter out non-spacing mark characters (accents)
        ascii_name = "".join(c for c in normalized_name if unicodedata.category(c) != 'Mn')
        
        # Replace spaces, double underscores, etc
        new_name = ascii_name.replace(" ", "_").replace("__", "_")
        # Keep dots, hyphens, underscores, alphanumerics
        new_name = "".join(c for c in new_name if c.isalnum() or c in "._-")
        
        if new_name != filename:
            old_p = os.path.join(input_folder, filename)
            new_p = os.path.join(input_folder, new_name)
            
            # COLLISION PROTECTION: Don't overwrite existing files during sanitization
            if os.path.exists(new_p):
                base, ext = os.path.splitext(new_name)
                counter = 1
                while os.path.exists(new_p):
                    new_p = os.path.join(input_folder, f"{base}_{counter}{ext}")
                    counter += 1
                new_name = os.path.basename(new_p)

            try:
                os.rename(old_p, new_p)
                logging.info(f"Sanitized: {filename} -> {new_name}")
            except Exception as e:
                logging.error(f"Could not sanitize {filename}: {e}")
    
    # --- Strict Binary Deduplication (Pre-Flight) ---
    logging.info("Running Strict Binary Deduplication...")
    # This ensures duplicates are moved BEFORE we even look at the log or start processing
    # Using verify_pdfs.scan_and_deduplicate which we already improved?
    # Actually, the user asked for a specific "deduplicate_files" function or logic that runs *before* loop.
    # We can use the existing 'scan_and_deduplicate' from verify_pdfs as it does exactly this:
    # "Scans directory, moves duplicates [based on MD5], and returns list of valid files."
    
    # Reload processed hashes to ensure we respect history? 
    # Actually, scan_and_deduplicate in verify_pdfs currently builds a local hash map of the *current* folder.
    # It doesn't know about historically processed files if they are not in the folder.
    # But that's fine for "current folder hygiene". 
    # For "Check Registry (True Duplicate)", we need to check against 'processed_hashes.json'.
    
    # Let's enhance the pre-flight check to also check against the historical registry.
    
    # Load Registry
    hashes_file_path = os.path.join(output_dir, "processed_hashes.json")
    if os.path.exists(hashes_file_path):
        with open(hashes_file_path, 'r') as f:
            processed_hashes = json.load(f)
    else:
        processed_hashes = {}

    all_pdf_files = []
    
    duplicates_dir = os.path.join(input_folder, "duplicates")
    if not os.path.exists(duplicates_dir):
        os.makedirs(duplicates_dir)

    # 1. Internal Deduplication (files in folder against each other)
    # 2. Historical Deduplication (files in folder against history)
    
    seen_hashes_current_run = {}
    
    raw_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    logging.info(f"Scanning {len(raw_files)} files for binary duplicates...")
    
    for filename in raw_files:
        filepath = os.path.join(input_folder, filename)
        try:
            # MD5 Hash
            file_hash = verify_pdfs.calculate_md5(filepath)
            
            is_duplicate = False
            match_name = ""
            
            # Check History
            if file_hash in processed_hashes:
                 is_duplicate = True
                 match_name = processed_hashes[file_hash]
                 # Wait, if match_name is the SAME file (just processed before), we shouldn't move it!
                 # We only move if it's a *different* filename but same content.
                 # OR if it's the exact same filename, it means it's already analyzed.
                 if match_name == filename:
                     # Same file, already processed. Keep it (it will be skipped by log check later).
                     is_duplicate = False
                 else:
                     # Different filename, same content. True duplicate.
                     logging.warning(f"Duplicate content found (Historic): {filename} == {match_name}")
            
            # Check Current Run (Collision within batch)
            if file_hash in seen_hashes_current_run:
                is_duplicate = True
                match_name = seen_hashes_current_run[file_hash]
                logging.warning(f"Duplicate content found (Current Batch): {filename} == {match_name}")
            
            if is_duplicate:
                # Move to duplicates
                try:
                    shutil.move(filepath, os.path.join(duplicates_dir, filename))
                    logging.info(f" moved to {duplicates_dir}")
                except Exception as e:
                    logging.error(f"Failed to move duplicate {filename}: {e}")
            else:
                # Keep it
                seen_hashes_current_run[file_hash] = filename
                # If it's new to history, add it to history map? 
                # No, only add to history AFTER successful processing.
                all_pdf_files.append(filename)
                
        except Exception as e:
            logging.error(f"Error checking hash for {filename}: {e}")
            # Keep file if check fails? Or skip? Skip to be safe.
            pass

    # Update valid list
    if not all_pdf_files:
        logging.warning("No valid unique PDFs found.")
        if processed_log:
             pass
        sys.exit(0)
        
    # --- Incremental Processing Filter ---
    # Filter out files that are already in the log
    pdf_files = [f for f in all_pdf_files if f not in processed_log and processed_log.get(f) != "Failed"]
    
    skipped_count = len(all_pdf_files) - len(pdf_files)
    if skipped_count > 0:
        logging.info(f"Skipping {skipped_count} already processed files.")

    logging.info(f"Queueing {len(pdf_files)} new valid PDF files for analysis...")
    
    processed_count = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_file)
        
        # Hash already calculated but not stored per file variable. 
        # Recalculate for registry update or store in map above?
        # Let's recalculate, it's fast.
        file_hash = verify_pdfs.calculate_md5(pdf_path)

        # Check Memory - Strict Check (Double check by name still useful)
        if pdf_file in processed_log:
            logging.info(f"Skipping {pdf_file} - Already analyzed")
            continue
        
        # Check Memory - Strict Check (Double check by name still useful)
        if pdf_file in processed_log:
            logging.info(f"Skipping {pdf_file} - Already analyzed")
            continue

        try:
             # --- 3. Strict Decoupled Processing Loop ---
            
            # Phase A: Upload (Explicit Open/Close in analyzer.upload_pdf)
            logging.info(f"Probessing Phase A - Upload: {pdf_file}")
            try:
                # This opens, uploads, and CLOSES the file handle immediately.
                file_ref = upload_pdf(pdf_path)
            except Exception as e:
                logging.error(f"Upload failed for {pdf_file}: {e}")
                # Log error and skip entire file
                with open(error_log_path, 'a') as ef:
                    ef.write(f"{pdf_file}: Upload Failed: {str(e)}\n")
                continue

            # Phase B: Analyze (Remote API only, no local file access)
            logging.info(f"Processing Phase B - Analyze: {pdf_file}")
            data = analyze_pdf_content(file_ref, model_name=model_name)
            
            # Phase C: Metadata & Citations (Pure data processing, no rename)
            logging.info(f"Processing Phase C - Metadata: {pdf_file}")
            # reference_manager.process now returns 'proposed_filename' without touching disk
            data = reference_manager.process(data, output_dir, model_name=model_name, pdf_path=pdf_path)

            # Phase D: Write to Excel (The Core Job)
            add_paper_to_workbook(wb, data)
            save_workbook(wb, excel_file_path)
            
            # Phase E: ATOMIC SUCCESS: Mark as Processed immediately
            processed_log[pdf_file] = "Processed" 
            save_processed_log(processed_log, log_file_path)
            
            # Update Hash Registry
            processed_hashes[file_hash] = pdf_file
            with open(hashes_file_path, 'w') as f:
                json.dump(processed_hashes, f, indent=4)
            
            processed_count += 1
            logging.info(f"Success: {pdf_file} (Log & Hash Updated)")

            # Phase F: Renaming (The "Nice to Have" Step, separate Phase)
            if 'proposed_filename' in data:
                 new_name = data['proposed_filename']
                 new_full_path = os.path.join(input_folder, new_name)
                 
                 # Handle Collisions (Robust Renaming) - Re-implement collision logic here since ref_manager is stateless
                 if os.path.exists(new_full_path) and new_full_path != pdf_path:
                     counter = 2
                     original_base, ext = os.path.splitext(new_name)
                     while os.path.exists(new_full_path) and new_full_path != pdf_path:
                         new_name = f"{original_base}_v{counter}{ext}"
                         new_full_path = os.path.join(input_folder, new_name)
                         counter += 1
                 
                 if new_full_path != pdf_path:
                     try:
                         # os.rename uses string paths, perfectly safe vs "closed file"
                         os.rename(pdf_path, new_full_path)
                         logging.info(f"Renamed: {pdf_file} -> {new_name}")
                         
                         # Update Log & Registry to track new name
                         del processed_log[pdf_file]
                         processed_log[new_name] = "Processed"
                         save_processed_log(processed_log, log_file_path)
                         
                         processed_hashes[file_hash] = new_name
                         with open(hashes_file_path, 'w') as f:
                             json.dump(processed_hashes, f, indent=4)
                             
                     except OSError as rename_error:
                        # Catch "I/O operation on closed file" or file permissions
                        logging.warning(f"Renaming Warning for {pdf_file}: {rename_error}")
                        with open(error_log_path, 'a') as ef:
                            ef.write(f"{pdf_file} (Rename Warning): {str(rename_error)}\n")
            
        except Exception as e:
            logging.error(f"Error processing {pdf_file}: {e}")
            with open(error_log_path, 'a') as ef:
                ef.write(f"{pdf_file}: {str(e)}\n")


            
    if processed_count == 0:
        logging.info("No new papers to process.")
        # Ensure dashboard is up to date and sheets are sorted
        save_workbook(wb, excel_file_path)
    else:
        logging.info(f"Completed. Processed {processed_count} new papers.")

    # Generate Knowledge Graph
    try:
        logging.info("Generating Knowledge Graph...")
        graph_builder.update_workbook_with_graph(wb)
        # Final Save
        save_workbook(wb, excel_file_path)
        logging.info(f"Final workbook saved with Knowledge Graph to {excel_file_path}")
    except Exception as e:
        logging.error(f"Failed to build Knowledge Graph: {e}")
        pass

if __name__ == "__main__":
    main()
