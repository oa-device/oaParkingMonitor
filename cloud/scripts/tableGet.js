#!/usr/bin/env node

const { DynamoDBClient, ScanCommand } = require('@aws-sdk/client-dynamodb');
const yargs = require('yargs');

// Parse command-line arguments
const argv = yargs
    .option('t', {
        alias: 'table',
        describe: 'DynamoDB table name',
        demandOption: true,
        type: 'string',
    })
    .help('h')
    .alias('h', 'help')
    .argv;

if (argv.help || !argv.table) {
    yargs.showHelp();
    process.exit(0);
}


function parseDynamoDBAttributeValue(attributeValue) {
    if ("M" in attributeValue) {
        // Handle DynamoDB Map
        const convertedMap = {};
        for (const key in attributeValue.M) {
            if (Object.hasOwnProperty.call(attributeValue.M, key)) {
                convertedMap[key] = parseDynamoDBAttributeValue(attributeValue.M[key]);
            }
        }
        return convertedMap;
    } else if ("L" in attributeValue) {
        // Handle DynamoDB List
        return attributeValue.L.map((item) => parseDynamoDBAttributeValue(item));
    } else if ("N" in attributeValue) {
        // Handle DynamoDB Number (convert to JavaScript number)
        return parseFloat(attributeValue.N);
    } else if ("BOOL" in attributeValue) {
        // Handle DynamoDB Boolean
        return attributeValue.BOOL;
    } else if ("S" in attributeValue) {
        // Handle DynamoDB String
        return attributeValue.S;
    } else {
        // For any other DynamoDB types not explicitly handled
        return attributeValue[Object.keys(attributeValue)[0]];
    }
}


async function scanDynamoDBTable(tableName) {

    let standardJsonData = [];

    let lastEvaluatedKey = undefined;

    do {
        const scanCommand = new ScanCommand({
            TableName: tableName,
            ExclusiveStartKey: lastEvaluatedKey,
        });

        const scanResult = await dynamoDBClient.send(scanCommand);

        // Process DynamoDB items and convert them to standard JSON
        const convertedItems = scanResult.Items.map((item) => {
            const convertedItem = {};
            for (const key in item) {
                if (Object.hasOwnProperty.call(item, key)) {
                    convertedItem[key] = parseDynamoDBAttributeValue(item[key]);
                }
            }
            return convertedItem;
        });

        standardJsonData = standardJsonData.concat(convertedItems);
        lastEvaluatedKey = scanResult.LastEvaluatedKey;

    } while (lastEvaluatedKey);

    console.log(JSON.stringify(standardJsonData, null, 2));
}

// Initialize DynamoDB client
const dynamoDBClient = new DynamoDBClient();

scanDynamoDBTable(argv.table);
// EOF