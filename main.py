import os
import sys
import argparse
import logging
import json
from dotenv import load_dotenv
from analyzer import analyze_pdf
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
    
    # --- PDF Verification & Deduplication Step ---
    # Replaces simple os.listdir
    logging.info("Running PDF Verification and Deduplication...")
    all_pdf_files = verify_pdfs.scan_and_deduplicate(input_folder)
    
    if not all_pdf_files:
        logging.warning(f"No valid PDF files found in {input_folder} (others may be duplicates or corrupt)")
        # Even if no PDFs, we might want to save the empty workbook or just exit
        if processed_log:
             pass
        sys.exit(0)

    # --- Incremental Processing Filter ---
    # Filter out files that are already in the log
    pdf_files = [f for f in all_pdf_files if f not in processed_log and processed_log.get(f) != "Failed"]
    
    skipped_count = len(all_pdf_files) - len(pdf_files)
    if skipped_count > 0:
        logging.info(f"Skipping {skipped_count} already processed files.")

    # Load Processed Hashes
    hashes_file_path = os.path.join(output_dir, "processed_hashes.json")
    if os.path.exists(hashes_file_path):
        with open(hashes_file_path, 'r') as f:
            processed_hashes = json.load(f)
    else:
        processed_hashes = {}

    logging.info(f"Scanning {len(pdf_files)} new valid PDF files in {input_folder}...")
    
    processed_count = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_file)
        
        # --- Content-Based Deduplication (MD5) ---
        try:
            # 1. Calculate Hash
            file_hash = verify_pdfs.calculate_md5(pdf_path)
            
            # 2. Check Registry (True Duplicate)
            if file_hash in processed_hashes:
                existing_file = processed_hashes[file_hash]
                logging.warning(f"Skipping {pdf_file}: Content matches {existing_file} (True Duplicate)")
                
                # Move to duplicates
                duplicates_dir = os.path.join(input_folder, "duplicates")
                if not os.path.exists(duplicates_dir):
                    os.makedirs(duplicates_dir)
                    
                try:
                    import shutil
                    shutil.move(pdf_path, os.path.join(duplicates_dir, pdf_file))
                    logging.info(f"Moved duplicate to {duplicates_dir}")
                except Exception as e:
                    logging.error(f"Failed to move duplicate: {e}")
                
                continue
                
        except Exception as e:
             logging.error(f"Error calculating hash for {pdf_file}: {e}")
             continue
        
        # Check Memory - Strict Check (Double check by name still useful)
        if pdf_file in processed_log:
            logging.info(f"Skipping {pdf_file} - Already analyzed")
            continue

        try:
             # --- 3. Decoupled Processing Loop ---
            
            # A. Upload & Analyze
            logging.info(f"Processing: {pdf_file}")
            data = analyze_pdf(pdf_path, model_name=model_name)
            
            # B. Analyze & Rename Logic (Decoupled)
            # We don't want to rely on side-effects inside reference_manager.process potentially crashing
            # But ref_manager does citations AND renaming. 
            # Let's let it handle it, but we've improved it to be robust (collisions -> _v2).
            
            logging.info(f"Verifying citations and renaming: {pdf_file}")
            data = reference_manager.process(data, output_dir, model_name=model_name, pdf_path=pdf_path)
            
            # C. Update State if Renamed
            if 'pdf_renamed' in data:
                 # Logic for "Collision (Same author/year, different paper)" is handled by reference_manager's _v2 logic
                 new_name = data['pdf_renamed']
                 # Verify it actually exists
                 new_full_path = os.path.join(input_folder, new_name)
                 
                 if os.path.exists(new_full_path):
                     pdf_path = new_full_path
                     pdf_file = new_name 
                     logging.info(f"State updated: Current file is now {pdf_file}")
                 else:
                     logging.error(f"Rename reported success but file missing: {new_full_path}")

            # D. Write to Excel
            add_paper_to_workbook(wb, data)
            save_workbook(wb, excel_file_path)
            
            # E. Atomic Log Update
            processed_log[pdf_file] = "Processed" 
            save_processed_log(processed_log, log_file_path)
            
            # F. Update Hash Registry
            processed_hashes[file_hash] = pdf_file
            with open(hashes_file_path, 'w') as f:
                json.dump(processed_hashes, f, indent=4)
            
            processed_count += 1
            logging.info(f"Success: {pdf_file} (Log & Hash Updated)")
            
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
