import os
import time
import json
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def configure_gemini():
    """Configures the Gemini API using the key from environment."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables.")
    genai.configure(api_key=api_key)

def analyze_pdf(pdf_path):
    """
    Uploads a PDF to Gemini and extracts analysis data in JSON format.
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')

        logging.info(f"Uploading file: {pdf_path}")
        sample_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
        
        # Verify upload
        while sample_file.state.name == "PROCESSING":
            logging.info("Processing file...")
            time.sleep(2)
            sample_file = genai.get_file(sample_file.name)
            
        if sample_file.state.name == "FAILED":
             raise ValueError("File upload failed.")

        logging.info(f"File uploaded successfully: {sample_file.name}")

        prompt = """
        You are a scientific paper analysis expert. 
        Analyze the attached PDF and extract the following information. 
        Return the result strictly as a valid JSON object. Do not include markdown formatting (like ```json ... ```) in the response, just the raw JSON string.

        The JSON structure must be keys corresponding to the specific questions below:

        1.  **Title**: The full title of the paper.
        2.  **Authors**: List of authors.
        3.  **Journal**: Name of the journal/conference.
        4.  **Volume**: Volume info if available (or "N/A").
        5.  **Pages**: Page range (or "N/A").
        6.  **Year**: Publication year.
        7.  **DOI**: DOI string (or "N/A").
        8.  **Central Problem**: The scientific/technical problem addressed.
        9.  **Central Hypothesis**: The primary theoretical assumption.
        10. **Central Objective**: Main goal based on hypothesis.
        11. **Central Independent Variables**: The variables manipulated or considered causes (X).
        12. **Central Dependent Variables**: The variables measured or considered effects (Y).
        13. **Methodology & Tools**: How X/Y are measured/calculated (brief summary).
        14. **Central Result**: Key finding of the study.
        15. **Central Conclusion**: Main conclusion, specifically relating back to the hypothesis.
        """

        response = model.generate_content(
            [sample_file, prompt],
            generation_config={"response_mime_type": "application/json"}
        )

        # Cleanup file after use to save storage/quota (optional, but good practice)
        # genai.delete_file(sample_file.name) 

        return json.loads(response.text)

    except Exception as e:
        logging.error(f"Error extracting data from {pdf_path}: {e}")
        raise e
