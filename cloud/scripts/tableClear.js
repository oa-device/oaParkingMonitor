#!/usr/bin/env node

const {
    DynamoDBClient,
    ScanCommand,
    BatchWriteItemCommand,
    DescribeTableCommand,
} = require('@aws-sdk/client-dynamodb');
const yargs = require('yargs');

// Parse command-line arguments
const argv = yargs
    .option('t', {
        alias: 'table',
        describe: 'DynamoDB table name to clear',
        demandOption: true,
        type: 'string',
    })
    .help('h')
    .alias('h', 'help')
    .argv;

const dynamoDBClient = new DynamoDBClient();

/**
 * Retrieve primary key attribute names from table schema
 */
async function getKeySchema(tableName) {
    const result = await dynamoDBClient.send(
        new DescribeTableCommand({ TableName: tableName })
    );

    return result.Table.KeySchema.map((entry) => entry.AttributeName);
}

/**
 * Delete all items from a DynamoDB table
 */
async function deleteAllItems(tableName) {
    const keyAttributes = await getKeySchema(tableName);
    //console.log(`Detected key schema: ${keyAttributes.join(', ')}`);

    let lastEvaluatedKey = undefined;
    let totalDeleted = 0;

    do {
        // 1. Scan only the keys
        const scanParams = {
            TableName: tableName,
            ExclusiveStartKey: lastEvaluatedKey,
            ProjectionExpression: keyAttributes
                .map((attr, i) => `#k${i}`)
                .join(', '),
            ExpressionAttributeNames: keyAttributes.reduce(
                (acc, attr, i) => ({ ...acc, [`#k${i}`]: attr }),
                {}
            ),
        };

        const scanResult = await dynamoDBClient.send(new ScanCommand(scanParams));
        lastEvaluatedKey = scanResult.LastEvaluatedKey;

        if (!scanResult.Items || scanResult.Items.length === 0) continue;

        // 2. Build delete requests with just the key attributes
        const deleteRequests = scanResult.Items.map((item) => {
            const key = {};
            for (const attr of keyAttributes) {
                key[attr] = item[attr];
            }
            return { DeleteRequest: { Key: key } };
        });

        // 3. Send in batches of 25
        for (let i = 0; i < deleteRequests.length; i += 25) {
            const batch = deleteRequests.slice(i, i + 25);

            await dynamoDBClient.send(
                new BatchWriteItemCommand({
                    RequestItems: { [tableName]: batch },
                })
            );

            totalDeleted += batch.length;
            console.log(`Deleted ${batch.length} items...`);
        }
    } while (lastEvaluatedKey);

    console.log(
        `✅ Finished deleting all items from table "${tableName}". Total deleted: ${totalDeleted}`
    );
}

(async () => {
    try {
        await deleteAllItems(argv.table);
    } catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
})();