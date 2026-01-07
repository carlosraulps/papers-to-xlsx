# Scientific Paper Analysis Tool

Automate the extraction of structured data from scientific PDFs using Google's Gemini 2.5 Flash. This tool analyzes papers, extracts key information (like Hypothesis, Methodology, Results), and organizes them into a formatted Excel file, while automatically organizing your file system.

## Features

-   **AI-Powered Analysis**: Uses Gemini 1.5 Flash to deeply understand and extract specific scientific details.
-   **Smart Caching**: Maintains a `processed_log.json` to skip already analyzed papers, saving time and API credits.
-   **Structured Excel Export**: Appends new analyses to a single `Paper_Analysis_Results.xlsx` file. Each paper gets its own alphabetically sorted tab.
-   **Automatic Organization**: Renames processed PDFs to `Author_Year_Title.pdf` standard format.
-   **Robust Error Handling**: Logs failures to `error_log.txt` without stopping the batch process.

## Prerequisites

-   Python 3.9+
-   A Google Cloud API Key with access to Gemini 2.5 Flash.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/paper-analysis-tool.git
    cd paper-analysis-tool
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  Create a `.env` file in the project root:
    ```bash
    touch .env
    ```

2.  Add your Google API Key to the `.env` file:
    ```env
    GOOGLE_API_KEY=your_actual_api_key_here
    ```

## Usage

Run the script by providing the folder containing your PDF files:

```bash
python3 main.py /path/to/your/pdf_folder
```

### Example
```bash
python3 main.py ./downloads/new_papers
```

The script will:
1.  Scan the folder for `.pdf` files.
2.  Check if they have been processed before.
3.  Analyze new papers.
4.  Save results to `papers_analysis_output/Paper_Analysis_Results.xlsx`.
5.  Rename the original PDF files.

## Output Structure

After running, your directory will look like this:

```
├── .env
├── main.py
├── processed_log.json         # Tracks processed files
├── papers_analysis_output/     
│   ├── Paper_Analysis_Results.xlsx  # The main output
│   └── error_log.txt                # Any failed files
└── [Your Source Folder]/
    ├── Smith_2023_Study_on_AI.pdf   # Renamed PDFs
    └── ...
```
