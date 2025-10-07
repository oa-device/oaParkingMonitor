// editor_actor_login/index.js

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
        if (!event.queryStringParameters && event.queryStringParameters.username && event.queryStringParameters.password) {
            throw { statusCode: 400, body: { status: 'error', msg: "Bad request." } };
        }
        const username = event.queryStringParameters.username;
        const password = event.queryStringParameters.password;


        // Authenticate user
        let actorsParams = {
            "TableName": process.env.ACTORS_TABLE,
            FilterExpression: "#username = :username",
            ExpressionAttributeNames: { "#username": "username" },
            ExpressionAttributeValues: { ":username": username }
        };
        const actors = await awsHelpers.getItems(actorsParams);
        if (actors.length == 0) {
            throw { statusCode: 401, body: { status: 'error', msg: "Unauthorized. Bad username or password." } };
        }
        if (actors.length > 1) {
            console.error(`More than 1 actor with username=${username}`, actors);
            const now = Date.now();
            const anomaly = {
                createdAt: now,
                updatedAt: now,
                category: "Table",
                description: `More than 1 actor with username=${username}: ${JSON.stringify(actors)}`,
                origin: `lambda ${process.env.LAMBDA_NAME}`
            }
            await awsHelpers.putItem(anomaly, process.env.ANOMALIES_TABLE);
        }
        const actor = actors[0];
        if ((await awsHelpers.hashPassword(password, actor.id)) !== actor.hashedPassword) {
            throw { statusCode: 401, body: { status: 'error', msg: "Unauthorized. Bad username or password." } };
        }


        // We don't care if there already is another session for this user, just create a new session.
        // The user has to save this session in a cookie and reuse if from there.
        // This allows to have multiple sessions on multiple browsers.


        // Create session
        const tokenDuration = await awsHelpers.getGeneralParameter(`editor_user_session_duration`, process.env.GENERAL_PARAMETERS_TABLE, 86400);
        const now = new Date();
        const session = {
            token: awsHelpers.newUUID(),
            userId: actor.id,
            userRoles: actor.roles,
            expiration: Math.floor(now.getTime() / 1000) + tokenDuration,
            createdOn: now.toISOString()
        };
        await awsHelpers.putItem(session, process.env.SESSIONS_TABLE);


        // Add log entry
        await awsHelpers.logs(actor.id, "login", session, process.env.LOGS_TABLE);


        // Update user last login
        const patches = [
            { "op": "replace", "path": "/lastLogin", "value": now.toISOString() }
        ];
        await awsHelpers.updateItem(patches, actor, process.env.ACTORS_TABLE);


        // Return the new session
        response.body = JSON.stringify(session);

    } catch (e) {
        console.error(e);
        response.statusCode = e.statusCode || 500;
        response.body = JSON.stringify(e.body);
    }

    if (debug) console.log("response=", response);
    return response;
};
