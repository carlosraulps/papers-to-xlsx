import os
import sys
import argparse
import logging
import json
from dotenv import load_dotenv
from analyzer import analyze_pdf
from excel_writer import load_or_create_workbook, add_paper_to_workbook, save_workbook
import graph_builder

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

OUTPUT_DIR = "papers_analysis_output"
LOG_FILE = "processed_log.json"
EXCEL_FILE = "Paper_Analysis_Results.xlsx"
ERROR_LOG_FILE = "error_log.txt"
FULL_EXCEL_PATH = os.path.join(OUTPUT_DIR, EXCEL_FILE)

def load_processed_log():
    """Loads the processed log from JSON."""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_processed_log(log_data):
    """Saves the processed log to JSON."""
    with open(LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=4)

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

import reference_manager

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF scientific papers using Gemini 2.5 Flash.")
    parser.add_argument("folder", help="Path to the folder containing PDF files")
    args = parser.parse_args()

    input_folder = args.folder

    if not os.path.exists(input_folder):
        logging.error(f"The directory {input_folder} does not exist.")
        sys.exit(1)

    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


    # Load Memory
    processed_log = load_processed_log()
    
    # Initialize Excel Workbook (Load existing or create new)
    wb = load_or_create_workbook(FULL_EXCEL_PATH)
    
    # Find PDFs (recursively? No, usually flat, let's keep it flat)
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logging.warning(f"No PDF files found in {input_folder}")
        sys.exit(0)

    logging.info(f"Scanning {len(pdf_files)} PDF files...")
    
    processed_count = 0

    for pdf_file in pdf_files:
        # Check Memory - Strict Check
        if pdf_file in processed_log:
            logging.info(f"Skipping {pdf_file} - Already analyzed")
            continue

        pdf_path = os.path.join(input_folder, pdf_file)
        
        try:
            # Analyze
            logging.info(f"Processing: {pdf_file}")
            data = analyze_pdf(pdf_path)
            
            # Post-Process: Citation Manager (Enrichment)
            logging.info(f"Verifying citations for: {pdf_file}")
            data = reference_manager.process(data)
            
            # Write to Excel (Sheet addition)
            add_paper_to_workbook(wb, data)
            
            # Rename File
            new_filename = rename_pdf(pdf_path, data)
            logging.info(f"Renamed {pdf_file} to {new_filename}")
            
            # Update Memory
            processed_log[new_filename] = "Processed" # New name
            processed_log[pdf_file] = "Processed (Renamed)" # Old name (crucial if file was just renamed but not moved)
            
            save_processed_log(processed_log)
            
            # Save Workbook (Incremental save, includes Dashboard update which calls save)
            # This regenerates dashboard every paper, which is safer but slightly slower.
            # Given user wants "run continuously", safe is better.
            save_workbook(wb, FULL_EXCEL_PATH)
            
            processed_count += 1
            logging.info(f"Successfully processed and saved: {new_filename}")
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Failed to process {pdf_file}. Error: {error_msg}")
            # Move error logging to the main error log in output dir
            error_log_path = os.path.join(OUTPUT_DIR, ERROR_LOG_FILE)
            timestamp = logging.Formatter('%(asctime)s').format(logging.LogRecord(None, None, None, None, None, None, None))
            with open(error_log_path, "a") as f:
                 f.write(f"[{timestamp}] Error processing {pdf_file}: {error_msg}\n")

    if processed_count == 0:
        logging.info("No new papers to process.")
        # We should still save workbook to ensure Dashboard is up to date if manually modified? 
        # Or if this run was just to update dashboard for existing files? 
        # User requirement 2: "When new papers are added... regenerate...". 
        # Only strictly necessary if new papers added. 
        # However, updating dashboard might be useful if the code changed.
        # Let's do a save to refresh dashboard anyway.
        save_workbook(wb, FULL_EXCEL_PATH)
    else:
        logging.info(f"Completed. Processed {processed_count} new papers.")

    # Generate Knowledge Graph
    try:
        logging.info("Generating Knowledge Graph...")
        graph_builder.update_workbook_with_graph(wb)
        # Final Save (Pins sheets in correct order and saves everything)
        save_workbook(wb, FULL_EXCEL_PATH)
        logging.info(f"Final workbook saved with Knowledge Graph to {FULL_EXCEL_PATH}")
    except Exception as e:
        logging.error(f"Failed to build Knowledge Graph: {e}")
        # Try to save anyway if graph failed, to ensure we don't lose previous work?
        # Typically previous work was saved in loop.
        pass

if __name__ == "__main__":
    main()
