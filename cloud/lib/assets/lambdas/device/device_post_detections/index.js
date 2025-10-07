/**
 * Lambda: device_post_detections/index.js
 *
 * This Lambda function receives device detections via HTTP POST requests.
 * It validates and enriches each detection (UUID, customerId, timestamp), checks for uniqueness,
 * and saves the detections to DynamoDB. It enforces customerId consistency and returns the saved detections.
 * If an item's timestamp is older than the last aggregation timestamp, it updates the last aggregation timestamp
 * in order to include the new detections in the next aggregation run. This can happen when a device is offline for a while.
 *
 * Input:
 *  - event.body: JSON (array or object) containing one or more detections
 *  - event.headers: must include 'x-customer-id'
 *
 * Output:
 *  - statusCode: 200 on success, 403/404/500 on error
 *  - body: { status: "ok", detections: [...] } or error message
 *
 * Required environment variables:
 *  - LAMBDA_NAME
 *  - GENERAL_PARAMETERS_TABLE
 *  - CUSTOMERS_TABLE
 *  - DETECTIONS_TABLE
 *
 * Dependencies:
 *  - awsHelpers (custom layer)
 */

// Importing modules from the custom layer
const awsHelpers = require('/opt/awsHelpers');

let debug = process.env.DEBUG == "true";
const BIGGEST_TS = 4102444800000; // Jan 1, 2100

exports.handler = async (event, context) => {
    context.callbackWaitsForEmptyEventLoop = false;

    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log('Event:', JSON.stringify(event, null, 2));


    let response = {
        statusCode: 200,
        headers: {
            "content-type": "application/json"
        }
    };

    try {        

        // get the detections in the body
        if (!event.body) {
            throw { statusCode: 400, body: { status: 'error', msg: "Bad Request: missing body" } };
        }
        const body = event.isBase64Encoded ? (new Buffer.from(event.body, 'base64')).toString() : event.body;
        let jsonBody = JSON.parse(body);
        if (!Array.isArray(jsonBody)) {
            // if a single object, convert to array for easier processing
            jsonBody = [jsonBody];
        }
        if (debug) console.log("jsonBody=", jsonBody);


        // get the customerId from the headers and validate it
        const headers = Object.fromEntries(
            // lowervase all header keys
            Object.entries(event.headers).map(([k, v]) => [k.toLowerCase(), v])
        );
        const customerId = headers["x-customer-id"];
        if (!awsHelpers.getItemByPrimaryKey("id", customerId, process.env.CUSTOMERS_TABLE)) {
            throw { statusCode: 404, body: { status: 'error', msg: "Not found: customerId not found" } };
        }


        // If the oldest item.ts is older than last_detections_aggregation, update last_detections_aggregation to the oldest item.ts
        // This will ensure that the new detections are included in the next aggregation run.
        const last_detections_aggregation = await awsHelpers.getItemByPrimaryKey("id", "last_detections_aggregation", process.env.SYSTEM_STATES_TABLE)
            .then(item => item ? item.value : BIGGEST_TS);
        if (debug) console.log(`Last detections aggregation timestamp: ${last_detections_aggregation}`);


        let detections = [];
        let oldestTs = last_detections_aggregation;
        const now = Date.now();

        for (let detection of jsonBody) { 
            if (debug) console.log("processing detection ", detection);

            // Enforce customer consistency
            if (detection.customerId && detection.customerId !== customerId) {
                throw { statusCode: 403, body: { status: 'error', msg: `Forbidden: customerId mismatch header(${customerId})/body(${detection.customerId})` } };
            }

            // TODO; make sure siteId, zoneId, and cameraId exist and belong to customerId.

            // Auto - generate UUIDv7 if not provided
            if (!detection.id) {
                detection.id = awsHelpers.uuidv7();
            }

            // Make sure the uuid hasn't been submitted before
            if (await awsHelpers.getItemByPrimaryKey("id", detection.id, process.env.DETECTIONS_TABLE)) {
                console.warn(`detection id ${detection.id} already exists. Skipping.`);
                continue;
            }

            // Add customerId if not in body
            if (!detection.customerId) {
                detection.customerId = customerId;
            }

            // Ensure timestamp: if not provided, add now in ms
            if (!detection.ts) {
                detection.ts = (new Date()).getTime();
            }

            detection.createdAt = now;

            // Save detection
            detections.push(detection);

            if (detection.ts < oldestTs) {
                oldestTs = detection.ts;
            }
        }


        // Save all detections
        await awsHelpers.putItems(detections, process.env.DETECTIONS_TABLE);
        if (debug) console.log("Number of detections saved:", detections.length);


        // If the oldest detection ts is older than last_detections_aggregation, update last_detections_aggregation
        // to the oldest detection ts to make sure the aggregator will process it.
        if (oldestTs < last_detections_aggregation) {
            // we want the aggregator to include the new detections
            if (debug) console.log(`Oldest detection ts ${oldestTs} is older than last_detections_aggregation ${last_detections_aggregation}. Updating last_detections_aggregation.`);
            await awsHelpers.putItem(
                { id: "last_detections_aggregation", value: oldestTs },
                process.env.SYSTEM_STATES_TABLE
            );
        }


        // Return the detections saved
        response.body = JSON.stringify({ status: "ok", detections });

    } catch (e) {
        console.error(e);
        response.statusCode = e.statusCode || 500;
        response.body = JSON.stringify(e.body);
    }

    if (debug) console.log("response=", response);
    return response;
};
// EOF