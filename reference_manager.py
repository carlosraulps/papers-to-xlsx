import os
import json
import logging
from google import genai
from google.genai import types

def get_citations_dir(output_dir):
    return os.path.join(output_dir, "citations")

def get_db_file(output_dir):
    return os.path.join(get_citations_dir(output_dir), "references_database.json")

def ensure_citations_dir(output_dir):
    citations_dir = get_citations_dir(output_dir)
    if not os.path.exists(citations_dir):
        os.makedirs(citations_dir)

def load_database(output_dir):
    ensure_citations_dir(output_dir)
    db_file = get_db_file(output_dir)
    if os.path.exists(db_file):
        try:
            with open(db_file, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_database(db, output_dir):
    ensure_citations_dir(output_dir)
    db_file = get_db_file(output_dir)
    with open(db_file, 'w') as f:
        json.dump(db, f, indent=4)

def check_missing_data(metadata):
    """Checks if critical citation fields are missing or 'N/A'."""
    critical_keys = ["DOI", "Volume", "Pages", "Journal", "Year"]
    missing = []
    for key in critical_keys:
        val = metadata.get(key, "N/A")
        if not val or val == "N/A" or val == "Unknown":
            missing.append(key)
    return missing

def get_grounding_tool():
    # Tools definition for google-genai SDK
    return types.Tool(
        google_search=types.GoogleSearch() 
    )

def enrich_with_grounding(metadata, missing_keys, model_name="gemini-2.5-flash"):
    """
    Uses Gemini with Google Search to find missing citation details.
    """
    if not missing_keys:
        return metadata

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logging.warning("No API Key found, skipping grounding.")
        return metadata

    try:
        client = genai.Client(api_key=api_key)

        title = metadata.get("Title", "")
        authors = metadata.get("Authors", "")
        if isinstance(authors, list):
            authors = ", ".join(authors)

        prompt = f"""
        I have a paper with the following incomplete metadata:
        Title: {title}
        Authors: {authors}
        
        The following fields are missing or incomplete: {', '.join(missing_keys)}.
        
        Please search for this specific paper to find the official valid publication details.
        Return ONLY a JSON object with the corrected/found values for the missing fields, and any other corrected fields if the original was wrong.
        Format: {{ "DOI": "...", "Volume": "...", "Pages": "...", "Journal": "...", "Year": "..." }}
        """
        
        logging.info(f"Grounding: Searching for missing info: {missing_keys}")
        
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[get_grounding_tool()],
                response_modalities=["TEXT"] 
            )
        )
        
        # Parse response
        # Typically the model returns text with the answer. We need to extract the JSON.
        text = response.text
        # Clean markdown
        if text:
            text = text.replace("```json", "").replace("```", "").strip()
            try:
                found_data = json.loads(text)
                # Merge found data
                for k, v in found_data.items():
                    if v and v != "N/A":
                        metadata[k] = v
                        logging.info(f"Grounding: Updated {k} -> {v}")
            except json.JSONDecodeError:
                logging.warning(f"Grounding returned invalid JSON: {text}")

    except Exception as e:
        logging.error(f"Grounding failed: {e}")
    
    return metadata

def export_bibtex(db, output_dir):
    """Exports database to library.bib"""
    filename = os.path.join(get_citations_dir(output_dir), "library.bib")
    with open(filename, 'w') as f:
        for ref in db:
            # Create a simple citation key: AuthorYearTitleWord
            authors = ref.get("Authors", [])
            if isinstance(authors, list):
                first_author = authors[0].split()[-1] if authors else "Unknown"
            else:
                 first_author = authors.split(',')[0].split()[-1]
            
            year = str(ref.get("Year", "0000"))
            title = ref.get("Title", "").split()[0] if ref.get("Title") else "Untitled"
            
            key = f"{first_author}{year}{title}"
            key = "".join(x for x in key if x.isalnum())
            
            f.write(f"@article{{{key},\n")
            f.write(f"  author = {{{ref.get('Authors', 'Unknown')}}},\n")
            f.write(f"  title = {{{ref.get('Title', 'Unknown')}}},\n")
            f.write(f"  journal = {{{ref.get('Journal', 'Unknown')}}},\n")
            f.write(f"  year = {{{year}}},\n")
            f.write(f"  volume = {{{ref.get('Volume', 'N/A')}}},\n")
            f.write(f"  pages = {{{ref.get('Pages', 'N/A')}}},\n")
            f.write(f"  doi = {{{ref.get('DOI', 'N/A')}}}\n")
            f.write("}\n\n")

def export_apa(db, output_dir):
    """Exports to APA text file."""
    filename = os.path.join(get_citations_dir(output_dir), "references_apa.txt")
    with open(filename, 'w') as f:
        for ref in db:
            # Very basic APA approximation
            authors = ref.get("Authors", "Unknown")
            if isinstance(authors, list):
                authors = ", ".join(authors)
            year = ref.get("Year", "n.d.")
            title = ref.get("Title", "Untitled")
            journal = ref.get("Journal", "Unknown Journal")
            volume = ref.get("Volume", "")
            pages = ref.get("Pages", "")
            doi = ref.get("DOI", "")
            
            entry = f"{authors} ({year}). {title}. {journal}"
            if volume:
                entry += f", {volume}"
            if pages:
                entry += f", {pages}"
            entry += "."
            if doi and doi != "N/A":
                entry += f" https://doi.org/{doi}"
            f.write(entry + "\n\n")

def export_aps(db, output_dir):
    """Exports to APS text file."""
    filename = os.path.join(get_citations_dir(output_dir), "references_aps.txt")
    with open(filename, 'w') as f:
        for ref in db:
            # Basic APS: Author, Journal Volume, Page (Year).
            authors = ref.get("Authors", "Unknown")
            if isinstance(authors, list):
                # APS often uses first author et al or comma sep.
                authors = ", ".join(authors) # Simplified
            
            journal = ref.get("Journal", "")
            volume = ref.get("Volume", "")
            pages = ref.get("Pages", "")
            year = ref.get("Year", "")
            
            entry = f"{authors}, {journal} {volume}, {pages} ({year})."
            f.write(entry + "\n")

def process(paper_data, output_dir, model_name="gemini-2.5-flash", pdf_path=None):
    """Main processing function for references."""
    # 1. Extract Metadata specific for citations
    metadata = {k: paper_data.get(k, "N/A") for k in ["Title", "Authors", "Journal", "Volume", "Pages", "Year", "DOI"]}
    
    # 2. Check for missing info
    missing = check_missing_data(metadata)
    
    # 3. Enrich if missing
    if missing:
        logging.info(f"Missing citation info for {metadata.get('Title','Unknown')}: {missing}")
        metadata = enrich_with_grounding(metadata, missing, model_name)
        # Update original paper_data with enriched info? 
        # Yes, beneficial for Excel too.
        for k, v in metadata.items():
            paper_data[k] = v
    
    # 4. Save to DB
    db = load_database(output_dir)
    # Check if exists (by title?) - prevent dupes
    current_title = metadata.get("Title", "").lower()
    exists = False
    for i, item in enumerate(db):
        if item.get("Title", "").lower() == current_title:
            db[i] = metadata # Update
            exists = True
            break
    if not exists:
        db.append(metadata)
    
    save_database(db, output_dir)
    
    # 5. Export all
    export_bibtex(db, output_dir)
    export_apa(db, output_dir)
    export_aps(db, output_dir)
    
    # 6. Rename PDF
    if pdf_path and os.path.exists(pdf_path):
        try:
            authors = paper_data.get("Authors", "Unknown")
            if isinstance(authors, list):
                 first_author = authors[0].split()[-1] if authors else "Unknown"
            else:
                 first_author = authors.split(',')[0].split()[-1] if ',' in authors else authors.split()[-1]
            
            year = str(paper_data.get("Year", "0000"))
            title = paper_data.get("Title", "Untitled")
            
            # Sanitize
            first_author = "".join(x for x in first_author if x.isalnum())
            year = "".join(x for x in year if x.isalnum())[:4]
            title = "".join(x for x in title if x.isalnum() or x in " -_")
            title = title[:150] # Limit length
            
            new_filename = f"{first_author}-{year}-{title}.pdf"
            # Cleanup multiple spaces
            new_filename = " ".join(new_filename.split())
            new_filename = new_filename.replace(" ", "_")
            
            new_path = os.path.join(os.path.dirname(pdf_path), new_filename)
            
            # Handle Collisions (Robust Renaming)
            # If target exists and it's NOT the current file
            counter = 2
            while os.path.exists(new_path) and new_path != pdf_path:
                 name_part, ext = os.path.splitext(new_filename)
                 # Check if name_part already has a version suffix? Simpler just to append.
                 new_filename = f"{name_part}_v{counter}{ext}"
                 new_path = os.path.join(os.path.dirname(pdf_path), new_filename)
                 counter += 1
            
            if new_path != pdf_path:
                os.rename(pdf_path, new_path)
                logging.info(f"Renamed PDF to: {new_filename}")
                paper_data['pdf_renamed'] = new_filename # Track change
        except Exception as e:
            logging.error(f"Failed to rename PDF: {e}")

    return paper_data
