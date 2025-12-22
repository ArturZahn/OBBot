#!/bin/bash

LAST_RUN_FILE="/home/artur/Documents/OBBot/.last_run"
MAIN_SCRIPT_PATH="/home/artur/Documents/OBBot/main.py"
LOG_FILE="/home/artur/Documents/OBBot/logs/cron.log"
PROJECT_DIR="/home/artur/Documents/OBBot"

# Change to the project directory
cd "$PROJECT_DIR" || exit

# Create log file if it doesn't exist
touch "$LOG_FILE"

# Check if the main script is already running
if pgrep -f "$MAIN_SCRIPT_PATH" > /dev/null; then
    echo "main.py is already running. Exiting." >> "$LOG_FILE"
    exit 0
fi

# Get current time in seconds
NOW=$(date +%s)

# Default to a long time ago if the last run file doesn't exist
LAST_RUN_TIME=0
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN_TIME=$(cat "$LAST_RUN_FILE")
fi

# Calculate the time difference in days
TIME_DIFF=$(( (NOW - LAST_RUN_TIME) / 86400 ))

# If it has been 1 or more days, run the script
if [ "$TIME_DIFF" -ge 1 ]; then
    echo "Running main.py at $(date)" >> "$LOG_FILE"
    source myenv/bin/activate
    python3 "$MAIN_SCRIPT_PATH" >> "$LOG_FILE" 2>&1
    # Update the last run time only if the script ran successfully
    # if [ $? -eq 0 ]; then
    #     echo "$NOW" > "$LAST_RUN_FILE"
    # else
    #     echo "main.py failed to run." >> "$LOG_FILE"
    # fi
    echo "$NOW" > "$LAST_RUN_FILE"
fi
