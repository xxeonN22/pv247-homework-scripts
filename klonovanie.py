import os
import time
import git
import shutil
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# ------------------------------------------------------
# 1) Print Usage Information
# ------------------------------------------------------

USAGE_MESSAGE = """
Usage:
    python script.py --homework-url <URL> --homework-folder <FOLDER>

Example:
    python script.py --homework-url "https://pv247-app.vercel.app/homework1" --homework-folder "/path/to/homework"

Arguments:
    --homework-url      Full URL to the PV247 homework (e.g., "https://pv247-app.vercel.app/homework1")
    --homework-folder   Path where the homework repositories should be cloned and processed.

After execution, a script named 'run_repos.sh' will be created inside the 'cloned_repos' directory.
To use it, navigate to the cloned folder and run:

    cd /path/to/homework/cloned_repos
    ./run_repos.sh build   # To install dependencies and build the projects
    ./run_repos.sh dev     # To install dependencies and run projects in dev mode

"""

# If no arguments are provided, print usage and exit
if len(os.sys.argv) < 2:
    print(USAGE_MESSAGE)
    exit(1)

# ------------------------------------------------------
# 2) Parse command-line arguments
# ------------------------------------------------------

parser = argparse.ArgumentParser(description="PV247 GitHub Repository Cloner")
parser.add_argument("--homework-url", required=True, help="Full PV247 homework URL (e.g., 'https://pv247-app.vercel.app/homework1')")
parser.add_argument("--homework-folder", required=True, help="Folder where this homework data (cloned repos + reviewed list) should be stored")
args = parser.parse_args()

HOMEWORK_URL = args.homework_url.strip()  # Ensure no extra spaces
HOMEWORK_FOLDER = args.homework_folder.strip()  # Ensure no extra spaces

# Validate URL format
if not HOMEWORK_URL.startswith("http"):
    print("❌ Invalid homework URL. Please provide a full URL (e.g., 'https://pv247-app.vercel.app/homework1')")
    print(USAGE_MESSAGE)
    exit(1)

# Define paths inside the homework folder
CLONE_FOLDER = os.path.join(HOMEWORK_FOLDER, "cloned_repos")
REVIEWED_REPOS_FILE = os.path.join(HOMEWORK_FOLDER, "reviewed_repos.txt")

# Ensure the folders exist
os.makedirs(CLONE_FOLDER, exist_ok=True)

# Ensure the reviewed_repos.txt file exists
if not os.path.exists(REVIEWED_REPOS_FILE):
    open(REVIEWED_REPOS_FILE, "w").close()  # Create an empty file if it doesn't exist

# ------------------------------------------------------
# 3) Setup Selenium (Attach to Running Chrome)
# ------------------------------------------------------

chrome_options = Options()
chrome_options.add_argument("--log-level=3") 
chrome_options.debugger_address = "localhost:9222"  # Attach to already running Chrome
driver = webdriver.Chrome(options=chrome_options)

# ------------------------------------------------------
# 4) Load the list of already-reviewed repos (if any)
# ------------------------------------------------------

with open(REVIEWED_REPOS_FILE, "r", encoding="utf-8") as f:
    reviewed_repos = set(line.strip() for line in f if line.strip())

try:
    # --------------------------------------------------
    # A) Open the Homework URL and wait for GitHub links
    # --------------------------------------------------

    print(f"🌍 Navigating to: {HOMEWORK_URL}")
    driver.get(HOMEWORK_URL)
    
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'github.com')]"))
    )

    links = driver.find_elements(By.XPATH, "//a[contains(@href, 'github.com')]")
    repo_urls = [link.get_attribute("href") for link in links]
    print(f"✅ Found {len(repo_urls)} potential GitHub repos.")

    # --------------------------------------------------
    # B) Process each repository
    # --------------------------------------------------

    for repo_url in repo_urls:
        repo_name = repo_url.split("/")[-1]
        print(f"\n--- Checking repo '{repo_name}' ---")

        # 1) Skip if already reviewed
        if repo_name in reviewed_repos:
            print(f"   🔸 '{repo_name}' is already marked as reviewed. Skipping.")
            continue

        # 2) Open the pull requests page
        pr_url = f"{repo_url}/pulls"
        driver.get(pr_url)
        time.sleep(2)

        # 3) Check for "Feedback" PR with "Submitted" label
        feedback_selector = (
            "//div[contains(@class,'flex-auto') and "
            ".//a[contains(text(),'Feedback')] and "
            ".//a[contains(@class, 'IssueLabel') and normalize-space()='Submitted']]"
        )
        feedback_prs = driver.find_elements(By.XPATH, feedback_selector)
        if feedback_prs:
            print("✅ Found PR with 'Feedback' + label 'Submitted'. Checking for review text...")

            # Extract the link to the "Feedback" PR
            feedback_link = feedback_prs[0].find_element(By.XPATH, ".//a[contains(text(),'Feedback')]").get_attribute("href")

            # Go to that PR page
            driver.get(feedback_link)
            time.sleep(2)

            # 4) Check if the review contains "hodnotenie", "hodnoceni", or "evaluation"
            review_xpaths = (
                "//*["
                "contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'hodnotenie') "
                "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'evaluation') "
                "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'hodnoceni')"
                "]"
            )
            try:
                driver.find_element(By.XPATH, review_xpaths)
                print("   Found review ('hodnotenie'/'evaluation'/'hodnoceni') -> already reviewed. Skipping.")
                reviewed_repos.add(repo_name)
                with open(REVIEWED_REPOS_FILE, "a", encoding="utf-8") as f:
                    f.write(repo_name + "\n")
                continue

            except NoSuchElementException:
                # No review found → Clone the repo
                print("   No existing evaluation found. Cloning this repo...")
                ssh_url = repo_url.replace("https://github.com/", "git@github.com:") + ".git"
                clone_path = os.path.join(CLONE_FOLDER, repo_name)

                if not os.path.exists(clone_path):
                    print(f"   Cloning into '{clone_path}'...")
                    git.Repo.clone_from(ssh_url, clone_path)
                    print("   ✅ Clone complete.")
                else:
                    print("   🔹 Already cloned; skipping.")

        else:
            print("   ❌ No 'Feedback' PR with label 'Submitted' found; skipping clone.")

finally:
    driver.quit()

# ------------------------------------------------------
# 5) Create run_repos.sh in the cloned_repos folder
# ------------------------------------------------------
run_script_content = """#!/bin/bash

################################################
# Main script logic
################################################

# Usage check
if [ $# -eq 0 ]; then
    echo "Usage: $0 <build|dev>"
    exit 1
fi

MODE=$1
BASE_DIR=$(pwd)

# This file will keep track of repos we've already processed.
PROCESSED_FILE="$BASE_DIR/processed_repos.txt"

# Create the file if it doesn't exist
if [ ! -f "$PROCESSED_FILE" ]; then
    touch "$PROCESSED_FILE"
fi

################################################
# Function to close all VSCode windows and clear cache
################################################
close_and_clear_vscode() {
    echo "➡️ Closing all VS Code windows..."
    pkill code 2>/dev/null

    echo "➡️ Removing VSCode cache..."
    rm -rf ~/.config/Code/Cache 2>/dev/null
    rm -rf ~/.config/Code/Code\ Cache 2>/dev/null
    rm -rf ~/.config/Code/workspaceStorage 2>/dev/null
}

################################################
# Start processing each repository
################################################
for repo in */; do
    # Remove trailing slash from repo name
    repo=${repo%/}

    # Skip if it's not a directory
    [ ! -d "$repo" ] && continue

    # If this repository is already in processed_repos, skip it
    if grep -Fxq "$repo" "$PROCESSED_FILE"; then
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Repository '$repo' has already been processed. Skipping..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        continue
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "REPOSITORY: $repo"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Construct the GitHub PR files URL dynamically
    GITHUB_PR_FILES_URL="https://github.com/FI-PV247/$repo/pull/1/files"

    # Open the GitHub PR files page in Chrome (suppress errors)
    echo "🌍 Opening GitHub PR Files: $GITHUB_PR_FILES_URL"
    google-chrome "$GITHUB_PR_FILES_URL" 2>/dev/null &

    # Close VSCode windows and clear cache before opening a new instance
    close_and_clear_vscode

    # Enter the repo directory
    cd "$repo" || continue

    # 1) Open VS Code (new window) for this repo (suppress errors)
    echo "➡️ Opening Visual Studio Code..."
    code -n . 2>/dev/null &
    # Give VS Code time to open
    sleep 10

    # 2) Focus the VS Code window
    echo "➡️ Focusing the VS Code window..."
    wmctrl -a "Visual Studio Code"
    sleep 2

    # 3) Open integrated terminal in VS Code
    echo "➡️ Opening integrated terminal..."
    xdotool key alt+n
    sleep 5  # Let terminal appear

    # 4) Type the commands
    if [ "$MODE" == "build" ]; then
        echo "➡️ Typing 'npm install && npm run build'..."
        xdotool type --delay 50 "npm install && npm run build"
        xdotool key Return

        echo
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo " Review the code in VS Code. Build has finished in the terminal."
        echo " When you're DONE reviewing, close the integrated terminal (optional)"
        echo " and then press ENTER here to go to the next repository."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        read -r

    elif [ "$MODE" == "dev" ]; then
        echo "➡️ Typing 'npm install && npm run dev'..."
        xdotool type --delay 50 "npm install && npm run dev"
        xdotool key Return

        echo "⏳ Waiting for Next.js to pick an open port (3000..3010)..."
        
        # Wait a few seconds for Next.js to initialize
        sleep 5 

        # Open localhost:3000 in Chrome (suppress errors)
        echo "🌍 Opening localhost:3000"
        google-chrome "http://localhost:3000" 2>/dev/null &

        echo " WHEN FINISHED:"
        echo "   1. Close the integrated terminal in VS Code (this kills 'npm run dev')."
        echo "   2. Press ENTER here to move on to the next repository."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        read -r

    else
        echo "❌ Invalid mode: $MODE (use 'build' or 'dev')"
        cd "$BASE_DIR"
        exit 1
    fi

    # 5) After pressing enter, close all VS Code windows and remove cache again
    close_and_clear_vscode

    # Mark this repo as processed
    echo "$repo" >> "$PROCESSED_FILE"

    # Return to the base directory
    cd "$BASE_DIR" || exit
done

echo
echo "✅ All repositories processed!"
"""

run_script_path = os.path.join(CLONE_FOLDER, "run_repos.sh")
with open(run_script_path, "w", encoding="utf-8") as f:
    f.write(run_script_content)

# Make it executable
os.chmod(run_script_path, 0o755)

print("\n✅ All repositories processed! A script named 'run_repos.sh' was created in the 'cloned_repos' folder.")
print("To run it, use:")
print(f"    cd {CLONE_FOLDER}")
print("    ./run_repos.sh build   # To install dependencies and build projects")
print("    ./run_repos.sh dev     # To install dependencies and run projects in dev mode")
