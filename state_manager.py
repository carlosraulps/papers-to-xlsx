import os
import json
import logging

class StateManager:
    def __init__(self, output_dir):
        """
        Initializes the StateManager and loads existing logs.
        """
        self.output_dir = output_dir
        self.log_file_path = os.path.join(output_dir, "processed_log.json")
        self.hashes_file_path = os.path.join(output_dir, "processed_hashes.json")
        
        self.processed_log = self._load_json(self.log_file_path)
        self.processed_hashes = self._load_json(self.hashes_file_path)
        
    def _load_json(self, path):
        """Helper to load JSON file safely."""
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load log {path}: {e}. Starting fresh.")
                return {}
        return {}
    
    def _save_json(self, data, path):
        """Helper to save JSON file safely."""
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=4, sort_keys=True)
        except Exception as e:
            logging.error(f"Failed to save log {path}: {e}")

    def is_processed(self, filename):
        """Checks if a file has definitely been processed successfully."""
        status = self.processed_log.get(filename)
        return status == "Processed"

    def mark_as_processed(self, filename, file_hash=None):
        """
        Atomic update: Marks file as Processed and updates hash registry.
        Saves to disk immediately.
        """
        self.processed_log[filename] = "Processed"
        self._save_json(self.processed_log, self.log_file_path)
        
        if file_hash:
            self.processed_hashes[file_hash] = filename
            self._save_json(self.processed_hashes, self.hashes_file_path)

    def mark_as_failed(self, filename):
        """Marks file as Failed."""
        self.processed_log[filename] = "Failed"
        self._save_json(self.processed_log, self.log_file_path)

    def record_rename(self, old_filename, new_filename, file_hash=None):
        """
        Updates the log when a file is renamed.
        Removes the old entry and adds the new one.
        Updates hash registry to point to new name.
        """
        # Update Log
        if old_filename in self.processed_log:
            del self.processed_log[old_filename]
        self.processed_log[new_filename] = "Processed"
        self._save_json(self.processed_log, self.log_file_path)
        
        # Update Hash Registry
        if file_hash:
            self.processed_hashes[file_hash] = new_filename
            self._save_json(self.processed_hashes, self.hashes_file_path)

    def is_known_hash(self, file_hash):
        """Checks if this content hash has been seen before."""
        return file_hash in self.processed_hashes

    def get_filename_for_hash(self, file_hash):
        """Returns the filename associated with a hash."""
        return self.processed_hashes.get(file_hash)
