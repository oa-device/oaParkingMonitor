// device_api_authorizer/index.js

// Importing modules from the custom layer
const awsHelpers = require('/opt/awsHelpers');

let debug = process.env.DEBUG == "true";

exports.handler = async (event) => {
    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log(event);

    let policyDocument;
    let response;
    let principalId = "agent";

    try {

        // Deny if invalid API key

        if (process.env.X_API_KEY != event.headers['x-api-key']) {
            if (debug) console.log('Denied: Invalid API key.');
            throw { type: "effect", effect: "Deny" };
        }
        if (debug) console.log('Valid API key.');

        policyDocument = getPolicyDocument(event, "Allow");

        response = {
            principalId,
            policyDocument
        };

    } catch (e) {
        console.error("Error: ", e);
        if (e.type == "effect") {
            policyDocument = getPolicyDocument(event, e.effect);
        } else {
            policyDocument = getPolicyDocument(event, 'Deny');
        }
        response = {
            policyDocument
        };
        if (principalId) {
            response.principalId = principalId;
        }
    }

    if (debug) console.log(`response => ${JSON.stringify(response)}`);
    return response;
};


function getPolicyDocument(event, Effect) {
    return {
        Version: '2012-10-17',
        Statement: [
            {
                Action: 'execute-api:Invoke',
                Effect,
                Resource: event.methodArn
            },
        ],
    };
}
