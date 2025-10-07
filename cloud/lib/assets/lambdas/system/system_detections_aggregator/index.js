/**
 * Lambda: system_detections_aggregator/index.js
 *
 * @description
 * Aggregates parking detections into time-based bins: hour, day, week, month, year.
 * Hour bins aggregate directly from detections.
 * Higher bins (day, week, month, year) are rolled up from lower bins.
 * If a bin already exists, it is updated with new data. Otherwise, a new bin is created.
 * </br>
 * Designed for memory efficiency: only hour bins store detection IDs.
 * Luxon is used to handle timezone-aware binning.
 *
 * @eventbridge
 * Triggered every hour by EventBridge.
 * 
 * Environment Variables:
 * - DEBUG: Enable debug logging (true/false).
 * - LAMBDA_NAME: Name of the Lambda function.
 * - GENERAL_PARAMETERS_TABLE: DynamoDB table for general parameters.
 * - SITES_TABLE: DynamoDB table containing site information (including timezones).
 * - DETECTIONS_TABLE: DynamoDB table containing parking detections.
 * - DETECTIONS_BIN_HOUR_TABLE: DynamoDB table for hour-level aggregated bins.
 * - DETECTIONS_BIN_DAY_TABLE: DynamoDB table for day-level aggregated bins.
 * - DETECTIONS_BIN_WEEK_TABLE: DynamoDB table for week-level aggregated bins.
 * - DETECTIONS_BIN_MONTH_TABLE: DynamoDB table for month-level aggregated bins.
 * - DETECTIONS_BIN_YEAR_TABLE: DynamoDB table for year-level aggregated bins.
 * - SYSTEM_STATES_TABLE: DynamoDB table for storing system state information (e.g., last aggregation timestamp).
 * 
 * Copyright (c) 2025 Orangead Media Inc.
 * Author: Edouard Boily
 * 
 * This code belongs to Orangead Media Inc. and is not to be shared or used without permission.
 */

const DetectionAggregator = require('./DetectionAggregator.class');

// Importing modules from the custom layer
const awsHelpers = require('/opt/awsHelpers');

// Global debug flag
let debug = process.env.DEBUG == "true";

// Accepted bin levels
const BIN_ACCEPTED_VALUES = ["hour", "day", "week", "month", "year"];

// Smallest timestamp to use as default (Jan 1, 2000)
const SMALLEST_TS = 946684800000;


/**
 * AWS Lambda function handler for the detections aggregator.
 * Called from eventbridge every hour.
 * Retrieves unprocesses detections and aggregate them into time bins.
 *
 * @param {Object} event - The AWS Lambda event object.
 * @returns {Promise<Object>} - A promise that resolves to the API response.
 */
exports.handler = async (event) => {

    // Retrieve debug flag from general parameters table.
    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log('Event:', JSON.stringify(event, null, 2));

    // Initialize response object.
    let response = {
        statusCode: 200,
        headers: {
            "content-type": "application/json"
        }
    };

    try {
        const now = Date.now();
        let params = null;


        // --------------------------------------------------------
        // GET THE SITES FOR THE TIMEZONES
        const sites = await awsHelpers.getItems({ TableName: process.env.SITES_TABLE });
        let timezoneBySiteId = {};
        for (const site of sites) {
            timezoneBySiteId[site.id] = site.timezone || "UTC";
        }


        // --------------------------------------------------------
        // GET LAST AGGREGATION TIMESTAMP FROM SYSTEM_STATES TABLE
        const last_detections_aggregation = await awsHelpers.getItemByPrimaryKey("id", "last_detections_aggregation", process.env.SYSTEM_STATES_TABLE)
            .then(item => item ? item.value : SMALLEST_TS);
        if (debug) console.log(`Last detections aggregation timestamp: ${last_detections_aggregation}`);


        // --------------------------------------------------------
        // GET DETECTIONS STARTING FROM LAST AGGREGATION TIMESTAMP
        params = {
            TableName: process.env.DETECTIONS_TABLE,
            FilterExpression: 'ts >= :last_detections_aggregation',
            ExpressionAttributeValues: {
                ':last_detections_aggregation': last_detections_aggregation
            }
        };

        const detections = await awsHelpers.getItems(params);
        if (debug) console.log(`Found ${detections.length} new detections since last aggregation.`);

        if (detections.length === 0) {
            response.body = JSON.stringify({ status: "no new detections to aggregate" });
            return response;
        }


        // --------------------------------------------------------
        // AGGREGATE DETECTIONS INTO BINS

        // Initialize the DetectionAggregator class
        const aggregator = new DetectionAggregator();

        // Get existing bins to update
        const existingBins = await getExistingBins(last_detections_aggregation);

        // Perform aggregation
        if (debug) {
            console.log("Existing bins...");
            for (const level of BIN_ACCEPTED_VALUES) { 
                console.log(`  - ${existingBins[`${level}Bins`].length} existing ${level} bins`);
            }
        }
        const updatedBins = aggregator.aggregate(detections, existingBins);
        if (debug) {
            console.log("Updated bins...");
            for (const level of BIN_ACCEPTED_VALUES) {
                console.log(`  - ${updatedBins[`${level}Bins`].length} updated ${level} bins`);
            }
        }


        // --------------------------------------------------------
        // STORE THE NEW BINS IN THEIR RESPECTIVE TABLES

        // Store new bins in their respective tables while keeping reporting details
        let numberOfBinsUpdated = {
            total: 0,
            hour: 0,
            day: 0,
            week: 0,
            month: 0,
            year: 0
        };
        for (const level of BIN_ACCEPTED_VALUES) {
            if (updatedBins[`${level}Bins`].length > 0) {
                await awsHelpers.putItems(updatedBins[`${level}Bins`], process.env[`DETECTIONS_BIN_${level.toUpperCase()}_TABLE`]);
                numberOfBinsUpdated.total += updatedBins[`${level}Bins`].length;
                numberOfBinsUpdated[level] = updatedBins[`${level}Bins`].length;
            }
        }

        // Update last aggregation timestamp in SYSTEM_STATES table
        await awsHelpers.putItem({ id: "last_detections_aggregation", value: now }, process.env.SYSTEM_STATES_TABLE);

        // Return success response.
        const message = `Aggregated ${detections.length} new detections.`;
        console.log(message);
        console.log("Bin update details:", numberOfBinsUpdated);
        response.body = JSON.stringify({ status: "success", message });

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
 * Fetch existing bins from DynamoDB starting from two hours before the last aggregation timestamp.
 *
 * @param {number} last_detections_aggregation - The timestamp of the last detections aggregation.
 * @returns {Promise<Object>} - An object containing arrays of existing bins for each level:
 * <ul>
 *   <li>hourBins</li>
 *   <li>dayBins</li>
 *   <li>weekBins</li>
 *   <li>monthBins</li>
 *   <li>yearBins</li>
 * </ul>
 */
async function getExistingBins(last_detections_aggregation) { 

    // Get existing bins to update
    let existingBins = {};
    const twoHoursBefore = last_detections_aggregation - (2 * 60 * 60 * 1000);
    if (debug) console.log(`Fetching existing bins starting from ${twoHoursBefore}...`);

    for (const level of BIN_ACCEPTED_VALUES) {
        const TableName = process.env[`DETECTIONS_BIN_${level.toUpperCase()}_TABLE`];
        if (!TableName) {
            throw new Error(`Environment variable DETECTIONS_BIN_${level.toUpperCase()}_TABLE is not set.`);
        }

        let fromTs = 0
        switch (level) {
            case "hour":
                // we get bins two hours before last aggregation because last_detections_aggregation may 
                // be in the middle of an hour. We play safe to ensure we catch any late arrivals and the cost
                // is minimal.
                fromTs = last_detections_aggregation - (2 * 60 * 60 * 1000);
                break;

            case "day":
                // we get bins two weeks before last aggregation because last_detections_aggregation may 
                // be in the middle of a week. We play safe to ensure we catch any late arrivals and the cost
                // is minimal. Same for the rest below.
                fromTs = last_detections_aggregation - (2 * 24 * 60 * 60 * 1000);
                break;

            case "week":
                fromTs = last_detections_aggregation - (2 * 7 * 24 * 60 * 60 * 1000);
                break;

            case "month":
                fromTs = last_detections_aggregation - (2 * 31 * 24 * 60 * 60 * 1000);
                break;

            case "year":
                fromTs = last_detections_aggregation - (2 * 12 * 31 * 24 * 60 * 60 * 1000);
                break;
        }

        params = {
            TableName,
            FilterExpression: 'startTs >= :fromTs',
            ExpressionAttributeValues: {
                ':fromTs': fromTs
            }
        };
        existingBins[`${level}Bins`] = await awsHelpers.getItems(params);
    }

    return existingBins;
}

// EOF