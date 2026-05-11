import os
import re
import glob


def is_sequence_source_valid(source_path):
    """Check if a sequence source path has any existing files"""
    # Handle UDIM patterns
    if '<UDIM>' in source_path:
        # Replace <UDIM> with wildcards to find matching files
        udim_pattern = source_path.replace('<UDIM>', '[0-9][0-9][0-9][0-9]')
        try:
            matching_files = glob.glob(udim_pattern)
            # Also check for 3-digit frame numbers sometimes used with UDIM
            udim_pattern_3digit = source_path.replace('<UDIM>', '[0-9][0-9][0-9]')
            matching_files_3digit = glob.glob(udim_pattern_3digit)
            matching_files.extend(matching_files_3digit)
            
            # Remove duplicates and check if any exist
            matching_files = list(set(matching_files))
            return len(matching_files) > 0
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
        match = re.match(pattern, source_path)
        if match:
            base_path = match.group(1)
            frame_num = match.group(2)
            extension = match.group(3)
            
            # Look for sequence in the same directory
            directory = os.path.dirname(source_path)
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
                
                if len(sequence_files) > 0:
                    return True
            except:
                pass
    
    # If not a sequence, fall back to regular file check
    return os.path.exists(source_path)