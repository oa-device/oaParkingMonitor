#!/bin/bash

# get the source environment, target environment, and mode from the command line
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 <source-env> <target-env> [mode: replace|add]"
    echo "mode:"
    echo "   replace : Will clear target tables before uploading"
    echo "   add     : Will only add data to target tables (default)"
    echo "Examples:"
    echo "  replace all test environment table content with dev environment table content"
    echo "      $0 dev test replace"
    echo "  Add all prod environment table content with dev environment table content"
    echo "      $0 prod test add"
    echo "      or"
    echo "      $0 prod test"
    exit 1
fi

SOURCE_PROFILE=$1
TARGET_PROFILE=$2

# Default mode is 'add' if not specified
MODE=${3:-add}

# Validate mode
if [[ "$MODE" != "add" && "$MODE" != "replace" ]]; then
    echo "Invalid mode: $MODE"
    echo "Allowed values: replace or add"
    exit 1
fi

echo "Source profile: $SOURCE_PROFILE"
echo "Target profile: $TARGET_PROFILE"
echo "Mode: $MODE"

# using ./tableList.js, put the list of source environment tables in a variable
sourceTables=$(node ./tableList.js | grep "_${SOURCE_PROFILE}_")
sourceTableArray=($sourceTables)

targetTables=$(node ./tableList.js | grep "_${TARGET_PROFILE}_")
targetTableArray=($targetTables)

# loop through the array and export each table name as an environment variable
for table in "${sourceTableArray[@]}"; do
    sourceTable=$(echo "$table" | xargs)  # trim whitespace
    targetTable=$(echo "$sourceTable" | sed "s/_${SOURCE_PROFILE}_/_${TARGET_PROFILE}_/")

    echo "Processing source table: '$sourceTable'"

    # check if target exists in targetTableArray
    if [[ " ${targetTableArray[*]} " =~ " ${targetTable} " ]]; then
        echo "  ✅ Found matching target: $targetTable"
    else
        echo "  ❌ No matching target found for $sourceTable. Skipping."
        echo
        continue   # skip to the next source table
    fi

    echo "Processing source table: '$sourceTable'"

    # using ./tableGet.js, get the content of each table and save it to a temporary file
    ./tableGet.js -t "$sourceTable" > "/tmp/${sourceTable}.json"

    # make a backup of the target tables
    ./tableGet.js -t "$targetTable" > "/tmp/${targetTable}.json"

    if [ "$MODE" == "replace" ]; then
        # clear the target table
        ./tableClear.js -t "$targetTable"
    fi

    # upload the content of the source table to the target table using ./tableUpload.js
    ./tableUpload.js -f "/tmp/${sourceTable}.json" -t "$targetTable"

    #inform the user
    echo "Copied table '$sourceTable' to '$targetTable'"
    echo
done   

# clean up temporary files
#rm /tmp/*.json
#echo "Temporary files cleaned up."
echo "Table copy from profile '$SOURCE_PROFILE' to '$TARGET_PROFILE' completed."
# EOF