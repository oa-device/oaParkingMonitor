let awsHelpers = null;
if (!process.env.LAMBDA_NAME) {
    process.env.LAMBDA_NAME = "editor_api_authorizer";
    //require("dotenv").config(); // Load .env variables if needed
    console.log('__dirname=', __dirname);
    awsHelpers = require("../../layers/awsHelpers/awsHelpers");
    awsHelpers.setupLogging(process.env.LAMBDA_NAME);
} else {
    awsHelpers = require("/opt/awsHelpers");
}


let debug = process.env.DEBUG == "true";


// when used locally as a forked process
process.on('message', async (message) => {
    console.log('----------------------------------------------------');
    if (message.type === 'REQUEST') {
        try {
            const result = await handler(message.event);
            process.send({
                type: 'RESPONSE',
                data: result
            });
        } catch (error) {
            process.send({
                type: 'ERROR',
                error: {
                    statusCode: 500,
                    body: JSON.stringify({ error: error.message })
                }
            });
        }
    }
});


const handler = async function (event) {
    debug = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_debug`, process.env.GENERAL_PARAMETERS_TABLE, debug);
    if (debug) console.log(event);

    let policyDocument = null;
    let principalId = 'unknown';
    let token = null;
    let user = null;
    let routeKeyPermissions = null;

    try {
        //throw { type: "effect", effect: "Allow" };

        const activeAuthorizer = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_activated`, process.env.GENERAL_PARAMETERS_TABLE, true);
        console.log('activeAuthorizer=', activeAuthorizer);
        if (!activeAuthorizer) {
            if (debug) console.log('Allow: Authorizer not active.');
            throw { type: "effect", effect: "Allow" };
        }


        if (!event.headers?.['x-api-key']) {
            if (debug) console.error("Deny: Missing required 'x-api-key' header.");
            throw { type: "effect", effect: "Deny" };
        }


        // If the path is login, always allow
        const logPaths = ['/login', '/logout'];
        if (logPaths.includes(event.path) || logPaths.includes(event.rawPath)) {
            if (debug) console.log(`Allow: login or logout`);
            throw { type: "effect", effect: "Allow" };
        }


        if (!event.headers?.['x-auth-token']) {
            if (debug) console.error("Deny: Missing required 'x-auth-token' header.");
            throw { type: "effect", effect: "Deny" };
        }


        // Deny if invalid API key
        const validateApiKey = await awsHelpers.getGeneralParameter(`lambda_${process.env.LAMBDA_NAME}_validateApiKey`, process.env.GENERAL_PARAMETERS_TABLE, true);
        if (validateApiKey && process.env.X_API_KEY != event.headers['x-api-key']) {
            if (debug) console.error('Deny: Invalid API key.');
            throw { type: "effect", effect: "Deny" };
        }
        if (debug) console.log('Valid API key.');


        // Deny if no token or token is expired
        token = await awsHelpers.getItemByPrimaryKey("token", event.headers['x-auth-token'], process.env.SESSIONS_TABLE);
        if (!token) {
            if (debug) console.error('Denied: Invalid token.');
            throw { type: "effect", effect: "Deny" };
        }
        if (token.expiration <= Date.now() / 1000) {
            if (debug) console.error('Deny: Token expired.');
            throw { type: "effect", effect: "Deny" };
        }
        if (debug) console.log('Valid token.');
        principalId = token.userId;
        user = await awsHelpers.getItemByPrimaryKey("id", token.userId, process.env.ACTORS_TABLE);


        // Allow if admin
        if (user?.roles.includes('admin')) {
            if (debug) console.log('Allow: User is an admin.');
            throw { type: "effect", effect: "Allow" };
        }


        // Is the current route allowed to this user according to his roles
        if (!event.routeKey) {
            console.error("event.routeKey not found!!!");
            throw { type: "effect", effect: "Deny" };
        }
        routeKeyPermissions = await awsHelpers.getItemByPrimaryKey("id", event.routeKey, process.env.PERMISSIONS_TABLE);
        if (debug) console.log('routeKeyPermissions=', routeKeyPermissions);
        if (!routeKeyPermissions) {
            const message = `Table ${process.env.PERMISSIONS_TABLE} is missing an entry for id '${event.routeKey}'.`;
            console.error(message);
            await recordAnomaly(event.routeKey, 'route', message);
            throw { type: "effect", effect: "Deny" };
        }
        if (!userIsAllowedThisRoute(user, routeKeyPermissions)) {
            if (debug) console.log('Deny: User not allowed this route.');
            throw { type: "effect", effect: "Deny" };
        }


        policyDocument = generatePolicy('Allow', event.routeArn);

    } catch (e) {
        if (e.type == "effect") {
            if (debug) console.log(e);
            policyDocument = generatePolicy(e.effect, event.routeArn);
        } else {
            if (debug) console.error("Catch: ", e);
            policyDocument = generatePolicy('Deny', event.routeArn);
        }
    }


    let response = {
        principalId,
        policyDocument,
        context: {
            token,
            user,
            routeKeyPermissions
        }
    };


    console.log(JSON.stringify(response, null, 2));
    return response;
};
exports.handler = handler;


const generatePolicy = (effect, resource) => {
    console.log('generatePolicy:', effect, resource);
    let policyDocument = {};

    if (effect && resource) {
        if (debug) console.log('creating policy document');
        policyDocument.Version = '2012-10-17';
        policyDocument.Statement = [];

        let statementOne = {};
        statementOne.Action = 'execute-api:Invoke';
        statementOne.Effect = effect;
        statementOne.Resource = resource;

        policyDocument.Statement.push(statementOne);
    }

    if (debug) console.log('policyDocument=', policyDocument);

    return policyDocument;
};



const userIsAllowedThisRoute = (user, routeKeyPermissions) => {
    if (!user) {
        if (debug) console.log('Deny: User not resolved.');
        return false;
    }
    let allowedKeys = ['allow', 'self', 'child'];
    for (let role of user.roles) {
        if (debug) console.log('routeKeyPermissions[role]=', routeKeyPermissions[role])
        if (hasIntersection(routeKeyPermissions[role], allowedKeys)) {
            return true;
        }
    }
    return false;
}

/**
 * Returns true if arrays have a common element. False otherwise.
 * Only support arrays of primitive types.
 * Doesn't support array of Objects.
 *
 * @param {Array} a
 * @param {Array} b
 * @returns {Boolean}
 */
function hasIntersection(a, b) {
    const setA = new Set(a);
    return (b.filter(value => setA.has(value))).length > 0;
}