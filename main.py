import os
import sys
import argparse
import logging
import json
from dotenv import load_dotenv
from analyzer import configure_gemini, analyze_pdf
from excel_writer import load_or_create_workbook, add_paper_to_workbook, save_workbook

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

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF scientific papers using Gemini 1.5 Flash.")
    parser.add_argument("folder", help="Path to the folder containing PDF files")
    args = parser.parse_args()

    input_folder = args.folder

    if not os.path.exists(input_folder):
        logging.error(f"The directory {input_folder} does not exist.")
        sys.exit(1)

    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Configure Gemini
    try:
        configure_gemini()
    except Exception as e:
        logging.error(f"Configuration failed: {e}")
        sys.exit(1)

    # Load Memory
    processed_log = load_processed_log()
    
    # Initialize Excel Workbook (Load existing or create new)
    wb = load_or_create_workbook(FULL_EXCEL_PATH)
    
    # Find PDFs
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logging.warning(f"No PDF files found in {input_folder}")
        sys.exit(0)

    logging.info(f"Scanning {len(pdf_files)} PDF files...")
    
    processed_count = 0

    for pdf_file in pdf_files:
        # Check Memory
        if pdf_file in processed_log:
            logging.info(f"Skipping {pdf_file} (Already processed as {processed_log[pdf_file]})")
            continue

        pdf_path = os.path.join(input_folder, pdf_file)
        
        try:
            # Analyze
            logging.info(f"Processing: {pdf_file}")
            data = analyze_pdf(pdf_path)
            
            # Write to Excel
            add_paper_to_workbook(wb, data)
            save_workbook(wb, FULL_EXCEL_PATH) # Save progress immediately
            
            # Rename File
            new_filename = rename_pdf(pdf_path, data)
            logging.info(f"Renamed {pdf_file} to {new_filename}")
            
            # Update Memory
            processed_log[new_filename] = "Processed" # Track result name
            # Also track original name if different, to avoid loop if script restarts before full completion?? 
            # Actually, we renamed it, so the file 'pdf_file' no longer exists in the folder for next run.
            # But if we strictly track 'processed files', we should maybe track the rename.
            # The prompt says: "Update the 'memory' to reflect this new filename so it isn't treated as a new file next time."
            # If we renamed it, next time we list dir, we will find 'new_filename'. 
            # If 'new_filename' is in log, we skip.
            
            save_processed_log(processed_log)
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
    else:
        logging.info(f"Completed. Processed {processed_count} new papers.")

if __name__ == "__main__":
    main()
