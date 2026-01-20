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

def upload_pdf(pdf_path):
    """
    Uploads a PDF to Gemini using SDK's path parameter.
    The SDK manages the file handle internally.
    Returns: file_ref (API object)
    """
    client = get_client()
    logging.info(f"Uploading file: {pdf_path}")
    
    # Let SDK handle file I/O - it will auto-detect MIME type from .pdf extension
    file_ref = client.files.upload(path=pdf_path)
    
    # Wait for processing
    while file_ref.state.name == "PROCESSING":
        logging.info("Processing file...")
        time.sleep(2)
        file_ref = client.files.get(name=file_ref.name)
        
    if file_ref.state.name == "FAILED":
        raise ValueError("File upload failed.")

    logging.info(f"File uploaded successfully: {file_ref.name}")
    return file_ref

def analyze_pdf_content(file_ref, model_name="gemini-2.5-flash"):
    """
    Analyzes an already uploaded file reference.
    Returns: JSON data
    """
    client = get_client()
    
    prompt = """
    You are a scientific paper analysis expert. 
    Analyze the attached PDF and extract the following information. 
    Return the result strictly as a valid JSON object. Do not include markdown formatting (like ```json ... ```) in the response, just the raw JSON string.

    The JSON structure must be keys corresponding to the specific questions below:

    1.  **Title**: The full title of the paper. Extract the title EXACTLY as it appears on the first page of the PDF. Do NOT update the title based on external search results unless the PDF title is missing. If it is a preprint, keep the preprint title.
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
    17. **Glossary**: A list of 3-5 complex terms found in the paper with brief definitions. 
        Format strictly as a JSON list of objects: [{"Term": "Term1", "Definition": "Def1"}, {"Term": "Term2", "Definition": "Def2"}].
        Do NOT use markdown tables or other formats.
    """

    # Generate Content with JSON response schema if supported, or text and parse.
    config = types.GenerateContentConfig(
        response_mime_type="application/json"
    )

    # Retry Logic
    max_retries = 2
    attempt = 0
    
    while attempt <= max_retries:
        logging.info(f"Analysis attempt {attempt + 1}")
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[file_ref, prompt],
                config=config
            )
            
            # Strip markdown if present
            response_text = response.text.strip()
            if response_text.startswith("```"):
                # Remove ```json and ``` wrappers
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(response_text)
            
            # Validation Logic
            short_summary = data.get("Short Summary", "")
            glossary = data.get("Glossary", [])
            
            is_valid = True
            missing_fields = []
            
            # Validate Short Summary
            if not short_summary or str(short_summary).strip().lower() in ["n/a", "none"] or len(str(short_summary)) < 10:
                    is_valid = False
                    missing_fields.append("Short Summary")
            
            # Validate Glossary
            glossary_valid = False
            if isinstance(glossary, list) and len(glossary) > 0:
                    glossary_valid = True
            
            if not glossary_valid:
                is_valid = False
                missing_fields.append("Glossary")
                
            if is_valid:
                    return data
                    
            logging.warning(f"Validation failed for {missing_fields}. Retrying...")
            
            # Update prompt for retry
            retry_instruction = f"\\n\\nIMPORTANT: The previous extraction failed for fields: {missing_fields}. You MUST extract valid content for these. Do NOT return N/A. For Glossary, if definitions are hard to find, provide just the Key Terms with simple definitions."
            prompt += retry_instruction
            
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
        
        attempt += 1

    # If failed after retries, return what we have or try to patch Glossary
    if not data.get("Glossary"):
            data["Glossary"] = [{"Term": "N/A", "Definition": "Extraction Failed"}]
            
    return data

def analyze_pdf(pdf_path, model_name="gemini-2.5-flash"):
    """
    Wrapper for backward compatibility.
    """
    file_ref = upload_pdf(pdf_path)
    return analyze_pdf_content(file_ref, model_name=model_name)



