import os
import sys
import argparse
import logging
from dotenv import load_dotenv
from analyzer import configure_gemini, analyze_pdf
from excel_writer import create_workbook, add_paper_to_workbook, save_workbook

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

ERROR_LOG_FILE = "error_log.txt"

def log_error(filename, error_msg):
    """Logs error to a specific text file."""
    timestamp = logging.Formatter('%(asctime)s').format(logging.LogRecord(None, None, None, None, None, None, None))
    with open(ERROR_LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] Error processing {filename}: {error_msg}\n")

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF scientific papers using Gemini 1.5 Flash.")
    parser.add_argument("folder", help="Path to the folder containing PDF files")
    args = parser.parse_args()

    input_folder = args.folder

    if not os.path.exists(input_folder):
        logging.error(f"The directory {input_folder} does not exist.")
        sys.exit(1)

    # Configure Gemini
    try:
        configure_gemini()
    except Exception as e:
        logging.error(f"Configuration failed: {e}")
        sys.exit(1)

    # Find PDFs
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logging.warning(f"No PDF files found in {input_folder}")
        sys.exit(0)

    logging.info(f"Found {len(pdf_files)} PDF files. Starting analysis...")

    # Initialize Excel Workbook
    wb = create_workbook()
    
    successful_count = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_file)
        try:
            # Analyze
            logging.info(f"Processing: {pdf_file}")
            data = analyze_pdf(pdf_path)
            
            # Write to Excel
            add_paper_to_workbook(wb, data)
            successful_count += 1
            logging.info(f"Successfully processed: {pdf_file}")
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Failed to process {pdf_file}. Error: {error_msg}")
            log_error(pdf_file, error_msg)

    # Save Output
    output_filename = "Paper_Analysis_Results.xlsx"
    # Save in the same directory where script is running, or user specified? 
    # User said "Output (Excel Generation): Create a single Excel file...". 
    # Usually safer to save in the current run directory or the input directory.
    # I'll save it in the current working directory for simplicity as per requirements ("Create a single Excel file named...").
    
    if successful_count > 0:
        save_workbook(wb, output_filename)
        logging.info(f"Analysis complete. Results saved to {output_filename}")
    else:
        logging.warning("No papers were successfully processed. Excel file was not created/saved.")

if __name__ == "__main__":
    main()
