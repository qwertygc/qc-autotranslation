#!/bin/bash
echo "Starting"
# Create venv
if [ -d ".venv" ]; then
    echo "Virtual environment exists."
else
    echo "Creating virtual environment."
    python3 -m venv ".venv"
fi

echo "What language are we translating today?" 
echo "Please inform langua name in two lowercase letters e.g. \'en\', \'pt\' or \'fr'\ )"
echo "If you don know, access https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes" 
read -p "So, what language?" lang
lang=$(echo "$lang" | tr '[:upper:]' '[:lower:]')

#Check for .po
pofile=$(ls | grep ".po")
if [ ! -z "$"pofile ];then
  echo "No .po file found"
  echo "Please add one to this script's directory"
  exit 1
fi
# Activate environment
source .venv/bin/activate

# Install required modules
echo "Installing requirements. This may take 10 minutes."
python3 -m pip install --upgrade pip
pip install -r requirements.txt

#check for argos_file
argosfile=$(ls | grep ".argosmodel")
if [ ! -z "$"argosfile ];then
  echo "No .argosmodel file found"
  echo "Please add one to this script's directory"
  echo "Download one that translates to English at https://www.argosopentech.com/argospm/index/"
  exit 1
else
  echo ".argosfile located"
  argospm install translate-en_"$lang"
fi

echo "Starting."
python translate.py --all --skip-fuzzy

# Exit environment
cd ../
deactivate
echo "Exiting virtual environment."
