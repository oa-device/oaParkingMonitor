#!/usr/bin/env node

const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const { BatchWriteCommand, DynamoDBDocumentClient } = require("@aws-sdk/lib-dynamodb");
const fs = require('fs');
const path = require('path');
const yargs = require('yargs');

// Helper function to chunk array into smaller arrays
const chunkArray = (array, size) => {
    const result = [];
    for (let i = 0; i < array.length; i += size) {
        result.push(array.slice(i, i + size));
    }
    return result;
};

// Main function to handle uploading the data
async function uploadData({ file, table }) {
    const client = new DynamoDBClient();
    const dbDocClient = DynamoDBDocumentClient.from(client);

    // Read JSON file
    const filePath = path.resolve(file);
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const items = JSON.parse(fileContent);

    console.log(`Uploading ${items.length} items to table '${table}'`);

    // Split the array into chunks of 25 (max items per BatchWriteCommand)
    const chunks = chunkArray(items, 25);

    // Upload each chunk
    for (const [index, chunk] of chunks.entries()) {
        const params = {
            RequestItems: {
                [table]: chunk.map((item) => ({
                    PutRequest: { Item: item }
                }))
            }
        };

        try {
            const data = await dbDocClient.send(new BatchWriteCommand(params));
            console.log(`Chunk ${index + 1} of ${chunks.length} uploaded successfully.`);
            if (data.UnprocessedItems && Object.keys(data.UnprocessedItems).length > 0) {
                console.warn('Some items were not processed:', data.UnprocessedItems);
            }
        } catch (error) {
            console.error(`Error uploading chunk ${index + 1}:`, error);
        }
    }

    console.log('All items uploaded.');
}

// Parse command line arguments
const argv = yargs(process.argv.slice(2))
    .usage('Usage: ./upload_table.js -f <file> -t <table>')
    .option('f', {
        alias: 'file',
        describe: 'The JSON file containing the items',
        demandOption: true,
        type: 'string'
    })
    .option('t', {
        alias: 'table',
        describe: 'The DynamoDB table name',
        demandOption: true,
        type: 'string'
    })
    .help()
    .argv;

// Execute the upload process
uploadData(argv);