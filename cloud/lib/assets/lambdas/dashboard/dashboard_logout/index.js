// editor_user_logout/index.js

// Importing modules from the custom layer
const awsHelpers = require('/opt/awsHelpers');


let debug = process.env.DEBUG == "true";

exports.handler = async (event) => {
    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log(event);

    let response = {
        statusCode: 200,
        headers: {
            "content-type": "application/json"
        }
    };

    try {

        // Delete session
        const token = event.headers['x-auth-token'];
        await awsHelpers.deleteItem(token, process.env.SESSIONS_TABLE, "token");

        response.body = JSON.stringify({"status":"ok"});

    } catch (e) {
        console.error(e);
        response.statusCode = e.statusCode || 500;
        response.body = JSON.stringify(e.body);
    }

    if (debug) console.log("response=", response);
    return response;
};
