#!/usr/bin/env node

const { DynamoDBClient, ListTablesCommand } = require('@aws-sdk/client-dynamodb');
const { parse } = require('yargs');
const yargs = require('yargs');

// Parse command-line arguments
const argv = yargs
    .help('h')
    .alias('h', 'help')
    .argv;

if (argv.help) {
    yargs.showHelp();
    process.exit(0);
}

// Show help and exit if --help or -h is specified
if (argv.help) {
    console.log('Usage: listDynamoDBTables.js');
    process.exit(0);
}

// Set the region in the DynamoDB client configuration
const dynamoDBClient = new DynamoDBClient();

async function listTables() {
    try {
        const command = new ListTablesCommand({});
        const result = await dynamoDBClient.send(command);

        if (result.TableNames.length === 0) {
            console.log('No DynamoDB tables found.');
        } else {
            result.TableNames.forEach((tableName) => {
                console.log(tableName);
            });
        }
    } catch (error) {
        console.error('Error:', error.message);
    }
}

// Call the function to list DynamoDB tables
listTables();
