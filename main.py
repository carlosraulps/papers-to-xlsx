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

def main():
    parser = argparse.ArgumentParser(description="Analyze PDF scientific papers using Gemini 2.5 Flash.")
    parser.add_argument("folder", help="Path to the folder containing PDF files")
    args = parser.parse_args()

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

    # Load Memory
    processed_log = load_processed_log(log_file_path)
    
    # Initialize Excel Workbook (Load existing or create new)
    wb = load_or_create_workbook(excel_file_path)
    
    # Find PDFs (recursively? No, usually flat, let's keep it flat)
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logging.warning(f"No PDF files found in {input_folder}")
        # Even if no PDFs, we might want to save the empty workbook or just exit
        if processed_log:
             # If we have history but no current files (maybe they were moved?), 
             # just exiting is fine.
             pass
        sys.exit(0)

    logging.info(f"Scanning {len(pdf_files)} PDF files in {input_folder}...")
    
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
            data = analyze_pdf(pdf_path, model_name=model_name)
            
            # Post-Process: Citation Manager (Enrichment)
            logging.info(f"Verifying citations for: {pdf_file}")
            # Pass output_dir to reference manager
            data = reference_manager.process(data, output_dir, model_name=model_name)
            
            # Write to Excel (Sheet addition)
            add_paper_to_workbook(wb, data)
            
            # Rename File (Renaming happens in INPUT folder, as per organization feature)
            new_filename = rename_pdf(pdf_path, data)
            logging.info(f"Renamed {pdf_file} to {new_filename}")
            
            # Update Memory
            processed_log[new_filename] = "Processed" # New name
            processed_log[pdf_file] = "Processed (Renamed)" # Old name
            
            save_processed_log(processed_log, log_file_path)
            
            # Save Workbook (Incremental save)
            save_workbook(wb, excel_file_path)
            
            processed_count += 1
            logging.info(f"Successfully processed and saved: {new_filename}")
            
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Failed to process {pdf_file}. Error: {error_msg}")
            timestamp = logging.Formatter('%(asctime)s').format(logging.LogRecord(None, None, None, None, None, None, None))
            with open(error_log_path, "a") as f:
                 f.write(f"[{timestamp}] Error processing {pdf_file}: {error_msg}\n")

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
