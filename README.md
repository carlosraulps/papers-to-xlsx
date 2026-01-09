# Scientific Paper Analysis Tool

Automate the extraction of structured data from scientific PDFs using Google's **Gemini 2.5 Flash**. This tool transforms a folder of research papers into a comprehensive, interlinked Excel database, complete with a knowledge graph and citation manager.

## 🚀 Features

-   **AI-Powered Deep Analysis**: Uses Gemini 2.5 Flash to extract complex scientific details including:
    -   Central Hypothesis, Objectives, and Variables (Independent/Dependent).
    -   Methodology & Tools.
    -   Key Results and Conclusions.
    -   **Short Summaries** and **Glossaries** of technical terms.
-   **Knowledge Graph Visualization**: Automatically builds and embeds a network graph (using NetworkX) linking papers to key concepts, visualizing the connections within your research library.
-   **Smart Excel Dashboard**: Generates a polished Excel workbook (`Paper_Analysis_Results.xlsx`) containing:
    -   **Dashboard**: A clickable Table of Contents with high-level summaries.
    -   **Knowledge Graph**: Visual representation of the research landscape.
    -   **Individual Sheets**: Detailed, structured analysis for every paper.
-   **Citation Manager & Grounding**:
    -   Extracts metadata and verifies it against **Google Search** to ensure accuracy (fixing missing DOIs, Volumes, etc.).
    -   Exports citations to `.bib` (BibTeX), APA, and APS formats in the `citations/` folder.
-   **Automatic Organization**: Renames PDF files to a standardized `Author_Year_Title.pdf` format for easy filesystem navigation.
-   **Incremental Processing**: Uses a `processed_log.json` to track analyzed files, allowing you to add new papers to the folder and run the script to process *only* the new additions.

## 📋 Prerequisites

-   **Python 3.9+**
-   A **Google Cloud API Key** with access to Gemini 2.5 Flash.

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/art-to-xlsx.git
    cd art-to-xlsx
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
    Create a `.env` file in the project root and add your API key:
    ```env
    GOOGLE_API_KEY=your_actual_api_key_here
    ```

## 💻 Usage

Run the main script by providing the path to the folder containing your PDF files:

```bash
python main.py /path/to/your/pdf_folder
```

### Example
```bash
python main.py ./downloads/new_papers
```

The script will:
1.  Scan the folder for `.pdf` files.
2.  Skip files that have already been processed (checked against `processed_log.json`).
3.  Analyze new papers using Gemini.
4.  Verify citations with Google Search.
5.  Update the Excel dashboard and Knowledge Graph.
6.  Rename the original PDF files.

## 📂 Output Structure

After execution, your directory will be organized as follows:

```text
/
├── citations/                  # Exported references
│   ├── library.bib
│   ├── references_apa.txt
│   └── references_aps.txt
├── papers_analysis_output/     
│   ├── Paper_Analysis_Results.xlsx  # The main Excel database
│   └── error_log.txt                # Log of any failed files
└── [Your Source Folder]/
    ├── Smith_2023_Study_on_AI.pdf   # Renamed PDFs
    └── ...
```

## 📄 License

[MIT](LICENSE)