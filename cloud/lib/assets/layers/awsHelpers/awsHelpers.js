"use strict";
//Object.defineProperty(exports, "__esModule", { value: true });
const AWS = require('aws-sdk');
const docClient = new AWS.DynamoDB.DocumentClient();
const s3 = new AWS.S3();
const firehose = new AWS.Firehose();
const lambda = new AWS.Lambda();
const sns = new AWS.SNS();
const { createHash } = require('crypto');

module.exports.AWS = AWS;
module.exports.docClient = docClient;
module.exports.s3 = s3;
module.exports.firehose = firehose;
module.exports.lambda = lambda;
module.exports.sns = sns;


/////////////////////////////////////////////////////////////
//
//   S3 Access
//
/////////////////////////////////////////////////////////////

/**
 * @description Returns the list of files in the speficied directory.
 * @param {String} bucketName - Bucket containing the files
 * @param {String} directoryPath - Directory path in the bucket
 * @returns {String[]}
 */
async function listObjects(bucketName, directoryPath) {
    let result = [];

    try {
        const data = await s3.listObjectsV2({ Bucket: bucketName, Prefix: directoryPath }).promise();

        // Extract file names from the response
        const files = data.Contents.map(obj => obj.Key);

        return files;
    } catch (error) {
        return error;
    }
}
module.exports.listObjects = listObjects;


/**
 * @description This method returns true if the key exits in the provided bucket. It returns false otherwise.
 * @param {String} key - S3 bucket path.
 * @param {String} bucket - Name of the bucket.
 * @returns {Bool}
 * @async
 */
async function keyExists(key, bucket) {
    const params = {
        Bucket: bucket,
        Key: key
    };
    try {
        await s3.headObject(params).promise();
        return true;
    }
    catch (err) {
        return false;
    }
}
module.exports.keyExists = keyExists;

/**
 * @deprecated replaced by getSignedDownloadUrl()
 * @description This method returns an URL for the provided object. The provided URL will expire in 1 day.
 * @param {String} key - S3 bucket path.
 * @param {String} bucket - Name of the bucket.
 * @param {Number} [expires=86400] - life time of the returned url
 * @returns {Object}
 * @async
 */
async function getSignedUrl(key, bucket, expires = 3600 * 24) {
    const params = {
        Bucket: bucket,
        Key: key,
        Expires: expires,
    };
    return await s3.getSignedUrlPromise('getObject', params);
}
module.exports.getSignedUrl = getSignedUrl;


/**
 * @description This method returns an URL for the provided object. The provided URL will expire in 1 day by default.
 * @param {String} key - S3 bucket path.
 * @param {String} bucket - Name of the bucket.
 * @param {Number} [expires=86400] - life time of the returned url
 * @returns {Object}
 * @async
 */
async function getSignedDownloadUrl(key, bucket, expires = 3600 * 24) {
    const params = {
        Bucket: bucket,
        Key: key,
        Expires: expires,
    };
    return await s3.getSignedUrlPromise('getObject', params);
}
module.exports.getSignedDownloadUrl = getSignedDownloadUrl;


/**
 * @description This method returns an URL for the provided object. The provided URL will expire in 1 day by default.
 * @param {String} key - S3 bucket path.
 * @param {String} bucket - Name of the bucket.
 * @param {String} contentType - MIME type.
 * @param {Number} [expires=86400] - life time of the returned url
 * @returns {Object}
 * @async
 */
async function getSignedUploadUrl(key, bucket, contentType, expires = 3600 * 24) {
    const params = {
        Bucket: bucket,
        Key: key,
        Expires: expires,
        ContentType: contentType,
    };
    return await s3.getSignedUrlPromise("putObject", params);
}
module.exports.getSignedUploadUrl = getSignedUploadUrl;

/**
 * @description This method writes the provided object in S3. The object will have a public visibility.
 * @param {Binary} data - Decoded file content.
 * @param {String} key - S3 bucket path.
 * @param {String} bucket - Name of the bucket.
 * @param {String} contentType - MIME file type. Ex: "image/jpg"
 * @returns {Object}
 * @async
 */
async function uploadPublicFile(data, key, bucket, contentType) {
    const params = {
        "Body": data,
        "Bucket": bucket,
        "Key": key,
        "ACL": 'public-read',
        "ContentType": contentType
    };
    return await s3.upload(params).promise();
}
module.exports.uploadPublicFile = uploadPublicFile;

async function uploadPrivateFile(data, key, bucket, contentType) {
    const params = {
        "Body": data,
        "Bucket": bucket,
        "Key": key,
        "ContentType": contentType
    };
    return await s3.upload(params).promise();
}
module.exports.uploadPrivateFile = uploadPrivateFile;

/**
 * Load the json file from s3 and return it parsed as a JSON object
 * @param {String} bucket
 * @param {Sttring} filename
 * @returns {Object} 
 */
async function s3LoadJson(bucket, filename) {
    var readParams = {
        Bucket: bucket,
        Key: filename
    };
    let readPromise = s3.getObject(readParams).promise();
    let body = (await readPromise)["Body"];
    return JSON.parse(body);
}
module.exports.s3LoadJson = s3LoadJson;

/**
 * Save the JSON object stringified in S3
 *
 * @param {String} bucket
 * @param {String} key
 * @param {Object} data
 * @returns {Object}
 */
async function s3SaveJson(bucket, key, data) {
    var saveParams = {
        Bucket: bucket,
        Key: key,
        Body: JSON.stringify(data),
        ContentType: "application/json"
    };
    let savePromise = s3.putObject(saveParams).promise();
    return await savePromise;
}
module.exports.s3SaveJson = s3SaveJson;

/**
 * Delete the file from s3
 *
 * @param {String} bucket
 * @param {String} key
 * @returns {Object}
 */
async function s3Delete(bucket, key) {
    const params = {
        Bucket: bucket,
        Key: key
    };
    const promise = s3.deleteObject(params).promise();
    return await promise;
}
module.exports.s3Delete = s3Delete;


/////////////////////////////////////////////////////////////
//
//   DynamoDB Access
//
/////////////////////////////////////////////////////////////

/**
 * @description This method applies the provided JSON patch to the provided object in the database.
 * @param {Object} patches - JSON patch to apply to object.
 * [
 *     { "op": "replace", "path": "/baz", "value": "boo" },
 *     { "op": "replace", "path": "/createdAt", "value": "2023-01-27T10:10:50EST" },
 *     { "op": "add", "path": "/hello", "value": ["world"] },
 *     { "op": "add", "path": "/hello2", "value": ["world2"] },
 *     { "op": "remove", "path": "/foo" },
 *     { "op": "remove", "path": "/tata" }
 * ]
 * @param {Object} item - Object to be updated.
 * @param {String} table - Name of the table to update.
 * @async
 * @throws 400
 * @returns nil
 */
async function updateItem(patches, item, table) {
    //let result = { id: item.id, OldValues: {}, NewValues: {} };
    if (!table) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:updateItem() undefined table (maybe a table is missing in write array)` } };

    let updateParams = {
        TableName: table,
        Key: {
            "id": item.id
        },
        UpdateExpression: "SET",
        ExpressionAttributeNames: {},
        ExpressionAttributeValues: {}
    };
    let removeParams = {
        TableName: table,
        Key: {
            "id": item.id
        },
        UpdateExpression: "REMOVE",
        ExpressionAttributeNames: {},
    };
    let addParams = {
        TableName: table,
        Key: {
            "id": item.id
        },
        UpdateExpression: "SET",
        ExpressionAttributeNames: {},
        ExpressionAttributeValues: {}
    };
    let hasUpdate, hasAdd, hasRemove = false;


    for (let i = 0; i < patches.length; i++) {
        let patch = patches[i];
        let property = patch.path.replace(/\//g, '');
        let value = patch.value;

        switch (patch.op) {
            case "replace":
                hasUpdate = true;
                updateParams.UpdateExpression = updateParams.UpdateExpression.concat(` #${property} = :${property},`);
                updateParams.ExpressionAttributeNames[`#${property}`] = property;
                updateParams.ExpressionAttributeValues[`:${property}`] = value;
                break;
        
            case "add":
                hasAdd = true;
                addParams.UpdateExpression = addParams.UpdateExpression.concat(` #${property} = :${property},`);
                addParams.ExpressionAttributeNames[`#${property}`] = property;
                addParams.ExpressionAttributeValues[`:${property}`] = value;
                break;

            case "remove":
                hasRemove = true;
                removeParams.UpdateExpression = removeParams.UpdateExpression.concat(` #${property},`);
                removeParams.ExpressionAttributeNames[`#${property}`] = property;
                break;

            default:
                throw { statusCode: 400, body: `Unsupported op '${patch.op}'.` };
        }
    }
    // remove last comma
    if (updateParams.UpdateExpression.at(-1) == ",") { 
        updateParams.UpdateExpression = updateParams.UpdateExpression.substring(0, updateParams.UpdateExpression.length - 1);
    }
    if (addParams.UpdateExpression.at(-1) == ",") {
        addParams.UpdateExpression = addParams.UpdateExpression.substring(0, addParams.UpdateExpression.length - 1);
    }
    if (removeParams.UpdateExpression.at(-1) == ",") {
        removeParams.UpdateExpression = removeParams.UpdateExpression.substring(0, removeParams.UpdateExpression.length - 1);
    }
    
    //console.log( { updateParams, addParams, removeParams });


    if (hasUpdate) { await docClient.update(updateParams).promise(); }
    if (hasRemove) { await docClient.update(removeParams).promise(); }
    if (hasAdd)    { await docClient.update(addParams).promise(); }
}
module.exports.updateItem = updateItem;

/**
 * @description - This method returns the object in the specified table matching the primary key provided.
 * @param {String} key - Primary key name.
 * @param {Any} value - Value of the primary key to look for.
 * @param {String} table - Table to look into.
 * @async
 * @returns {Object|Null}
 */
async function getItemByPrimaryKey(key, value, table) {
    if (!table) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:getItemByPrimaryKey() undefined table (maybe a table is missing in read array)` } };
    const params = {
        TableName: table,
        Key: {}
    };
    params.Key[key] = value;
    const promise = docClient.get(params).promise();
    const result = await promise;
    if (!result.Item) {
		return;
        //const msg = `Cannot find item with ${key}=${value} in table ${table}`;
        //throw { statusCode: 404, body: { status: 'error', msg } };
    }
    return result.Item;
}
module.exports.getItemByPrimaryKey = getItemByPrimaryKey;


/**
 * @description - This method returns the object in the specified table matching the key and index provided.
 * @param {String} key - Secondary key name.
 * @param {Any} value - Value of the primary key to look for.
 * @param {String} table - Table to look into.
 * @param {String} indexName - Name of the index.
 * @async
 * @returns {Object|Null}
 */
async function getItemBySecondaryIndexKey(key, value, table, indexName) {
    if (!table) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:getItemBySecondaryIndexKey() undefined table (maybe a table is missing in read array)` } };
    const params = {
        TableName: table,
        IndexName: indexName,
        KeyConditionExpression: `${key} = :id`,
        ExpressionAttributeValues: { ':id': value }
    };
    const promise = docClient.query(params).promise();
    const result = await promise;
    if (!result.Items) {
        return;
    }
    return result.Item;
}
module.exports.getItemBySecondaryIndexKey = getItemBySecondaryIndexKey;

/**
 * @description - This method returns objects in the specified table matching the primary keys provided.
 * @param {String} key - Primary key name.
 * @param {Any[]} values - Value of the primary key to look for.
 * @param {String} table - Table to look into.
 * @async
 * @returns {Object[]}
 */
async function batchGet(params) {
    if (!params.TableName) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:batchGet() undefined table (maybe a table is missing in read array)` } };
    const promise = docClient.batchGet({RequestItems: params}).promise();
    const result = await promise;
    return result.Responses;
}
module.exports.batchGet = batchGet;

/**
 * @description - This method performs a dynamoDB scan.
 * @example
 * // returns all items of table1
 * await awsHelpers.getItems({ TableName: table1 });
 * 
 * // return all entries with specific bookId
 * const params = {
 * TableName: process.env.BOOK_DISTRIBUTOR_TABLE,
 *      FilterExpression: "#bookId = :bookId",
 *      ExpressionAttributeNames: { "#bookId": "bookId" },
 *      ExpressionAttributeValues: { ":bookId": bookId }
 * };
 * const book_distributors = await awsHelpers.getItems(params);
 * @param {Object} params - AWS DynamoDB Scan method parameters.
 * @return {Object[]}
 * @async
 * @todo internally handle db errors
 */
async function getItems(params) {
    if (!params.TableName) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:getItems() undefined table (maybe a table is missing in read array)` } };
    let promise = docClient.scan(params).promise();
    let result = await promise;
    let data = result.Items;
    if (result.LastEvaluatedKey) {
        params.ExclusiveStartKey = result.LastEvaluatedKey;
        data = data.concat(await getItems(params));
    }
    return data;
}
module.exports.getItems = getItems;


// Similar to getItems, but doesn't automatically iterate over the whole table
async function getPageItems(params) {
  if (!params.TableName) {
    throw {
      statusCode: 500,
      body: { status: "error", msg: "function has no table" },
    };
  }

  const result = await docClient.scan(params).promise();

  // Return items and pagination key (if it exists)
  return {
    items: result.Items,
    lastEvaluatedKey: result.LastEvaluatedKey || null,
  };
}

module.exports.getPageItems = getPageItems;

/**
 * @description - This method performs a dynamoDB query.
 * @param {Object} params - AWS DynamoDB query method parameters.
 * @return {Object[]}
 * @async
 * @todo internally handle db errors
 */
async function queryItems(params) {
    if (!params.TableName) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:queryItems() undefined table (maybe a table is missing in read array)` } };
    const dynamoDB = new AWS.DynamoDB.DocumentClient();
    try {
        const result = await dynamoDB.query(params).promise();
        return result.Items;
    } catch (error) {
        console.error("Unable to query. Error:", JSON.stringify(error, null, 2));
        throw error;
    }
}
module.exports.queryItems = queryItems;


/**
 * Insert item in a table
 * @param item - data to store
 * @param table - name of the table
 */
async function putItem(item, table) {
    if (!table) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:putItem() undefined table (maybe a table is missing in write array)` } };
    var params = {
        Item: item,
        TableName: table
    };
    let promise = docClient.put(params).promise();
    let result = await promise;
    return result;
}
module.exports.putItem = putItem;


/**
 * Insert item in a table
 * @param items - array of data to store
 * @param table - name of the table
 */
async function putItems(items, tableName) {
    const chunkSize = 25; // DynamoDB batchWrite limit
    const chunks = Array.from(
        { length: Math.ceil(items.length / chunkSize) },
        (_, i) => items.slice(i * chunkSize, (i + 1) * chunkSize)
    );

    for (const chunk of chunks) {
        const params = {
            RequestItems: {
                [tableName]: chunk.map(item => ({
                    PutRequest: { Item: item }
                }))
            }
        };

        try {
            const response = await docClient.batchWrite(params).promise();

            if (response.UnprocessedItems && response.UnprocessedItems[tableName]?.length > 0) {
                console.warn(`${response.UnprocessedItems[tableName].length} items were not processed`);
                // Optional: implement retry logic here
            } else {
                console.log("Batch written successfully");
            }
        } catch (err) {
            console.error("Error writing batch:", err);
            throw err;
        }
    }
}
module.exports.putItems = putItems;


/**
 * @description Delete an item from the table
 * @param {string} itemId - key of the item to delete
 * @param {string} table - name of the table
 * @param {string} [key="id"] - primary key
 * @param 
 */
async function deleteItem(itemId, table, key = "id") {
    if (!table) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:deleteItem() undefined table (maybe a table is missing in write array)` } };
    var params = {
        TableName: table
    };
    params.Key = {};
    params.Key[key] = itemId;
    let promise = docClient.delete(params).promise();
    let result = await promise;
    return result;
}
module.exports.deleteItem = deleteItem;


/**
 * Returns the properly typed value of the requested general parameter.
 *
 * @param {string} id - identifier of the required general parameter.
 * @param {string} table - name of the general parameter table.
 * @param {any} value_if_problem - value to return if there is a problem.
 * @returns {boolean|integer|float|string|json} parameter value
 */
async function getGeneralParameter(id, table, value_if_problem = false, rawItem = false) { 
    if (!table) throw { statusCode: 500, body: { status: 'error', msg: `awsHelper layer:getGeneralParameter() undefined table (maybe a table is missing in read array)` } };
    const parameter = await getItemByPrimaryKey("id", id, table);
    if (parameter) {

        // support 2 versions
        let parameterType;
        if (parameter.general_parameter_type_id) {
            parameterType = parameter.general_parameter_type_id;
        } else if (parameter.type) { 
            parameterType = parameter.type;
        }

        try {
            switch (parameterType) {
                case "boolean":
                    return rawItem ? parameter : parameter.value === "true";
                    break;

                case "integer":
                    return rawItem ? parameter : parseInt(parameter.value);
                    break;

                case "float":
                    return rawItem ? parameter : parseFloat(parameter.value);
                    break;

                case "string":
                    return rawItem ? parameter : parameter.value;
                    break;

                case "json":
                    return rawItem ? parameter : JSON.parse(parameter.value);
                    break;

                default:
                    console.error(`Cannot parse general_parameter type "${parameter.type}"`);
                    return value_if_problem
                    break;
            }            
        } catch (error) {
            console.error(error);
        }
    }
    return value_if_problem;
}
module.exports.getGeneralParameter = getGeneralParameter;


/////////////////////////////////////////////////////////////
//
//   SNS
//
/////////////////////////////////////////////////////////////

/**
 * Post a message to the provided SNS topic
 *
 * @param {string} Message - Message to post to the topic
 * @param {string} [topic='alert_oa_media_general'] - name of the topic
 */
async function alert(Message, topic = 'alert_orangead_general') {
    const result = await sns.publish({
        Message,
        TopicArn: `arn:aws:sns:us-east-1:128868293117:${topic}`
    }).promise();
}
module.exports.alert = alert;


/////////////////////////////////////////////////////////////
//
//   Firehose
//
/////////////////////////////////////////////////////////////

/**
 *
 *
 * @param {*} stream
 * @param {*} data
 * @returns {Object}
 */
async function firehosePut(stream, data) {
    let result;
    try {
        const params = {
            DeliveryStreamName: stream,
            Record: {
                Data: JSON.stringify(data)
            }
        };
        let promise = firehose.putRecord(params).promise();
        result = await promise;
    }
    catch (e) {        
        console.error(e);
    }
    return result;
}
module.exports.firehosePut = firehosePut;


/////////////////////////////////////////////////////////////
//
//   WebServices
//
/////////////////////////////////////////////////////////////
/**
 * Send the payload JSON object to the websocket
 *
 * @param {String} connectionId
 * @param {Object} payload
 * @param {String} connectionsTableName
 * @param {Function} sendFunction - result of getWebSocketSendFunction() function
 * 
 * @requires "dynamodb:DeleteItem" action on connectionsTableName
 * @requires "execute-api:ManageConnections" action on ws api-gateway
 * @requires "execute-api:Invoke" action on ws api-gateway
 */
async function wsSend(connectionId, payload, connectionsTableName, sendFunction) {
   try {
       await sendFunction(connectionId, JSON.stringify(payload));
   } catch (e) {
       if (e.statusCode === 410) {
           const errmsg = `Found stale connection ${connectionId}`;
           await deleteItem(connectionId, connectionsTableName);
       } else {
           throw e;
       }
   }
}
module.exports.wsSend = wsSend;



/**
 * @param {String} endpoint
 * @returns function
 * 
 * @requires "execute-api:ManageConnections" action on ws api-gateway
 * @requires "execute-api:Invoke" action on ws api-gateway
 */
//let _send_ = undefined;
function getWebSocketSendFunction(endpoint) {
    const apigwManagementApi = new AWS.ApiGatewayManagementApi({
        apiVersion: '2018-11-29',
        endpoint
    });

    const send = async (connectionId, dataString) => {
        await apigwManagementApi.postToConnection({ ConnectionId: connectionId, Data: dataString }).promise();
    };
    return send;
}
//module.exports._send_ = _send_;
module.exports.getWebSocketSendFunction = getWebSocketSendFunction;


/////////////////////////////////////////////////////////////
//
//   Utilities
//
/////////////////////////////////////////////////////////////

/**
 * @description This function returns a new UUID
 * @returns {String}
 */
function newUUID() {
    var S4 = function () {
        return (((1 + Math.random()) * 0x10000) | 0).toString(16).substring(1);
    };
    return (S4() + S4() + "-" + S4() + "-" + S4() + "-" + S4() + "-" + S4() + S4() + S4());
}
module.exports.newUUID = newUUID;


/**
 * This function returns a random string like "yML458YrlzHHJ1Tv7MwWk".
 * The dictionary is '1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
 * 
 * @param {number} [size=22] - Number of characters in the id. With 22 characters, a nanoid is as collision-safe as a UUID composed of 36 characters.
 * @returns {String}
 */
async function nanoid(size = 22) {
    const { customAlphabet } = await import('nanoid');
    const nanoid = customAlphabet('1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', size);
    return nanoid();
}
module.exports.nanoid = nanoid;


/**
 * This function create an index of the objects in the array.
 * The selected key must be unique.
 * 
 * @example
 * const array = [{id:1, a:10}, {id:2, a:20}];
 * const arrayIdx = arrayToIndexByUniqueKey(array);
 * // returns {
 * //     "1": {id:1, a:10},
 * //     "2": {id:2, a:20}
 * // }
 * 
 * const arrayIdx2 = arrayToIndexByUniqueKey(array, "a");
 * // returns {
 * //     "10": {id:1, a:10},
 * //     "20": {id:2, a:20}
 * // }
 * @param {Array} array - array to index
 * @param {string} [key='id'] - index key
 * @returns {Object} - Indexed array content
 */
function arrayToIndexByUniqueKey(array, key = 'id') {
    if (!Array.isArray(array)) return;
    let index = {};
    for (let item of array) {
        let property = item[key];
        index[property] = item;
    }
    return index;
}
module.exports.arrayToIndexByUniqueKey = arrayToIndexByUniqueKey;


/////////////////////////////////////////////////////////////
//
//   Gargoyle
//
/////////////////////////////////////////////////////////////

/**
 * Records the current timestamp in the lact contact table.
 *
 * @param {String} deviceId - UUID of the device to update
 * @param {String} lastContactTableName - Name opf the table
 */
async function recordLastContact(deviceId, lastContactTableName) {
    const lastContact = await getItemByPrimaryKey("id", deviceId, lastContactTableName);
    const now = new Date();

    if (lastContact) {
        // update
        const patches = [
            { "op": "replace", "path": "/updatedAt", "value": now.toISOString() },
            { "op": "replace", "path": "/ts", "value": now.getTime() },
        ];
        await updateItem(patches, lastContact, lastContactTableName);
    }
    else {
        // new contact
        const contact = {
            id: deviceId,
            createdAt: now.toISOString(),
            updatedAt: now.toISOString(),
            ts: now.getTime()
        };
        await putItem(contact, lastContactTableName);
    }
}
module.exports.recordLastContact = recordLastContact


/**
 * Post an alert to http api
 * @param {String} deviceId - UUID of the device
 * @param {String} type - Class of the alarm. ["batteryState", "batteryLevel", "lastContact", 
 * "networkConnection", "chocDetected", "test", "configuration", "registration", "websocket", "camera"]
 * @param {String} op - Operation on the alarm. ["raise", "clear"]
 * @param {String} msg - Message to display
 * @param {String} alert_host - host name of the API gateway
 * @param {String} api_key - API Key of the api gateway
 * Usage ex:
    const https = require('https');
    const api_key = "e1992b41-808b-4e24-9fab-bc39e7a6a92b-4d0c9b6e-e991-4336-8592-22dcda34d924";
    const alert_host = "lr8e1d6qmj.execute-api.us-east-1.amazonaws.com";
    const msg = `Device not connected to websocket (${deviceId}`;
    await postAlert(deviceId, "websocket", "raise", msg, alert_host, api_key)
        .then(result => console.log(`Status code: ${result}`))
        .catch(err => console.error(`Error rausing the alert '${msg} => ${err}'`));
 */
const postAlert = (deviceId, type, op, msg, alert_host, api_key) => {
    const payload = {
        "ts": Date.now(),
        type,
        op,
        msg
    };
    console.log("Alert to POST:", payload);

    return new Promise((resolve, reject) => {
        const options = {
            host: alert_host,
            path: `/devices/${deviceId}/alert`,
            method: 'POST',
            headers: {
                'X-Api-Key': api_key,
                'Content-Type': 'application/json'
            }
        };
        console.log("options=", options);
    
        //create the request object with the callback with the result
        const req = https.request(options, (res) => {
            resolve(JSON.stringify(res.statusCode));
        });

        // handle the possible errors
        req.on('error', (e) => {
            reject(e.message);
        });
    
        //do the request
        req.write(JSON.stringify(payload));

        //finish the request
        req.end();
    });
};
module.exports.postAlert = postAlert


/**
 * Add an entry in the logs table.
 *
 * @param {String} userId - UUID of the user
 * @param {String} op - operation performed
 * @param {Object} object - operations details
 * @param {String} [table=process.env.LOGS_TABLE] - tablename where to add the log
 */
async function logs(userId, op, object, table=process.env.LOGS_TABLE) {
    const log = {
        id: newUUID(),
        ts: Date.now(),
        userId,
        op,
        object
    };
    await putItem(log, table);
}
module.exports.logs = logs


/**
 * This function allows saving an anomaly into a table.
 *
 * @param {String} itemId - id of the item where the anomaly has been detected (if applicable)
 * @param {String} itemType - type of the item (table name)
 * @param {String} message - description of the anomaly
 * @param {String} context - general contect on how the anomaly has been discovered
 * @param {String} [table=process.env.ANOMALIES_TABLE] - table to record the anomaly
 */
async function recordAnomaly(itemId, itemType, message, context, table=process.env.ANOMALIES_TABLE) {
    const log = {
        id: newUUID(),
        ts: Date.now(),
        itemId,
        itemType,
        message,
        context
    };
    await putItem(log, table);
}
module.exports.recordAnomaly = recordAnomaly


/**
 * This function works with authorizers. Is an authorizer has been
 * in the loop, it probably (ar least for atlas media) returned
 * a permission structure. This function processes this structure 
 * and returns it.
 *
 * @param {Object} event - event received by the handler
 * @returns {Object}
 */
function getRequesterAuthorization(event) {
    let requesterAuthorization = event.requestContext
        && event.requestContext.authorizer
        && event.requestContext.authorizer.lambda
        ? event.requestContext.authorizer.lambda
        : null;
    if (!requesterAuthorization) {
        requesterAuthorization = {
            userId: 'unknown',
            roles: ["admin"]
        }
    }
    return requesterAuthorization;
}
module.exports.getRequesterAuthorization = getRequesterAuthorization

/**
 * Hash a password to save in the table or compare to the table.
 *
 * @param {String} password - Plain text password
 * @param {String} userId - Unique identifier of the user
 * @returns {String}
 */
async function hashPassword(password, userId='X') {
    const salt = await getGeneralParameter(`lambda_editor_password_hash_salt`, process.env.GENERAL_PARAMETERS_TABLE, '');
    return createHash('sha256').update("d98de361-e30c-419c-a2fc-47d408c2aa0b"+password+salt+userId).digest('hex')
}
module.exports.hashPassword = hashPassword

/**
 * Hash a text
 *
 * @param {String} text - tyext to hash
 * @returns {String}
 */
function hash(text) {
    return createHash('sha256').update(text).digest('hex')
}
module.exports.hash = hash

/**
 * Generate a UUIDv7
 *
 * @returns {String}
 */
function uuidv7() {
    const now = BigInt(Date.now()); // milliseconds since epoch
    const timestamp = now.toString(16).padStart(12, "0"); // 48-bit timestamp (12 hex chars)

    // Generate 74 bits of randomness
    const random = crypto.getRandomValues(new Uint8Array(10)); // 80 bits
    let randomHex = Array.from(random, b => b.toString(16).padStart(2, "0")).join("");
    randomHex = randomHex.slice(0, 14); // keep only 56 bits (14 hex chars)

    // Construct UUID: time_hi_and_version + clock_seq_hi_and_reserved + node
    // Layout (UUID v7): time_low (8) - time_mid (4) - time_hi_and_version (4) - clock_seq (4) - node (12)
    const time_low = timestamp.slice(4);         // last 8 chars
    const time_mid = timestamp.slice(0, 4);      // first 4 chars
    const time_hi = "7" + randomHex.slice(0, 3); // version 7
    const clock_seq = (parseInt(randomHex.slice(3, 4), 16) & 0x3 | 0x8).toString(16) + randomHex.slice(4, 7);
    const node = randomHex.slice(7, 19).padEnd(12, "0"); // ensure 12 hex chars

    return `${time_low}-${time_mid}-${time_hi}-${clock_seq}-${node}`;
}
module.exports.uuidv7 = uuidv7
