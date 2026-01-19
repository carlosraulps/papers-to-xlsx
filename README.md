# Scientific Paper Analysis Tool (Gemini-Powered)

Automate the extraction of structured data from scientific PDFs using Google's **Gemini 2.5 Flash**. This tool transforms a chaotic folder of research papers into a structured, publication-quality Excel database, complete with an interactive Knowledge Graph and automated Citation Management.

## 🚀 Key Features

-   **AI-Powered Deep Analysis**: Extracts complex scientific metadata including:
    -   Central Problem, Hypothesis, and Objectives.
    -   Independent/Dependent Variables (X/Y).
    -   Methodology & Tools.
    -   Key Results and Conclusions.
    -   **Short Summaries** and **Glossaries** of technical terms.
-   **Pub-Quality Knowledge Graph**: 
    -   Builds a dynamic NetworkX graph linking papers to technical concepts.
    -   Uses **adjustText** physics simulation to prevent label overlap.
    -   Auto-embedded into the Excel workbook with customizable Obsidian-style dark aesthetics.
-   **Smart Excel Dashboard**:
    -   **Dashboard**: Clickable Table of Contents with summaries and glossary previews.
    -   **Individual Sheets**: Dedicated pages for each paper with structured data.
    -   **Strict Deduplication**: Automatically updates existing sheets instead of creating duplicates.
-   **Robust File Management**:
    -   **Content-Based Deduplication**: Uses MD5 hashing to move identical PDFs to a `duplicates/` folder, even if filenames differ.
    -   **Automated Renaming**: Standardizes files to `Author-Year-ShortTitle.pdf`.
    -   **Safe Grounding**: Uses Google Search to verify citations (DOI, Journal, etc.) without losing the original paper's identity.
    -   **Garbage Collection**: Automatically removes "Zombie" log entries if files are deleted from the disk.

## 📋 Prerequisites

-   **Python 3.9+**
-   A **Google Cloud API Key** with access to Gemini 2.5 Flash.

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/papers-to-xlsx.git
    cd papers-to-xlsx
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    Create a `.env` file in the project root:
    ```env
    GOOGLE_API_KEY=your_actual_api_key_here
    ```

## 💻 Usage

Run the tool by providing the path to your PDF folder:

```bash
python3 main.py /path/to/your/pdf_folder
```

### Advanced: Resetting State
If you want to perform a fresh rebuild without re-downloading PDFs, use the cleanup tool:
```bash
python3 clean_state.py /path/to/your/pdf_folder
```

## 📂 Project Structure

-   **`main.py`**: Orchestrator for the entire pipeline.
-   **`analyzer.py`**: Gemini API interface (File uploads, prompts, and JSON parsing).
-   **`excel_writer.py`**: Handles all Excel logic (Formatting, Dashboard, Sheet Deduplication).
-   **`graph_builder.py`**: Generates the Knowledge Graph using NetworkX and Matplotlib.
-   **`reference_manager.py`**: Manages citations, Google Search Grounding, and PDF renaming.
-   **`verify_pdfs.py`**: Validates PDF integrity and handles MD5-based deduplication.
-   **`clean_state.py`**: Utility to wipe logs and Excel for a clean re-run.

## 📊 Output Organization

The script creates an `outputs/` folder inside your target directory:

```text
Target-Folder/
├── outputs/
│   ├── Paper_Analysis_Results.xlsx  # The main Database
│   ├── processed_log.json           # Progress tracker
│   ├── processed_hashes.json        # Duplicate prevention registry
│   ├── error_log.txt                # Log of any failed attempts
│   └── citations/                   # BibTeX, APA, and APS exports
├── duplicates/                      # Identical files moved here
└── [Renamed-Papers].pdf             # Cleanly organized PDF files
```

## 🛡️ Synchronization Details
The tool includes several "Self-Healing" features:
-   **Zombies**: If you delete a PDF manually, the next run will remove it from the analysis log.
-   **Safe Grounding**: Internet searches will fill in missing DOIs but are restricted from changing the paper's title to prevent hallucinated renaming loops.
-   **Unicode Safety**: Handles accents (e.g., Wójcik) robustly across different operating systems.