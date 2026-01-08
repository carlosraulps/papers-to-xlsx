import os
import time
import json
import logging
from google import genai
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_client():
    """Initializes the Gen AI Client."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables.")
    return genai.Client(api_key=api_key)

def analyze_pdf(pdf_path):
    """
    Uploads a PDF to Gemini and extracts analysis data in JSON format.
    """
    try:
        client = get_client()

        logging.info(f"Uploading file: {pdf_path}")
        # New SDK file upload
        file_ref = client.files.upload(file=pdf_path)
        
        # Verify upload (Active state check)
        # New SDK might handle this differently, but let's check state if available
        # Typically file_ref has metadata.
        while file_ref.state.name == "PROCESSING":
             logging.info("Processing file...")
             time.sleep(2)
             file_ref = client.files.get(name=file_ref.name)
             
        if file_ref.state.name == "FAILED":
             raise ValueError("File upload failed.")

        logging.info(f"File uploaded successfully: {file_ref.name}")

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
        16. **Short Summary**: A concise summary of the paper's core physics in under 200 words.
        17. **Glossary**: A list of 3-5 complex terms found in the paper with brief definitions (as a dictionary or list of objects).
        """

        # Generate Content with JSON response schema if supported, or text and parse.
        # User requested using 'types' for structured JSON config if possible, but also "Return the result strictly as a valid JSON object".
        # We can use response_mime_type="application/json" in config.
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[file_ref, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # Cleanup file? client.files.delete(name=file_ref.name)
        
        return json.loads(response.text)

    except Exception as e:
        logging.error(f"Error extracting data from {pdf_path}: {e}")
        raise e

