const awsHelpers = require('/opt/awsHelpers.js');
require('/opt/patch.js');

let debug = process.env.DEBUG == "true";

exports.handler = async (event) => {
    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log(event);

    init(event);


    let response = {
        statusCode: 200,
        headers: {
            "content-type": "application/json"
        }
    };

    try {
        let connectionId = event.requestContext.connectionId;
        if (debug) console.log(`connectionId = '${connectionId}'`);
        let payload;
        switch (event.requestContext.eventType) {
            case 'CONNECT':
                if (debug) console.log('CONNECT');

                let clientId = awsHelpers.newUUID();
                if (event.queryStringParameters && event.queryStringParameters.clientIdPrefix) {
                    clientId = `${event.queryStringParameters.clientIdPrefix}_${clientId}`;
                }
                if (debug) console.log(`clientId = '${clientId}'`);

                const appType = process.env.PREFIX + "_pipeline";
                if (debug) console.log(`appType = '${appType}'`);


                const now = new Date();
                const connection = {
                    id: connectionId,
                    api: 'pipelines',
                    createdAt: now.toISOString(),
                    updatedAt: now.toISOString(),
                    clientId,
                    appType,
                    ts: now.getTime(),
                    agentId: event.headers['X-Kampus-Agent-Id'] ?? 'Undefined'
                };

                let connections = await awsHelpers.getItems({ TableName: process.env.CONNECTIONS_TABLE });
                for (let connection of connections) {
                    if (connection.clientId == clientId) {
                        await awsHelpers.deleteItem(connection.id, process.env.CONNECTIONS_TABLE);
                    }
                }

                if (debug) console.log("connection=", connection);
                await awsHelpers.putItem(connection, process.env.CONNECTIONS_TABLE);

                response.body = JSON.stringify({ status: "ok", connectionId });

                break;


            case 'DISCONNECT':
                if (debug) console.log('DISCONNECT');
                await awsHelpers.deleteItem(event.requestContext.connectionId, process.env.CONNECTIONS_TABLE);
                break;


            case 'MESSAGE':
                if (debug) console.log('MESSAGE');
                const body = JSON.parse(event.body);
                if (debug) console.log("message body=", body);

                switch (body.action) {
                    case 'ping':
                        let response = body;
                        response.action = "pong";
                        payload = JSON.stringify(response);
                        if (debug) console.log(payload);
                        await send(event.requestContext.connectionId, payload);
                        break;

                    case 'connectionId':
                        payload = JSON.stringify({ action: "connectionId", connectionId });
                        await send(connectionId, payload);
                        break;

                    default:
                        console.error(`Unsupported action "${body.action}"`);
                }
                break;

            default:
            // code
        }

    }
    catch (e) {
        console.error(e);
        response.statusCode = e.statusCode;
        response.body = JSON.stringify(e.body);
    }

    if (debug) console.log(response);
    return response;
};


let send = undefined;
function init(event) {
    const apigwManagementApi = new awsHelpers.AWS.ApiGatewayManagementApi({
        apiVersion: '2018-11-29',
        endpoint: event.requestContext.domainName + '/' + event.requestContext.stage
    });
    //console.log(event.requestContext.domainName + '/' + event.requestContext.stage);

    send = async (connectionId, data) => {
        await apigwManagementApi.postToConnection({ ConnectionId: connectionId, Data: data }).promise();
    };
}
