
import os
import shutil

def cleanup(target_dir):
    print(f"Cleaning state in {target_dir}...")
    
    output_dir = os.path.join(target_dir, "outputs")
    
    files_to_remove = [
        "processed_log.json",
        "processed_hashes.json",
        "Paper_Analysis_Results.xlsx",
        "error_log.txt",
        "citations/references_database.json",
        "citations/library.bib",
        "citations/references_apa.txt",
        "citations/references_aps.txt"
    ]
    
    if os.path.exists(output_dir):
        for f in files_to_remove:
            path = os.path.join(output_dir, f)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"Removed: {f}")
                except Exception as e:
                     print(f"Failed to remove {f}: {e}")
        
    print("Cleanup complete. You can now run main.py for a fresh start.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cleanup(sys.argv[1])
    else:
        print("Usage: python clean_state.py <target_folder>")
