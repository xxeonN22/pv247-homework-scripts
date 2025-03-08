#!/bin/bash

# Check if required arguments are provided
if [ $# -ne 3 ]; then
    echo "❌ Usage: $0 <homework-url> <homework-folder> <homework-number>"
    echo "Example: $0 'https://pv247-app.vercel.app/lector/homeworks/react-basics?type=own' 'react-basics' 2"
    exit 1
fi

HOMEWORK_URL=$1
HOMEWORK_FOLDER=$2
HOMEWORK_NUMBER=$3

# Define GitHub Solution URLs for each homework
declare -A HOMEWORK_SOLUTION_URLS
HOMEWORK_SOLUTION_URLS[1]="https://github.com/FI-PV247/task-01-typescript-solution/pull/2/files"
HOMEWORK_SOLUTION_URLS[2]="https://github.com/FI-PV247/task-02-2024-react-basics-solution/pull/1/files"
HOMEWORK_SOLUTION_URLS[3]="https://github.com/FI-PV247/task-03-styling-solution/pull/2/files"
HOMEWORK_SOLUTION_URLS[4]="https://github.com/FI-PV247/task-04-state-solution/pull/1/files"
HOMEWORK_SOLUTION_URLS[5]="https://github.com/FI-PV247/task-05-2024-table-memo-solution/pull/1/files"
HOMEWORK_SOLUTION_URLS[6]="https://github.com/FI-PV247/task-06-2024-forms-async-solution/pull/1/files"
HOMEWORK_SOLUTION_URLS[7]="https://github.com/FI-PV247/task-07-2024-nextjs-basic-solution/pull"
HOMEWORK_SOLUTION_URLS[8]="https://github.com/FI-PV247/task-08-2024-rsc-forms-solution/pull/1/files"
HOMEWORK_SOLUTION_URLS[9]="https://github.com/FI-PV247/task-09-2024-api-actions-database-solution/pull/1/files"

# Define Homework Evaluation Pages based on number
declare -A HOMEWORK_EVALUATION_PAGES
HOMEWORK_EVALUATION_PAGES[1]="https://pv247-app.vercel.app/lector/homeworks/typescript?type=own"
HOMEWORK_EVALUATION_PAGES[2]="https://pv247-app.vercel.app/lector/homeworks/react-basics?type=own"
HOMEWORK_EVALUATION_PAGES[3]="https://pv247-app.vercel.app/lector/homeworks/styling?type=own"
HOMEWORK_EVALUATION_PAGES[4]="https://pv247-app.vercel.app/lector/homeworks/state?type=own"
HOMEWORK_EVALUATION_PAGES[5]="https://pv247-app.vercel.app/lector/homeworks/table-memo?type=own"
HOMEWORK_EVALUATION_PAGES[6]="https://pv247-app.vercel.app/lector/homeworks/forms-async?type=own"
HOMEWORK_EVALUATION_PAGES[7]="https://pv247-app.vercel.app/lector/homeworks/nextjs-basic?type=own"
HOMEWORK_EVALUATION_PAGES[8]="https://pv247-app.vercel.app/lector/homeworks/rsc-forms?type=own"
HOMEWORK_EVALUATION_PAGES[9]="https://pv247-app.vercel.app/lector/homeworks/api-actions-database?type=own"

# Define Homework Overview Pages based on number
declare -A HOMEWORK_OVERVIEW_PAGES
HOMEWORK_OVERVIEW_PAGES[1]="https://pv247-app.vercel.app/homeworks/typescript"
HOMEWORK_OVERVIEW_PAGES[2]="https://pv247-app.vercel.app/homeworks/react-basics"
HOMEWORK_OVERVIEW_PAGES[3]="https://pv247-app.vercel.app/homeworks/styling"
HOMEWORK_OVERVIEW_PAGES[4]="https://pv247-app.vercel.app/homeworks/state"
HOMEWORK_OVERVIEW_PAGES[5]="https://pv247-app.vercel.app/homeworks/table-memo"
HOMEWORK_OVERVIEW_PAGES[6]="https://pv247-app.vercel.app/homeworks/forms-async"
HOMEWORK_OVERVIEW_PAGES[7]="https://pv247-app.vercel.app/homeworks/nextjs-basic"
HOMEWORK_OVERVIEW_PAGES[8]="https://pv247-app.vercel.app/homeworks/rsc-forms"
HOMEWORK_OVERVIEW_PAGES[9]="https://pv247-app.vercel.app/homeworks/api-actions-database"

# Validate that the homework number is between 1 and 9
if ! [[ "$HOMEWORK_NUMBER" =~ ^[1-9]$ ]]; then
    echo "❌ Invalid homework number: $HOMEWORK_NUMBER (must be between 1-9)"
    exit 1
fi

# Get the corresponding URLs
SOLUTION_URL=${HOMEWORK_SOLUTION_URLS[$HOMEWORK_NUMBER]}
EVALUATION_PAGE=${HOMEWORK_EVALUATION_PAGES[$HOMEWORK_NUMBER]}
OVERVIEW_PAGE=${HOMEWORK_OVERVIEW_PAGES[$HOMEWORK_NUMBER]}

# Kill all running Chrome instances
echo "🔴 Killing existing Chrome instances..."
pkill chrome

# Start Chrome in debug mode (if not already running)
if ! pgrep -f "chrome.*remote-debugging-port=9222" > /dev/null; then
    echo "🚀 Starting Chrome in debug mode..."
    google-chrome --remote-debugging-port=9222 \
                  --user-data-dir="/home/samuel/.config/google-chrome/" \
                  --profile-directory="Default" \
                  --disable-gpu 2>/dev/null &
    
    # Give Chrome time to start
    sleep 3
fi

# Open required URLs in new tabs
echo "🌍 Opening required homework pages in Chrome..."
google-chrome "$OVERVIEW_PAGE" \
              "$EVALUATION_PAGE" \
              "$SOLUTION_URL" &

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "🛠️ Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Run your Python script with dynamic arguments
echo "🚀 Running script with:"
echo "   📌 Homework URL: $HOMEWORK_URL"
echo "   📂 Homework Folder: $HOMEWORK_FOLDER"
echo "   🏫 Homework Number: $HOMEWORK_NUMBER"
echo "   🔗 Opening GitHub Solution: $SOLUTION_URL"
echo "   📖 Opening Homework Evaluation Page: $EVALUATION_PAGE"
echo "   📜 Opening Homework Overview Page: $OVERVIEW_PAGE"
python3 klonovanie.py --homework-url "$HOMEWORK_URL" --homework-folder "$HOMEWORK_FOLDER"

# Close the first Chrome tab (the cloning page)
echo "🔴 Closing the first Chrome tab (cloning page)..."
xdotool key Ctrl+1  # Focus the first tab
sleep 1
xdotool key Ctrl+w  # Close the tab

# Automatically `cd` into the cloned repositories folder
CLONED_REPOS_DIR="$HOMEWORK_FOLDER/cloned_repos"

if [ -d "$CLONED_REPOS_DIR" ]; then
    echo "📂 Navigating to: $CLONED_REPOS_DIR"
    cd "$CLONED_REPOS_DIR" || exit
else
    echo "❌ Cloned repositories folder not found!"
    exit 1
fi

echo
echo "✅ All repositories processed! You can now run:"
echo "   ./run_repos.sh build   # To install dependencies and build projects"
echo "   ./run_repos.sh dev     # To install dependencies and run projects in dev mode"
