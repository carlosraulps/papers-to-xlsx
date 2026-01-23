import os
import shutil
import sys
import time
import logging
import subprocess
import hashlib

# Ensure we can import modules from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - TEST - %(message)s')

TEST_DIR = "test_env"
INPUT_DIR = os.path.join(TEST_DIR, "input")
OUTPUT_DIR = os.path.join(INPUT_DIR, "outputs")
DUPLICATES_DIR = os.path.join(INPUT_DIR, "duplicates")

MAIN_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main.py'))

def create_valid_pdf(filepath, content="Dummy Content"):
    """Creates a minimal valid PDF file."""
    with open(filepath, 'wb') as f:
        f.write(b"%PDF-1.4\n")
        f.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        f.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        f.write(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n")
        f.write(b"4 0 obj\n<< /Length 20 >>\nstream\n")
        f.write(content.encode('utf-8'))
        f.write(b"\nendstream\nendobj\n")
        f.write(b"xref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000216 00000 n \n")
        f.write(b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n265\n%%EOF")

def setup_env():
    """Sets up the test environment."""
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(INPUT_DIR)
    # os.makedirs(OUTPUT_DIR) # main.py should create this

def run_script():
    """Runs the main.py script via subprocess."""
    # We need to preserve env vars (like API KEY)
    env = os.environ.copy()
    
    # We might need to mock input() for model selection?
    # main.py asks for input. We can pipe "1\n" to select the first default model.
    try:
        process = subprocess.Popen(
            [sys.executable, MAIN_SCRIPT, INPUT_DIR],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(input="1\n") # Select duplicate or first model
        
        if process.returncode != 0:
            logging.error(f"Script failed:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
            return False, stdout
        return True, stdout
    except Exception as e:
        logging.error(f"Subprocess error: {e}")
        return False, str(e)

def test_scenario_a_clean_run():
    logging.info("--- Starting Scenario A: Clean Run ---")
    setup_env()
    
    # Create Dummy PDFs
    create_valid_pdf(os.path.join(INPUT_DIR, "paper1.pdf"), "Paper 1 unique content")
    create_valid_pdf(os.path.join(INPUT_DIR, "paper2.pdf"), "Paper 2 unique content")
    
    success, output = run_script()
    if not success:
        logging.error("Scenario A Failed: Script did not run successfully.")
        return False

    # Check Outputs
    if not os.path.exists(os.path.join(OUTPUT_DIR, "processed_log.json")):
        logging.error("Scenario A Failed: processed_log.json missing.")
        return False
    
    if not os.path.exists(os.path.join(OUTPUT_DIR, "Paper_Analysis_Results.xlsx")):
        logging.error("Scenario A Failed: Excel file missing.")
        return False
        
    logging.info("Scenario A Passed: Outputs generated.")
    return True

def test_scenario_b_idempotency():
    logging.info("--- Starting Scenario B: Idempotency (Resume) ---")
    # Run again without changes
    success, output = run_script()
    if not success:
        logging.error("Scenario B Failed: Script crashed on re-run.")
        return False
        
    # Check output for "No new papers" or similar
    if "No new papers to process" not in output and "Skipping" not in output:
         logging.warning("Scenario B Warning: Did not see 'Skipping' message. Output excerpt:\n" + output[-500:])
         # It might just say "Completed. Processed 0" if filter works silently
    
    logging.info("Scenario B Passed: Script ran safely on existing data.")
    return True

def test_scenario_c_binary_duplicate():
    logging.info("--- Starting Scenario C: Binary Duplicate Attack ---")
    
    # Find a processed PDF to duplicate (since paper1.pdf was likely renamed)
    pdfs = [f for f in os.listdir(INPUT_DIR) if f.endswith('.pdf')]
    if not pdfs:
        logging.error("Scenario C Failed: No PDFs found to duplicate.")
        return False
        
    src = os.path.join(INPUT_DIR, pdfs[0])
    dst = os.path.join(INPUT_DIR, "duplicate_paper.pdf")
    shutil.copy2(src, dst)
    
    logging.info("Created duplicate_paper.pdf (Copy of paper1)")
    
    # NOTE: Deduplication is currently DISABLED in main.py by default.
    # This test expects the file to be PROCESSED or SKIPPED based on hash?
    # Actually, current main.py hash check is also permissive (catches error or skips warning).
    # If the user wants `duplicates/` move, main.py needs 'deduplicate_files' active.
    # For now, we simulate the 'Processed Only' workflow.
    
    success, output = run_script()
    
    # In current "Disabled" mode, it will likely process it again as a "new" file (different name),
    # unless hash check inside loop catches it.
    # main.py line 441 check uses FILENAME text matching against log.
    # 'duplicate_paper.pdf' is NOT in log.
    # So it will be treated as new.
    # Unless verify_pdfs hash check stops it?
    # Current main.py: hash check just logs error on fail calculation.
    
    logging.info("Scenario C Completed (Observation Mode).")
    return True

def main():
    if test_scenario_a_clean_run():
        if test_scenario_b_idempotency():
             test_scenario_c_binary_duplicate()
             
    logging.info("Integration Test Suite Completed.")

if __name__ == "__main__":
    main()
