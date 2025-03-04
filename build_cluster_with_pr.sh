#!/bin/bash

# Function to display help message
show_help() {
  echo "Usage: $0 <wip_label>"
  echo
  echo "Arguments:"
  echo "  <wip_label>        The WIP label or directory name (e.g., wip-hemanth4-testing)"
  echo
  echo "Example:"
  echo "  $0 wip-hemanth4-testing"
  exit 0
}

# Check if the argument is --help or --h and display help
if [[ "$1" == "--help" || "$1" == "--h" ]]; then
  show_help
fi

# Ensure exactly one argument is provided 
if [[ "$#" -ne 1 || "$1" == --* ]]; then
  echo "Error: Invalid argument. Please provide a valid <wip_label>."
  show_help
fi

# Store the WIP label
WIP_LABEL="$1"

# Ensure the WIP label is a valid directory name
if [[ ! "$WIP_LABEL" =~ ^[a-zA-Z0-9._-]+$ ]]; then
  echo "Error: Invalid WIP label '$WIP_LABEL'. Only letters, numbers, dots, underscores, and hyphens are allowed."
  exit 1
fi

# Default values
REPO_URL="https://github.com/ceph/ceph.git"
CI_REMOTE_URL="https://github.com/ceph/ceph-ci.git"
BUILD_SCRIPT_PATH="src/script/build-integration-branch"

# Check if a WIP label is passed as a positional argument
if [[ "$#" -ne 1 ]]; then
  echo "Error: Missing required argument <wip_label>."
  show_help
fi

# Get the WIP label from the first positional argument
WIP_LABEL="$1"

# Clone or update the main repository
cd ~
if [ -d "ceph" ]; then
  cd ceph
  git checkout main
  git pull
  cd ..
else
  git clone $REPO_URL
fi

# Validate if the WIP path already exists
if [ -d "$WIP_LABEL" ]; then
  echo "WIP path $WIP_LABEL already exists. Please clean up and rerun the script."
  exit 1
fi

# Clone the WIP repository
git clone "$REPO_URL" "$WIP_LABEL"
cd "$WIP_LABEL"

# Add the CI remote
git remote add ci "$CI_REMOTE_URL"

# Run the build script and capture the branch name if it passes
if $BUILD_SCRIPT_PATH "$WIP_LABEL"; then
  BRANCH_NAME="$(git rev-parse --abbrev-ref HEAD)"
  echo "Branch name is: $BRANCH_NAME"

  # Push to ceph-ci
  git push ci "$BRANCH_NAME"

  # Provide the URLs with the appended branch name
  SHAMAN_URL="https://shaman.ceph.com/builds/ceph/$BRANCH_NAME/"
  CI_COMMITS_URL="https://github.com/ceph/ceph-ci/commits/$BRANCH_NAME"

  echo "Shaman URL: $SHAMAN_URL"
  echo "Ceph-CI Commits URL: $CI_COMMITS_URL"
  sleep 300

  # Fetch the SHA1 for default link from Shaman URL
  SHA1=$(curl -s "$SHAMAN_URL" | grep -oE '/builds/ceph/'"$BRANCH_NAME"'/[a-f0-9]{40}/default/' | awk -F '/' '{print $5}' | head -n 1)

  if [[ -z "$SHA1" ]]; then
    echo "Error: Failed to fetch SHA1 from $SHAMAN_URL."
    exit 1
  fi

  echo "Captured SHA1 for default link: $SHA1"
else
  echo "Build script failed."
  exit 1
fi

