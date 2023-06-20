#!/bin/bash
# necessary shell option for aliases to work
shopt -s expand_aliases
set -o pipefail

# argument handling
while getopts i:n: flag
do
    case "${flag}" in
        i) install=${OPTARG};;
        n) no_venv=${OPTARG};;
        *) echo "Invalid argument" && exit 1;;
    esac
done

if command -v apt-get > /dev/null && [ $EUID -eq 0 ] && [ "$install" == "true" ]
then
  # from debconf manpage, section 7 specifically (man 7 debconf)
  sudo DEBIAN_FRONTEND=noninteractive apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install ffmpeg python3 python3-pip python3-venv -y
elif [ $EUID -ne 0 ] && [ "$install" == "true" ]
then
  printf "Install requested, but not running as root\nWill not install packages\n"
fi

# check if python exists
if ! command -v python > /dev/null && ! command -v python3 > /dev/null
then
  echo "Python doesn't exist, exiting..."
  exit 1
fi

if ! command -v python > /dev/null && command -v python3 > /dev/null
then
  echo "Python is only accessible via \"python3\", a temporary alias will created"
  alias python="python3"
fi

# ensure pip
if ! type pip > /dev/null
then
  echo "PIP doesn't exist, installing..."
  python -m ensurepip
fi

if [ "$no_venv" == "true" ]
then
  # install wheel globally
  pip install wheel

  # install requirements
  pip install -r requirements.txt

  # notify that no_venv was requested
  printf "All done!\nNo venv was requested, so packages were installed into the system python environment\n"
else
  # create a venv
  python -m venv .venv

  # make activation script executable
  chmod +x .venv/bin/activate

  # install wheel in the venv
  .venv/bin/pip install wheel

  # install requirements
  .venv/bin/pip install -r requirements.txt

  # command to run
  printf "All done!\nRun \"source .venv/bin/activate\"\n"
fi