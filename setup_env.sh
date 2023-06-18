#!/bin/bash
# necessary shell option for aliases to work
shopt -s expand_aliases

# argument handling
while getopts i: flag
do
    case "${flag}" in
        i) install=${OPTARG};;
        *) echo "Invalid argument" && exit 1;;
    esac
done

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

if command -v apt-get > /dev/null && [ $EUID -eq 0 ] && [ "$install" == "true" ]
then
  # from debconf manpage, section 7 specifically (man 7 debconf)
  sudo DEBIAN_FRONTEND=noninteractive apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install ffmpeg python3 python3-pip python3-venv
elif [ $EUID -ne 0 ] && [ "$install" == "true" ]
then
  printf "Install requested, but not running as root\nWill not install packages\n"
fi

# ensure pip
if ! type pip > /dev/null
then
  echo "PIP doesn't exist, installing..."
  python -m ensurepip
fi

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