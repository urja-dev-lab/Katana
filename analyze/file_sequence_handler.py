import os
import re
import glob


def process_file_sequence(file_path):
    """Detect and expand file sequences including UDIM patterns"""
    # Handle UDIM patterns first
    if '<UDIM>' in file_path:
        # Replace <UDIM> with a wildcard to find matching files
        udim_pattern = file_path.replace('<UDIM>', '[0-9][0-9][0-9][0-9]')
        try:
            matching_files = glob.glob(udim_pattern)
            if matching_files:
                # Also check for 3-digit frame numbers sometimes used with UDIM
                udim_pattern_3digit = file_path.replace('<UDIM>', '[0-9][0-9][0-9]')
                matching_files_3digit = glob.glob(udim_pattern_3digit)
                matching_files.extend(matching_files_3digit)
                
                # Remove duplicates and sort
                matching_files = sorted(list(set(matching_files)))
                if matching_files:
                    return matching_files
        except:
            pass
    
    # Check for standard file sequences
    sequence_patterns = [
        r'(.*)\.(\d+)\.(.*)',  # filename.1001.ext
        r'(.*)\.(\d{4})\.(.*)',  # filename.1001.ext with 4-digit frame
        r'(.*)\.(\d{3})\.(.*)',  # filename.001.ext with 3-digit frame
        r'(.*)\.(\d{1,4})\.(.*)',  # filename.1.ext or filename.0001.ext
    ]
    
    for pattern in sequence_patterns:
        match = re.match(pattern, file_path)
        if match:
            base_path = match.group(1)
            frame_num = match.group(2)
            extension = match.group(3)
            
            # Look for sequence in the same directory
            directory = os.path.dirname(file_path)
            if not directory:
                directory = '.'
            
            try:
                files_in_dir = os.listdir(directory)
                sequence_files = []
                
                # Find all files matching the pattern
                prefix = os.path.basename(base_path)
                suffix = '.' + extension if extension else ''
                
                for f in files_in_dir:
                    if f.startswith(prefix) and f.endswith(suffix):
                        # Extract frame number
                        frame_part = f[len(prefix):-len(suffix)] if suffix else f[len(prefix):]
                        if frame_part.isdigit():
                            sequence_files.append(os.path.join(directory, f))
                
                if len(sequence_files) > 1:
                    return sorted(sequence_files)
            except:
                pass
    
    return [file_path]  # Return as single item list if not a sequence