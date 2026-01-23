# Project Context: Scientific Paper Analysis Tool

## Overview
This project is an automated pipeline for analyzing scientific PDFs using Google's **Gemini Flash** model. It extracts structured metadata (e.g., hypothesis, methodology, results), manages citations, and visualizes connections between papers. The tool is designed to assist researchers by creating a comprehensive Excel dashboard and a knowledge graph from a collection of PDF papers.

## Key Features
*   **AI Extraction**: Utilizes Gemini Flash to parse PDFs and extract key scientific insights (Hypothesis, Variables, Results, etc.).
*   **Excel Dashboard**: Generates a `Paper_Analysis_Results.xlsx` file with:
    *   **Knowledge Graph**: A visual network of papers and concepts.
    *   **Dashboard**: A clickable Table of Contents with summaries.
    *   **Individual Sheets**: Detailed analysis for each paper.
*   **Citation Management**: Validates and enriches citation data using **Google Search Grounding**. Exports to BibTeX, APA, and APS formats.
*   **File Organization**: Automatically renames PDF files to a standard `Author_Year_Title.pdf` format.
*   **Smart Processing**: Tracks processed files in `processed_log.json` to avoid redundancy.

## Architecture

### Core Modules
*   **`main.py`**: The entry point. Orchestrates the high-level flow: scanning, analysis, Excel write, atomic logging, and graph generation.
*   **`state_manager.py`**: Encapsulates all JSON logging and state tracking (`processed_log.json` and `processed_hashes.json`).
*   **`file_utils.py`**: Safe file operations, including path normalization and robust renaming.
*   **`analyzer.py`**: Gemini API interface. Handles file uploads and structured JSON extraction.
*   **`excel_writer.py`**: Manages all Excel operations and formatting.
*   **`reference_manager.py`**: Citation enrichment and formatting.
*   **`graph_builder.py`**: Generates the Knowledge Graph.
*   **`verify_pdfs.py`**: PDF integrity and hashing.

### Data Flow
1.  **Input**: Folder containing PDF files.
2.  **State Check**: `main.py` -> `state_manager.py` (Check if already processed).
3.  **Analysis**: `main.py` -> `analyzer.py` (Gemini API) -> Metadata.
4.  **Storage**: `main.py` -> `excel_writer.py` -> Update Excel.
5.  **Logging**: `main.py` -> `state_manager.py` -> **Atomic update** of log.
6.  **Organization**: `main.py` -> `file_utils.py` -> Safe rename.
7.  **Visualization**: `main.py` -> `graph_builder.py` -> Update Knowledge Graph.

## Setup & Installation

### Prerequisites
*   Python 3.9+
*   Google Cloud API Key (with access to Gemini Flash)

### Installation
1.  **Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
2.  **Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configuration**:
    Create a `.env` file in the root directory:
    ```env
    GOOGLE_API_KEY=your_api_key_here
    ```

## Usage

Run the tool by pointing it to a directory containing PDFs:

```bash
python main.py /path/to/pdf_folder
```

### Outputs
*   **`papers_analysis_output/Paper_Analysis_Results.xlsx`**: The primary output file.
*   **`citations/`**: Contains `library.bib`, `references_apa.txt`, and `references_aps.txt`.
*   **`processed_log.json`**: Tracks processed files to enable incremental runs.
*   **Renamed PDFs**: Files in the source directory are renamed to `Author_Year_Title.pdf`.

## Development Conventions
*   **Logging**: All major actions are logged to stdout and `processed_log.json`. Errors are logged to `papers_analysis_output/error_log.txt`.
*   **Error Handling**: The pipeline is resilient; if one paper fails, it logs the error and continues to the next.
*   **Conventions**: Code follows standard Python PEP 8 guidelines. Dependencies are managed via `requirements.txt`.
