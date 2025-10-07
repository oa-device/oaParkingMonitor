/**
 * Lambda: device_post_detections/index.js
 *
 * Description:
 * This AWS Lambda function processes device detection events sent via HTTP POST requests.
 * It validates and enriches each detection (ensuring UUID, customerId, and timestamp),
 * validates for uniqueness, and saves the detections to DynamoDB. The function enforces
 * customerId consistency between the request header and detection body, and returns
 * the saved detections in the response.
 * If the requested bin size is a named size, the bins are taken from the corresponding
 * pre-compiled table.
 *
 * Input:
 *  - event.body: JSON (array or object) containing one or more detections
 *  - event.headers: must include 'x-customer-id'
 *
 * Output:
 *  - statusCode: 200 on success, 400/403/404/500 on error
 *  - body: { status: "ok", detections: [...] } or error message
 *
 * Required environment variables:
 *  - LAMBDA_NAME
 *  - GENERAL_PARAMETERS_TABLE
 *  - CUSTOMERS_TABLE
 *  - DETECTIONS_TABLE
 *
 * Dependencies:
 *  - awsHelpers (custom Lambda layer)
 *
 * Author: Orangead Team
 * Date: 2025-09-16
 */

// Importing modules from the custom layer
const awsHelpers = require('/opt/awsHelpers');

let debug = process.env.DEBUG == "true";
const BIN_ACCEPTED_VALUES = ["hour", "day", "week", "month"];

/**
 * AWS Lambda function handler for the GET /detections route.
 * Retrieves and processes revenue statistics based on query parameters.
 *
 * @param {Object} event - The AWS Lambda event object.
 * @returns {Promise<Object>} - A promise that resolves to the API response.
 */
exports.handler = async (event) => {

    // Retrieve debug flag from general parameters table.
    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log('Event:', JSON.stringify(event, null, 2));

    let response = {
        statusCode: 200,
        headers: {
            "content-type": "application/json"
        }
    };

    try {
        const headers = Object.fromEntries(
            // lowervase all header keys
            Object.entries(event.headers).map(([k, v]) => [k.toLowerCase(), v])
        );

        // Construct DynamoDB query parameters.
        let params = {
            TableName: process.env.DETECTIONS_TABLE,
            FilterExpression: 'customerId = :customerId',
            ExpressionAttributeValues: {
                ':customerId': headers["x-customer-id"]
            }
        };

        if (event?.queryStringParameters?.siteId) {
            params.FilterExpression = params.FilterExpression + ' AND siteId = :siteId';
            params.ExpressionAttributeValues[':siteId'] = event.queryStringParameters.siteId;
        }

        if (event?.queryStringParameters?.zoneId) {
            params.FilterExpression = params.FilterExpression + ' AND zoneId = :zoneId';
            params.ExpressionAttributeValues[':zoneId'] = event.queryStringParameters.zoneId;
        }

        if (event?.queryStringParameters?.cameraId) {
            params.FilterExpression = params.FilterExpression + ' AND cameraId = :cameraId';
            params.ExpressionAttributeValues[':cameraId'] = event.queryStringParameters.cameraId;
        }

        if (event?.queryStringParameters?.start) { 
            params.FilterExpression = params.FilterExpression + ' AND ts >= :start';
            params.ExpressionAttributeValues[':start'] = parseInt(event.queryStringParameters.start, 10);
        }

        if (event?.queryStringParameters?.end) {
            params.FilterExpression = params.FilterExpression + ' AND ts <= :end';
            params.ExpressionAttributeValues[':end'] = parseInt(event.queryStringParameters.end, 10);
        }


        // Binning
        if (event?.queryStringParameters?.bin) {

            // TODO: respect timezone

            const binString = event?.queryStringParameters?.bin;

            // Check if bin is numeric
            const binIsNumeric = !isNaN(binString) && !isNaN(parseFloat(binString));

            let binnedDetections = [];

            if (binIsNumeric) {
                const detections = await awsHelpers.getItems(params);
                console.log(`Found ${detections.length} detections`);

                const bin = Number(binString);
                const start = event?.queryStringParameters?.start ? parseInt(event.queryStringParameters.start, 10) : Math.min(...detections.map(d => d.ts));
                const end = event?.queryStringParameters?.end ? parseInt(event.queryStringParameters.end, 10) : Math.max(...detections.map(d => d.ts));
                console.log(`Binning detections...`);
                binnedDetections = binDetections(detections, start, end, bin);
            } else {
                if (!BIN_ACCEPTED_VALUES.includes(binString)) {
                    throw {
                        statusCode: 400,
                        body: {
                            status: 'error',
                            msg: `Bad Request: invalid bin value '${binString}'. Acceptable values are: ${BIN_ACCEPTED_VALUES.join(', ')}.`
                        }
                    };
                }

                params.TableName = process.env[`DETECTIONS_BIN_${binString.toUpperCase()}_TABLE`];
                binnedDetections = await awsHelpers.getItems(params);
            }


            console.log(`Returning ${binnedDetections.length} bins`);
            response.body = JSON.stringify(binnedDetections);

        } else {
            const detections = await awsHelpers.getItems(params);
            console.log(`Found ${detections.length} detections`);

            response.body = JSON.stringify(detections);
        }

    } catch (e) {
        // Handle errors.
        console.error(e);
        response.statusCode = e.statusCode || 500;
        response.body = JSON.stringify(e.body);
    }

    // Log and return response.
    if (debug) console.log("response=", response);
    return response;
};


/**
 * Bin detections by time
 * @param {Array} detections - array of detection objects
 * @param {number} startTs - start timestamp (ms)
 * @param {number} endTs - end timestamp (ms)
 * @param {number} binSize - bin size in ms
 * @param {boolean} extended - if true, include extended stats for merging a new detection
 * @returns {Array} array of binned detection objects
 */
function binDetections(detections, startTs, endTs, binSize, extended = false) {
    // Filter detections in the time window
    const filtered = detections.filter(d => d.ts >= startTs && d.ts <= endTs);

    // Group detections by bin index
    const binsMap = new Map();

    for (const d of filtered) {
        const binIndex = Math.floor((d.ts - startTs) / binSize);
        if (!binsMap.has(binIndex)) {
            binsMap.set(binIndex, []);
        }
        binsMap.get(binIndex).push(d);
    }

    // Build result array
    const binned = [];

    for (const [binIndex, binDetections] of binsMap.entries()) {
        const tsMid = startTs + binIndex * binSize + Math.floor(binSize / 2);

        const totalSpacesArray = binDetections.map(d => d.totalSpaces);
        const occupiedSpacesArray = binDetections.map(d => d.occupiedSpaces);

        const sum = arr => arr.reduce((a, b) => a + b, 0);
        const mean = arr => Math.round(sum(arr) / arr.length);

        let bin = {
            ts: tsMid,
            customerId: binDetections[0].customerId,
            siteId: binDetections[0].siteId,
            zoneId: binDetections[0].zoneId,
            cameraId: binDetections[0].cameraId,
            minTotalSpaces: Math.min(...totalSpacesArray),
            minOccupiedSpaces: Math.min(...occupiedSpacesArray),
            meanTotalSpaces: mean(totalSpacesArray),
            meanOccupiedSpaces: mean(occupiedSpacesArray),
            maxTotalSpaces: Math.max(...totalSpacesArray),
            maxOccupiedSpaces: Math.max(...occupiedSpacesArray),
            detectionIds: binDetections.map(d => d.id)
        }

        // Extended stats to allow merging a new detection
        if (extended) {
            bin.binSize = binSize;
            bin.number = binDetections.length;
            bin.sumTotalSpaces = sum(...totalSpacesArray);
            bin.sumOccupiedSpaces = sum(...occupiedSpacesArray);
        }

        binned.push(bin);
    }

    // Sort bins by timestamp
    binned.sort((a, b) => a.ts - b.ts);

    return binned;
}


/**
 *
 *
 * @param {Object} bin - the bin to update (must be an extended bin)
 * @param {Object} detection - the detection to add
 * @returns {Object} - the updated bin
 * @throws {Error} - if the bin is not an extended bin
 */
function addDetectionToExtendedBin(bin, detection) {
    if (!bin.number) {
        throw new Error("Bin must be an extended bin (with binSize, number, and sums).");
    }

    // Update sums and counts
    bin.number += 1;
    bin.sumTotalSpaces += detection.totalSpaces;
    bin.sumOccupiedSpaces += detection.occupiedSpaces;

    // Update min/max
    bin.minTotalSpaces = Math.min(bin.minTotalSpaces, detection.totalSpaces);
    bin.maxTotalSpaces = Math.max(bin.maxTotalSpaces, detection.totalSpaces);
    bin.minOccupiedSpaces = Math.min(bin.minOccupiedSpaces, detection.occupiedSpaces);
    bin.maxOccupiedSpaces = Math.max(bin.maxOccupiedSpaces, detection.occupiedSpaces);

    // Update means (recomputed from sums)
    bin.meanTotalSpaces = Math.round(bin.sumTotalSpaces / bin.number);
    bin.meanOccupiedSpaces = Math.round(bin.sumOccupiedSpaces / bin.number);

    // Add detection ID
    bin.detectionIds.push(detection.id);

    return bin;
}
// EOF