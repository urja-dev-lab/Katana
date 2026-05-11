#!/usr/bin/env python3
"""
Logger class for Katana integration scripts
"""

import os
from datetime import datetime


class KatanaLogger:
    """Handles logging to both console and file for Katana scripts"""
    
    def __init__(self, log_file=None):
        self.log_file = log_file
    
    def log(self, message):
        """Log a message with timestamp to both console and log file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp}: {message}"
        print(log_entry)
        
        if self.log_file:
            # Ensure directory exists
            log_dir = os.path.dirname(self.log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            with open(self.log_file, 'a') as f:
                f.write(log_entry + '\n')
    
    def info(self, message):
        """Log an info message"""
        self.log(f"[INFO] {message}")
    
    def error(self, message):
        """Log an error message"""
        self.log(f"[ERROR] {message}")
    
    def warning(self, message):
        """Log a warning message"""
        self.log(f"[WARNING] {message}")
    
    def success(self, message):
        """Log a success message"""
        self.log(f"[SUCCESS] {message}")
    def repath(self, source, target):
        """Log a repath action with source and target paths"""
        self.info(f"Repathing {source} -> {target}")