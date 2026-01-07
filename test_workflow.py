from unittest.mock import MagicMock
import sys
import os
import json

# Mock analyzer.py
sys.modules['analyzer'] = MagicMock()
# Mock configure_gemini
sys.modules['analyzer'].configure_gemini = lambda: None

# Mock analyze_pdf to return dummy data
def mock_analyze(pdf_path):
    print(f"Mock analyzing {pdf_path}")
    base = os.path.basename(pdf_path)
    return {
        "Title": f"Study of {base}",
        "Authors": ["Alice Smith", "Bob Jones"],
        "Year": "2023",
        "Journal": "Journal of Testing",
        "Central Result": "It works!"
    }
sys.modules['analyzer'].analyze_pdf = mock_analyze

# Import main after mocking
import main

# Setup test environment
test_dir = "test_pdfs"
if not os.path.exists(test_dir):
    os.makedirs(test_dir)

# Create dummy PDFs
with open(os.path.join(test_dir, "paper1.pdf"), "w") as f:
    f.write("dummy content")
with open(os.path.join(test_dir, "paper2.pdf"), "w") as f:
    f.write("dummy content")

# Run main
print("--- FIRST RUN ---")
sys.argv = ["main.py", test_dir]
main.main()

# Check output
print("\n--- CHECKING OUTPUT ---")
log_path = "processed_log.json"
if os.path.exists(log_path):
    with open(log_path) as f:
        print("Log content:", json.load(f))
else:
    print("Log file missing!")

# Check renaming
print("\nFiles in test_pdfs:")
print(os.listdir(test_dir))

# Run again (should skip)
print("\n--- SECOND RUN (Should skip) ---")
# Reset argv just in case
sys.argv = ["main.py", test_dir]
main.main()
