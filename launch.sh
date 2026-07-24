#!/bin/bash
echo "Starting"
# Create venv
if [ -d ".venv" ]; then
    echo "Virtual environment exists."
else
    echo "Creating virtual environment."
    python3 -m venv ".venv"
fi

# Activate environment
source .venv/bin/activate

# Install required modules
echo "Installing requirements. This may take 10 minutes."
python3 -m pip install --upgrade pip
pip install -r requirements.txt

echo "Starting SocioTranscribe."
python translate.py --lang fr

# Exit environment
cd ../
deactivate
echo "Exiting virtual environment."
