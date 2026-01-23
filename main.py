import os
import sys
import argparse
import logging
from dotenv import load_dotenv

from analyzer import upload_pdf, analyze_pdf_content
from excel_writer import load_or_create_workbook, add_paper_to_workbook, save_workbook
import graph_builder
import reference_manager
import verify_pdfs

from state_manager import StateManager
import file_utils
from google import genai

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
        all_models = list(client.models.list())
        valid_models = []
        exclude_terms = ["embedding", "image", "audio", "tts", "robotics", "computer-use", "gemma"]
        
        for m in all_models:
             name = m.name.lower()
             if "gemini" in name and not any(term in name for term in exclude_terms):
                  valid_models.append(m.name)
        
        valid_models.sort()
        
        if not valid_models:
            print("No models found that support generateContent.")
            sys.exit(1)
            
        print("\nAvailable Models:")
        for idx, name in enumerate(valid_models):
            print(f"{idx + 1}. {name}")
            
        while True:
            try:
                selection = input("\nSelect a model number: ")
                idx = int(selection) - 1
                if 0 <= idx < len(valid_models):
                    selected_model = valid_models[idx]
                    print(f"Selected model: {selected_model}")
                    return selected_model
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a number.")
                
    except Exception as e:
        print(f"Error fetching models: {e}")
        return "gemini-2.5-flash"

def deduplicate_files(input_folder, state_mgr):
    """
    Scans for duplicates.
    Currently DISABLED by user request.
    To enable, uncomment logic here using verify_pdfs and file_utils.
    """
    # logging.info("Running Deduplication Check...")
    # Logic provided by verify_pdfs.scan_and_deduplicate or manual loop
    # using file_utils.safe_move_to_duplicates(filepath, duplicates_dir)
    pass

def process_files(input_folder, output_dir, model_name, state_mgr, wb, excel_file_path):
    """
    Main processing loop.
    1. Scan dir
    2. Check StateManager
    3. Analyze -> Excel -> Atomic Log -> Safe Rename
    """
    error_log_path = os.path.join(output_dir, "error_log.txt")
    
    # Reload/Sync NOT performed here (Disabled per request)
    
    # Get raw files
    raw_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    
    # Filter processed
    pdf_files = []
    for f in raw_files:
        if state_mgr.is_processed(f):
             # logging.debug(f"Skipping {f} (Processed)")
             continue
        pdf_files.append(f)

    if not pdf_files:
        logging.info("No new papers to process.")
        return

    logging.info(f"Queueing {len(pdf_files)} new valid PDF files for analysis...")
    processed_count = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_file)
        
        # Double check state (in case of parallel run or manual change)
        if state_mgr.is_processed(pdf_file):
            continue

        # Calculate Hash
        try:
            file_hash = verify_pdfs.calculate_md5(pdf_path)
            # Duplicate Hash Check (Optional strictness)
            # if state_mgr.is_known_hash(file_hash):
            #     logging.warning(f"Duplicate content detected for {pdf_file}")
            #     # Continue or skip? User asked to disable strict checks.
        except Exception as e:
            logging.error(f"Hash calculation failed for {pdf_file}: {e}")
            file_hash = None # Proceed anyway

        try:
            # --- Phase A: Upload ---
            logging.info(f"Processing Phase A - Upload: {pdf_file}")
            try:
                file_ref = upload_pdf(pdf_path)
            except Exception as e:
                logging.error(f"Upload failed for {pdf_file}: {e}")
                with open(error_log_path, 'a') as ef:
                    ef.write(f"{pdf_file}: Upload Failed: {str(e)}\n")
                continue

            # --- Phase B: Analyze ---
            logging.info(f"Processing Phase B - Analyze: {pdf_file}")
            data = analyze_pdf_content(file_ref, model_name=model_name)
            
            # --- Phase C: Metadata & Citations ---
            logging.info(f"Processing Phase C - Metadata: {pdf_file}")
            # This generates 'proposed_filename' in data
            data = reference_manager.process(data, output_dir, model_name=model_name, pdf_path=pdf_path)

            # --- Phase D: Write to Excel ---
            add_paper_to_workbook(wb, data)
            save_workbook(wb, excel_file_path)
            
            # --- Phase E: ATOMIC LOGGING ---
            # Mark original name as processed immediately
            state_mgr.mark_as_processed(pdf_file, file_hash)
            processed_count += 1
            logging.info(f"Success: {pdf_file} (Log & Hash Updated)")

            # --- Phase F: Safe Renaming ---
            if 'proposed_filename' in data:
                 new_name = data['proposed_filename']
                 # Check strict unique path
                 full_new_path, final_new_name = file_utils.get_unique_filename(input_folder, new_name)
                 
                 # Only rename if different
                 if full_new_path != pdf_path:
                     logging.info(f"Attempting rename: {pdf_file} -> {final_new_name}")
                     if file_utils.safe_rename(pdf_path, full_new_path):
                         logging.info(f"Renamed successfully.")
                         # Atomic update of log for NEW name
                         state_mgr.record_rename(pdf_file, final_new_name, file_hash)
                     else:
                         logging.warning("Rename failed (continuing safely).")

        except Exception as e:
            logging.error(f"Error processing {pdf_file}: {e}")
            state_mgr.mark_as_failed(pdf_file)
            with open(error_log_path, 'a') as ef:
                ef.write(f"{pdf_file}: {str(e)}\n")

    if processed_count > 0:
        logging.info(f"Completed. Processed {processed_count} new papers.")
    else:
        logging.info("Completed batch. No files successfully processed.")

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF scientific papers using Gemini 2.5 Flash.")
    parser.add_argument("folder", help="Path to the folder containing PDF files")
    args = parser.parse_args()

    # Setup Encoding
    sys.stdout.reconfigure(encoding='utf-8')

    # Interactive Model Selection
    model_name = select_model()

    # Path Setup
    input_folder = os.path.abspath(args.folder)
    output_dir = os.path.join(input_folder, "outputs")
    excel_file_path = os.path.join(output_dir, "Paper_Analysis_Results.xlsx")

    if not os.path.exists(input_folder):
        logging.error(f"The directory {input_folder} does not exist.")
        sys.exit(1)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Initialize Components
    state_mgr = StateManager(output_dir)
    wb = load_or_create_workbook(excel_file_path)

    # Deduplication (Placeholder/Disabled)
    deduplicate_files(input_folder, state_mgr)

    # Run Main Loop
    process_files(input_folder, output_dir, model_name, state_mgr, wb, excel_file_path)

    # Generate Knowledge Graph
    try:
        logging.info("Generating Knowledge Graph...")
        graph_builder.update_workbook_with_graph(wb)
        save_workbook(wb, excel_file_path)
        logging.info(f"Final workbook saved with Knowledge Graph to {excel_file_path}")
    except Exception as e:
        logging.error(f"Failed to build Knowledge Graph: {e}")

if __name__ == "__main__":
    main()
