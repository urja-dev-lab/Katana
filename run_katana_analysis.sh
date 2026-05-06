#!/bin/bash
# Script to run Katana analysis in Katana environment on Linux

# Check arguments
if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.katana> <output_directory>"
    echo "Example: $0 /path/to/input.katana /path/to/output"
    exit 1
fi

INPUT_KANA="$1"
OUTPUT_DIR="$2"

# Check if input file exists
if [ ! -f "$INPUT_KANA" ]; then
    echo "Error: Input file '$INPUT_KANA' does not exist."
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Check if katanaBin is available
if ! command -v katana &> /dev/null; then
    echo "Error: katana not found in PATH. Please ensure Katana is installed and in your PATH."
    echo "You may need to source your Katana setup script or add Katana/bin to your PATH."
    exit 1
fi

# Run the analysis script in Katana environment
echo "Running Katana analysis..."
echo "Input file: $INPUT_KANA"
echo "Output directory: $OUTPUT_DIR"

katana --script src/analyze/analyze_katana.py -- "$INPUT_KANA" "$OUTPUT_DIR"

# Check exit status
if [ $? -eq 0 ]; then
    echo "Analysis completed successfully."
    echo "Output files:"
    echo "  - $OUTPUT_DIR/create_log.txt"
    echo "  - $OUTPUT_DIR/katana_file_list.txt"
    echo "  - $OUTPUT_DIR/web_ui_data.json"
else
    echo "Analysis failed. Check the output above for errors."
    exit 1
fi
