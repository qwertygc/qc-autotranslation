#!/bin/bash
count=0
get_script_dir()
{
    local SOURCE_PATH="${BASH_SOURCE[0]}"
    local SYMLINK_DIR
    local SCRIPT_DIRECTORY
    # Resolve symlinks recursively
    while [ -L "$SOURCE_PATH" ]; do
        # Get symlink directory
        SYMLINK_DIR="$( cd -P "$( dirname "$SOURCE_PATH" )" >/dev/null 2>&1 && pwd )"
        # Resolve symlink target (relative or absolute)
        SOURCE_PATH="$(readlink "$SOURCE_PATH")"
        # Check if candidate path is relative or absolute
        if [[ $SOURCE_PATH != /* ]]; then
            # Candidate path is relative, resolve to full path
            SOURCE_PATH=$SYMLINK_DIR/$SOURCE_PATH
        fi
    done
    # Get final script directory path from fully resolved source path
    SCRIPT_DIRECTORY="$(cd -P "$( dirname "$SOURCE_PATH" )" >/dev/null 2>&1 && pwd)"
    echo "$SCRIPT_DIRECTORY"
}
SCRIPT_DIR=$(get_script_dir)
check_file(){
    local ext="$1"
    file=$(ls $SCRIPT_DIR | grep "$ext")
if [ ! -z "$file" ];then
  echo "No $ext file found"
  echo "Please add one to this script's directory"
  return 1
  count=(($count++))
fi
}

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
check_file ".po"
check_file ".ts"

if [ count -gt 1] then;
    echo "No .ts or .po file located"
    echo "Add at least one to start the process"
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
if [ -z "$"argosfile ];then
  echo "No .argosmodel file found"
  echo "Please add one to this script's directory"
  echo "Downloading one that translates to English at https://www.argosopentech.com/argospm/index/..."
  url1="https://argos-net.com/v1/translate-{en-${lang},${lang}_en}-[0-9]_[0-9].argosmodel"
  url2="https://argos-net.com/v1/translate-{en-${lang},${lang}_en}-[0-9]_[0-9]_[0-9].argosmodel"
  if [ $lang == "pt" ];then
      url1="https://argos-net.com/v1/translate-{pb_en,en_pb}-[0-9]_[0-9].argosmodel"
      url2="https://argos-net.com/v1/translate-{pb_en,en_pb}-[0-9]_[0-9]_[0-9].argosmodel"
  fi  
  if ! curl --connect-timeout 30 --max-time 300 "$SCRIPT_DIR" -O $url1; then
      if ! curl --connect-timeout 30 --max-time 300 "$SCRIPT_DIR" -O $url2; then
          if ! wget --connect-timeout 30 --max-time 300 "$SCRIPT_DIR" -O $url1; then
              if ! wget --connect-timeout 30 --max-time 300 --output-dir "$SCRIPT_DIR" -O $url2; then
                   echo "Download Failed, please download ir manually at https://www.argosopentech.com/argospm/index/"
                   exit 1
              fi
          fi
      fi
  fi
else
  echo ".argosfile located"
  if ! argospm install translate-en_"$lang"
      if ! argospm install translate-"$lang"_en
          echo "Failed to install translations model"
          echo "Aborting..."
          exit 1
      fi
  fi
fi

echo "Starting."
python translate.py --all --skip-fuzzy

argospm remove translate-en_"$lang"
# Exit environment
cd ../
deactivate
echo "Exiting virtual environment."
