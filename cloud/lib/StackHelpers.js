const cdk = require('aws-cdk-lib');
const dynamodb = require("aws-cdk-lib/aws-dynamodb");
const s3 = require("aws-cdk-lib/aws-s3");
const s3n = require('aws-cdk-lib/aws-s3-notifications');
const s3deploy = require('aws-cdk-lib/aws-s3-deployment');
const Lambda = require("aws-cdk-lib/aws-lambda");
const { LayerVersion, Function, Code } = require('aws-cdk-lib/aws-lambda');
const LambdaEventSources = require('aws-cdk-lib/aws-lambda-event-sources');
const Iam = require("aws-cdk-lib/aws-iam");
const apigwv2 = require('aws-cdk-lib').aws_apigatewayv2;
const { PayloadFormatVersion } = require('aws-cdk-lib/aws-apigatewayv2');
const { WebSocketLambdaIntegration, HttpLambdaIntegration, integration } = require('aws-cdk-lib/aws-apigatewayv2-integrations');
const { DynamoEventSource, S3EventSource } = require('aws-cdk-lib/aws-lambda-event-sources');
const { aws_events: Events, aws_events_targets: Targets } = require('aws-cdk-lib');
const { HttpLambdaAuthorizer, HttpLambdaResponseType, AuthorizerPayloadVersion } = require('aws-cdk-lib/aws-apigatewayv2-authorizers');
const sns = require('aws-cdk-lib/aws-sns');
const subs = require('aws-cdk-lib/aws-sns-subscriptions');

const Graph = require('./Graph.class');

class StackHelpers {

    static debug = false;
    graph = new Graph();

    /**
     * @param {HTMLTableElement} root The table element which will display the CSV data.
     */
    constructor(root) {
        this.root = root;
    }
    
    static createTable(stackClass, tableSpec, props) {
        const fullTableName = getFullName(tableSpec.name, props);
        const graph = new Graph();
        graph.addNode("Table", tableSpec.name, tableSpec);
        if (StackHelpers.debug) if (StackHelpers.debug) console.log(`Creating table ${fullTableName}`);

        let options = {
            tableName: fullTableName,
            partitionKey: {
                name: tableSpec.partitionKey ? tableSpec.partitionKey : 'id',
                type: tableSpec.partitionKeyType ? dynamodbAttributeTypeOf(tableSpec.partitionKeyType) : dynamodb.AttributeType.STRING
            },
            pointInTimeRecovery: tableSpec.pointInTimeRecovery ? tableSpec.pointInTimeRecovery : true,
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            removalPolicy: cdk.RemovalPolicy.RETAIN,
        };

        if (tableSpec.enableStream) {
            options.stream = dynamodb.StreamViewType.NEW_AND_OLD_IMAGES;
        }

        if (tableSpec.timeToLiveAttribute) {
            options.timeToLiveAttribute = tableSpec.timeToLiveAttribute;
        }

        if (tableSpec.sortKey) {
            options.sortKey = {
                name: tableSpec.sortKey,
                type: tableSpec.sortKeyType ? dynamodbAttributeTypeOf(tableSpec.sortKeyType) : dynamodb.AttributeType.STRING
            }
        }

        if (tableSpec.timeToLiveAttribute) {
            options.timeToLiveAttribute = tableSpec.timeToLiveAttribute;
        }

        if (StackHelpers.debug) console.log(`options=`, options);
        let table = new dynamodb.Table(stackClass, fullTableName, options);
        if (StackHelpers.debug) console.log(table);

        if (tableSpec.secondaryIndexes && tableSpec.secondaryIndexes.length > 0) {
            for (let secondaryIndex of tableSpec.secondaryIndexes) {
                table.addGlobalSecondaryIndex({
                    indexName: `${secondaryIndex}Index`,
                    partitionKey: { name: secondaryIndex, type: dynamodb.AttributeType.STRING },
                    projectionType: dynamodb.ProjectionType.ALL,
                });
            }
        }

        // // add indexes (experimental)
        // if (tableSpec.indexes && tableSpec.indexes.length > 0) { 
        //     for (let index of tableSpec.indexes) { 
        //         let params = {
        //             indexName: index.name, // Replace with the desired index name
        //             projectionType: dynamodb.ProjectionType.ALL, // Replace with the desired projection type (e.g., ALL, KEYS_ONLY, INCLUDE)
        //         }
        //         if (index.partitionKeyName && index.partitionKeyType) { 
        //             params.partitionKey = {
        //                 name: index.partitionKeyName, // Replace with the desired partition key attribute name
        //                 type: dynamodbAttributeTypeOf(index.partitionKeyType), // Replace with the data type of the partition key attribute
        //             }
        //         }
        //         if (index.sortKeyName && index.sortKeyType) { 
        //             params.sortKey = {
        //                 name: index.sortKeyName, // ReppartitionKeyTypelace with the desired sort key attribute name (if applicable)
        //                 type: dynamodbAttributeTypeOf(index.sortKeyType), // Replace with the data type of the sort key attribute (if applicable)
        //             }
        //         }
        //         table.addGlobalSecondaryIndex(params);
        //     }
        // }

        return table;
    }


    static createBucket(stackClass, bucketSpec, props, buckets) {
        const fullBucketName = getFullName(bucketSpec.name, props, '-');

        const graph = new Graph();
        graph.addNode("Bucket", bucketSpec.name + "_bucket", bucketSpec);

        if (StackHelpers.debug) console.log(`Creating bucket ${fullBucketName}`);

        let bucketProps = {
            bucketName: fullBucketName,
            accessControl: s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            removalPolicy: cdk.RemovalPolicy.RETAIN
        };

        if (bucketSpec.vault) { 
            bucketProps.versioned = true;                                           // Keep previous versions for safety
            bucketProps.encryption = s3.BucketEncryption.S3_MANAGED;                   // Encrypt with S3-managed keys (AES-256)
            bucketProps.blockPublicAccess = s3.BlockPublicAccess.BLOCK_ALL;            // Completely block public access
            bucketProps.objectOwnership = s3.ObjectOwnership.BUCKET_OWNER_ENFORCED;    // Prevent ACL overrides
            bucketProps.enforceSSL = true;                                          // Require SSL for access
            bucketProps.removalPolicy = cdk.RemovalPolicy.RETAIN;                   // Prevent bucket deletion
            bucketProps.autoDeleteObjects = false;                                  // Prevent accidental object deletion
        }
        
        // https://aws.amazon.com/fr/about-aws/whats-new/2022/12/amazon-s3-automatically-enable-block-public-access-disable-access-control-lists-buckets-april-2023/
        let bucket = new s3.Bucket(stackClass, fullBucketName, bucketProps);
        if (bucketSpec.loggingBucketName) {
            if (buckets.hasOwnProperty(bucketSpec.loggingBucketName)) {
                bucket.serverAccessLogsBucket = buckets[bucketSpec.loggingBucketName];
                bucket.serverAccessLogsPrefix = 'logs';
            }
        }
        if (bucketSpec.vault) {
            // Prevent Delete & Modification (Write-Once, Read-Many)
            bucket.addToResourcePolicy(
                new Iam.PolicyStatement({
                    effect: Iam.Effect.DENY,
                    actions: ["s3:DeleteObject", "s3:PutObject", "s3:PutObjectAcl"],
                    resources: [`${bucket.bucketArn}/*`],
                    principals: [new cdk.aws_iam.AnyPrincipal()], // Deny delete/modification to everyone
                })
            );

            // Allow AWS Console Access (For Admins)
            bucket.addToResourcePolicy(
                new Iam.PolicyStatement({
                    effect: Iam.Effect.ALLOW,
                    actions: ["s3:ListBucket", "s3:GetObject", "s3:GetBucketVersioning"],
                    resources: [bucket.bucketArn, `${bucket.bucketArn}/*`],
                    principals: [new cdk.aws_iam.AccountRootPrincipal()], // Only AWS account admin can list/view
                })
            );
        }


        // const fullLoggingBucketName = getFullName('logging', props, '-');
        // console.log(fullLoggingBucketName);
        // const loggingBucket = new s3.Bucket(stackClass, fullLoggingBucketName, {
        //     bucketName: fullLoggingBucketName,
        //     accessControl: s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
        //     removalPolicy: cdk.RemovalPolicy.DESTROY, // tmp bucket. Delete if removed from here.
        // });

        // bucket.addLogging({
        //     targetBucket: loggingBucket,
        //     targetPrefix: 'logs/',
        // });


        if (bucketSpec.public) {

            const bucketPolicy = new s3.BucketPolicy(stackClass, 'MyBucketPolicy', {
                bucket,
            });

            bucketPolicy.document.addStatements(
                new Iam.PolicyStatement({
                    effect: Iam.Effect.ALLOW,
                    principals: [new Iam.AnyPrincipal()],
                    actions: ['s3:ListBucket', 's3:GetObject'],
                    resources: [`arn:aws:s3:::${fullBucketName}`]
                })
            );

            // bucketPolicy.document.addStatements(
            //     new Iam.PolicyStatement({
            //         effect: Iam.Effect.ALLOW,
            //         principals: [new Iam.AnyPrincipal()],
            //         actions: ['s3:GetObject'],
            //         resources: [`arn:aws:s3:::${fullBucketName}/*`]
            //     })
            // );

            if (bucketSpec.allowedOrigins) {
                bucket.addCorsRule({
                    allowedOrigins: bucketSpec.allowedOrigins,
                    allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET],
                    allowedHeaders: ['*']
                });

            }

        }


        // Upload initial content
        // We comment this because this will wipe the bucket's content and replace it with our local content.
        // This is WAY too dangerous, so it is disabled.
        // new s3deploy.BucketDeployment(stackClass, `${fullBucketName}-Files`, {
        //     sources: [s3deploy.Source.asset(`${props.assetsDir}s3/${bucketSpec.name}`)],
        //     destinationBucket: bucket,
        // });

        return bucket;
    }


    static createSNS(stackClass, snsSpec, props) {
        const fullSNSName = getFullName(snsSpec.topic, props, '-');
        if (StackHelpers.debug) console.log("fullSNSName=", fullSNSName);

        const snsTopic = new sns.Topic(stackClass, `${snsSpec.topic}Topic`, {
            topicName: snsSpec.topic
        });
        //graph.addNode("SNS", snsSpec.topic, snsSpec);


        // Subscribe an email endpoint to the topic
        if (snsSpec.emailSubscriptions) {
            for (let emailSubscription of snsSpec.emailSubscriptions) {
                snsTopic.addSubscription(new subs.EmailSubscription(emailSubscription));
            }
        }

        // Subscribe an sms endpoint to the topic
        // Make sure to provide the phone number in E.164 format (i.e., +<country code><number>).
        // Example: +1234567890 where + 1 is the country code for the US.
        // The SMS subscription does not require confirmation like the email subscription.
        if (snsSpec.smsSubscriptions) {
            for (let smsSubscription of snsSpec.smsSubscriptions) {
                snsTopic.addSubscription(new subs.SmsSubscription(smsSubscription));
            }
        }

        return snsTopic;
    }


    static createLayer(stackClass, layerSpec, props) {

        const layername = getFullName(layerSpec.name, props, "");
        if (StackHelpers.debug) console.log("layername=", layername);

        const graph = new Graph();
        graph.addNode("Layer", layerSpec.name, layerSpec);


        let properties = {
            layerVersionName: layername,
            code: Lambda.Code.fromAsset(`${props.assetsDir}layers/${layerSpec.name}`),
            compatibleRuntimes: [Lambda.Runtime.NODEJS_16_X, Lambda.Runtime.NODEJS_20_X],
            license: 'Apache-2.0',
            description: layerSpec.description,
            compatibleArchitectures: [Lambda.Architecture.X86_64, Lambda.Architecture.ARM_64],
            removalPolicy: cdk.RemovalPolicy.RETAIN, // keeping old versions is more resilient to stack rollback failures.
        }

        // A layer can use and depends on other layers.
        if (layerSpec.layers) {
            properties.layers = [];
            for (const layer of layerSpec.layers) {
                const layerFullName = getFullName(layer.name, props, "");
                const layerVersionNumber = props.layerVersion[layer.name][props.environment];
                const layerArn = `arn:aws:lambda:${props.region}:${props.account}:layer:${layerFullName}:${layerVersionNumber}`;
                const layerVersion = LayerVersion.fromLayerVersionArn(stackClass, UUID(), layerArn);
                properties.layers.push(layerVersion)
            }
        }

        let currentLayer = new Lambda.LayerVersion(stackClass, layername, properties);

        return currentLayer;
    }


    static allLambdasProps(stackClass, props) {
        let lambdasProps = {
            runtime: props.runtime,
            architecture: props.architecture,
            handler: props.handler,
            timeout: props.timeout,
            logRetention: props.logRetention,
            memorySize: props.memorySize,
            environment: {
                PREFIX: props.prefix,
                ENVIRONMENT: props.environment,
                DEBUG: props.defaultDebug,
                VERSION: props.version,
                REGION: props.region
            }
        }

        return lambdasProps;
    }


    static createLambda(stackClass, lambdaSpec, lambdasProps, props) {

        const lambdaFullName = getFullName(lambdaSpec.name, props);
        //console.log(`Creating lambda ${lambdaFullName}`);

        const graph = new Graph();
        graph.addNode("Lambda", lambdaSpec.name, lambdaSpec);


        lambdasProps.environment.LAMBDA_NAME = lambdaSpec.name;


        if (lambdaSpec.layers) {
            let layers = [];

            // Sort layers by name (or another property, if needed)
            const sortedLayers = lambdaSpec.layers.sort((a, b) => {
                return a.name.localeCompare(b.name);
            });
            
            for (const layerSpec of sortedLayers) {
                const layerFullName = getFullName(layerSpec.name, props, "");
                if (StackHelpers.debug) console.log(`Adding layer ${layerSpec.name} to lambda ${lambdaSpec.name}`);

                // get the layer version number from the props. Each env may have a different number depending on how often
                // we updated the layer. Until we find a way to get the latest version number of a layer, we hardcode this info
                // in the props. We still allow a specific lambda to use its own layer version by setting layerSpec.version.
                const layerVersionNumber = props.layerVersion[layerSpec.name][props.environment];

                const layerArn = `arn:aws:lambda:${props.region}:${props.account}:layer:${layerFullName}:${layerVersionNumber}`;
                const layerVersion = LayerVersion.fromLayerVersionArn(stackClass, lambdaFullName+layerFullName, layerArn);

                layers.push(layerVersion);
            }

            if (layers.length > 0) {
                lambdasProps.layers = layers;
            }
        }

        const codeAsset = `${props.assetsDir}lambdas/${stackClass.lambdasSubdir ?? ""}/${lambdaSpec.name}`;
        let lambdaOptions = {
            functionName: lambdaFullName,
            code: Lambda.Code.fromAsset(codeAsset),
            bundling: {
                image: props.runtime.bundlingImage,
                command: [
                    'bash', '-c',
                    'if [ -f package.json ]; then npm install; fi && cp -r . /asset-output',
                ]
            },
            description: lambdaSpec.description,
            ...lambdasProps
        }

        const lambda = new Lambda.Function(stackClass, lambdaFullName, lambdaOptions);

        if (lambdaSpec.environment_variables) {
            const variables = Object.keys(lambdaSpec.environment_variables);
            const env = lambdasProps.environment.ENVIRONMENT;
            for (let variable of variables) {
                const value = lambdaSpec.environment_variables[variable][env];
                if (!value) {
                    throw new Error(`Environment variable '${variable}' undefined in lambda spec '${lambdaSpec.name}' for environment '${env}'.`);
                }
                lambda.addEnvironment(variable, value);
            }
        }


        // Grant Lambda permission to publish to the SNS topic
        if (lambdaSpec.notifications) {
            for (let notification of lambdaSpec.notifications) {
                if (!props.storageStack[notification.topic]) { 
                    throw new Error(`Cannot give permission to lambda ${lambdaSpec.name} to post to sns ${notification.topic}.`);
                }
                props.storageStack[notification.topic].grantPublish(lambda);
            }
        }


        return lambda;
    }


    static grantTableAccess(stackClass, lambda, lambdaSpec, props) {
        const graph = new Graph();

        if (lambdaSpec.tables) {
            let tablesAlreadyInEnvironment = [];

            // Read tables
            if (lambdaSpec.tables.read) {
                for (let read of lambdaSpec.tables.read) {
                    const tableKey = read.toUpperCase() + "_TABLE";
                    const fullTableName = getFullName(read, props);

                    graph.addEdge(lambdaSpec.name, "reads", read);


                    if (!tablesAlreadyInEnvironment.includes(read)) {
                        if (StackHelpers.debug) console.log(`Adding environment variable ${tableKey}=${fullTableName}`);
                        lambda.addEnvironment(tableKey, fullTableName);
                        tablesAlreadyInEnvironment.push(read);
                    }

                    if (StackHelpers.debug) console.log(`Allowing reading table ${read}`);
                    const tableArn = `arn:aws:dynamodb:${props.region}:${props.account}:table/${fullTableName}*`;
                    const table = dynamodb.Table.fromTableArn(stackClass, UUID(), tableArn);
                    table.grantReadData(lambda);
                }
            }

            // Write tables
            if (lambdaSpec.tables.write) {
                for (let write of lambdaSpec.tables.write) {
                    const tableKey = write.toUpperCase() + "_TABLE";
                    const fullTableName = getFullName(write, props);

                    graph.addEdge(lambdaSpec.name, "writes", write);


                    if (!tablesAlreadyInEnvironment.includes(write)) {
                        if (StackHelpers.debug) console.log(`Adding environment variable ${tableKey}=${fullTableName}`);
                        lambda.addEnvironment(tableKey, fullTableName);
                        tablesAlreadyInEnvironment.push(write);
                    }

                    if (StackHelpers.debug) console.log(`Allowing writing table ${write}`);
                    const tableArn = `arn:aws:dynamodb:${props.region}:${props.account}:table/${fullTableName}`;
                    let table = dynamodb.Table.fromTableArn(stackClass, UUID(), tableArn);
                    table.grantWriteData(lambda);
                }
            }

        }
    }


    static grantKmsAccess(stackClass, lambda, lambdaSpec, props) {
        if (lambdaSpec.kms) {
            for (let kms of lambdaSpec.kms) {

                // Define the KMS actions to be allowed for this function
                let kmsActions = [
                    'kms:GetPublicKey'
                ];
                if (kms.methods.includes('crypt')) { 
                    kmsActions.push('kms:Encrypt');
                    kmsActions.push('kms:Decrypt');
                }
                if (kms.methods.includes('sign')) {
                    kmsActions.push('kms:Sign');
                    kmsActions.push('kms:Verify');
                }


                const keyArn = `arn:aws:kms:${props.region}:${props.account}:key/${props[kms.key]}`;
                
                // Create a policy statement with these permissions
                const kmsPolicyStatement = new Iam.PolicyStatement({
                    actions: kmsActions,
                    resources: [keyArn],
                });

                // Attach the policy to the Lambda function's execution role
                lambda.addToRolePolicy(kmsPolicyStatement);

                lambda.addEnvironment(`${kms.key}Arn`, keyArn);
            }
        }
    }


    /**
     * Grant a lambda the permission to invoke other lambdas.
     *
     * @static
     * @param {Object} stackClass - current context
     * @param {Object} lambdaSpec - the current lambda
     * @param {[Object]} lambdas - all lambdas
     * @memberof StackHelpers
     */
    static grantPermissionToInvokeLambda(stackClass, lambdaSpec, lambdas) {
        if (lambdaSpec.lambdas) {
            const lambda = lambdas[lambdaSpec.name];

            for (let lambdaNameToInvoke of lambdaSpec.lambdas) {
                const lambdaToInvoke = lambdas[lambdaNameToInvoke];

                // 👇 add the policy to the invoking function's role
                lambda.role.attachInlinePolicy(
                    new Iam.Policy(stackClass, 'invoke-lambda-policy', {
                        statements: [new Iam.PolicyStatement({ actions: ['lambda:InvokeFunction'], resources: [lambdaToInvoke.functionArn] })],
                    }),
                );
            }
        }

    }


    /**
     * Set event sources to invoke a lambda. The event surce can be an S3 trigger, 
     * a DynamoDB table trigger or EventBridge.
     *
     * @static
     * @param {Object} stackClass - current context
     * @param {Object} lambdaSpec - the current lambda
     * @param {[Object]} lambdas - all lambdas
     * @param {Object} props - Multistack application properties
     * @memberof StackHelpers
     */
    static setEventSources(stackClass, lambdaSpec, lambdas, props) {
        const graph = new Graph();
        const lambda = lambdas[lambdaSpec.name];
        if (lambdaSpec.eventSources) {

            for (let eventSource of lambdaSpec.eventSources) {

                switch (eventSource.type) {
                    case "bucket":
                        const bucket = props.storageStack.buckets[eventSource.name];

                        for (let name of eventSource.names) {
                            graph.addEdge(name+"_bucket", "writeTriggers", lambdaSpec.name);
                        }

                        bucket.addEventNotification(
                            s3.EventType.OBJECT_CREATED,
                            new s3n.LambdaDestination(lambda),
                            { 
                                prefix: eventSource.prefix,
                                suffix: eventSource.suffix
                            }
                        );
                        break;

                    case "table":
                        for (let tableName of eventSource.names) {
                            const table = props.storageStack.tables[tableName];

                            graph.addEdge(tableName, "writeTriggers", lambdaSpec.name);


                            lambda.addEventSource(new DynamoEventSource(table, {
                                startingPosition: Lambda.StartingPosition.LATEST,
                                batchSize: 10,
                                bisectBatchOnError: true,
                                retryAttempts: 10,
                            }));
                        }
                        break;

                    case "scheduler":
                        graph.addNode("EventBridge", "EventBridge");

                        let rule = null;
                        if (eventSource.schedule) {
                            graph.addEdge("EventBridge", "triggers", lambdaSpec.name);
                            rule = new Events.Rule(stackClass, lambdaSpec.name, {
                                schedule: Events.Schedule.cron(eventSource.schedule),
                            });
                        } else if (eventSource.interval) {
                            graph.addEdge("EventBridge", "triggers", lambdaSpec.name);
                            rule = new Events.Rule(stackClass, lambdaSpec.name, {
                                schedule: Events.Schedule.rate(getDuration(eventSource)),
                            });
                        }

                        if (rule) rule.addTarget(new Targets.LambdaFunction(lambda));
                        break;

                    default:
                        break;
                }
            }

        }
    }


    static grantPermissionsToBucket(stackClass, lambdaSpec, lambdas, props) {
        const graph = new Graph();
        if (lambdaSpec.buckets) { 
            if (lambdaSpec.buckets.write) { 
                for (const name of lambdaSpec.buckets.write) { 
                    graph.addEdge(lambdaSpec.name, "writes", name + "_bucket");

                    const bucket = props.storageStack.buckets[name];
                    const lambda = lambdas[lambdaSpec.name];
                    bucket.grantWrite(lambda);

                    const fullBucketName = getFullName(name, props, "-");
                    lambda.addEnvironment(name.toUpperCase() + "_BUCKET", fullBucketName);
                }
            }
            if (lambdaSpec.buckets.read) { 
                for (const name of lambdaSpec.buckets.read) {
                    graph.addEdge(lambdaSpec.name, "reads", name + "_bucket");

                    const bucket = props.storageStack.buckets[name];
                    const lambda = lambdas[lambdaSpec.name];
                    bucket.grantRead(lambda);

                    const fullBucketName = getFullName(name, props, "-");
                    lambda.addEnvironment(name.toUpperCase() + "_BUCKET", fullBucketName);
                }
            }
        }
    }


    static createApis(stackClass, specs, lambdas, props) {
        const graph = new Graph();

        let apis = [];
        if (specs.apis) {
            for (let api of specs.apis) {
                
                graph.addNode("API", api.name, api);
                
                const fullApiName = getFullName(api.name, props);
                if (StackHelpers.debug) console.log(`Creating api ${fullApiName}`);

                if (api.type == "http") {

                    const defaultAllowOrigins = [
                        'http://127.0.0.1:5173',
                        'http://127.0.0.1:5174',
                        'http://127.0.0.1:5175',
                        'http://127.0.0.1:5176',
                        'http://127.0.0.1:5177',
                        'http://127.0.0.1:5178',
                        'http://127.0.0.1:5179',
                        'http://127.0.0.1:5180',
                        'http://localhost:5173',
                        'http://localhost:5174',
                        'http://localhost:5175',
                        'http://localhost:5176',
                        'http://localhost:5177',
                        'http://localhost:5178',
                        'http://localhost:5179',
                        'http://localhost:5180',
                        'http://localhost:8080',
                        'http://localhost:8081',
                        'http://localhost:8082',
                        'http://localhost:8083',
                    ]

                    const allowOrigins = api.allowOrigins ? api.allowOrigins : defaultAllowOrigins;

                    let apiProps = {
                        apiName: fullApiName,
                        description: api.description,
                        corsPreflight: {
                            allowOrigins,
                            allowMethods: [apigwv2.CorsHttpMethod.ANY],
                            allowHeaders: ['*'],
                        }
                    }

                    if (api.allowCredentials) {
                        apiProps.allowCredentials = true;
                    }

                    let httpApi = new apigwv2.HttpApi(stackClass, `${api.name}_api`, apiProps);

                    // // Add throttling to the $default stage
                    // new apigwv2.CfnStage(stackClass, `${api.name}_defaultStage`, {
                    //     apiId: httpApi.apiId,
                    //     stageName: '$default',
                    //     autoDeploy: true,
                    //     defaultRouteSettings: {
                    //         throttlingBurstLimit: api.throttlingBurstLimit ?? 100, // fallback default
                    //         throttlingRateLimit: api.throttlingRateLimit ?? 50,    // fallback default
                    //     },
                    // });

                    // TODO: add a cloudfront to this api

                    apis[api.name] = httpApi;

                    if (api.authorizerFunction) {
                        graph.addEdge(api.name, "has_authorizer", api.authorizerFunction.name);

                        const authorizerFunction = new HttpLambdaAuthorizer(`${api.name}Authorizer`, lambdas[api.authorizerFunction.name], {
                            authorizerName: api.authorizerFunction.name,
                            responseTypes: [HttpLambdaResponseType.IAM],
                            resultsCacheTtl: cdk.Duration.seconds(api.authorizerFunction.resultsCacheTtl),
                            identitySource: api.authorizerFunction.identitySource,
                            payloadFormatVersion: PayloadFormatVersion.VERSION_2_0,
                        });

                        let lambdaIntegration = new HttpLambdaIntegration('LambdaIntegration', lambdas[api.authorizerFunction.name], {
                            payloadFormatVersion: PayloadFormatVersion.VERSION_2_0, // ✅ Set Payload Format Version 2.0 for integration
                        });
                        apis[api.name].authorizerFunction = authorizerFunction;
                    }

                } else if (api.type == "ws") {

                    graph.addEdge(api.name, "connect", api.integrations.connect);
                    graph.addEdge(api.name, "disconnect", api.integrations.disconnect);
                    graph.addEdge(api.name, "default", api.integrations.default);


                    const fullApiName = getFullName(api.name, props);

                    let wsApi = new apigwv2.WebSocketApi(stackClass, `${api.name}_api`, {
                        apiName: fullApiName,
                        description: api.description,
                        routeSelectionExpression: '$request.body.action',
                        connectRouteOptions: { integration: new WebSocketLambdaIntegration('Integration', lambdas[api.integrations.connect]) },
                        disconnectRouteOptions: { integration: new WebSocketLambdaIntegration('Integration', lambdas[api.integrations.disconnect]) },
                        defaultRouteOptions: { integration: new WebSocketLambdaIntegration('Integration', lambdas[api.integrations.default]) }
                    });

                    new apigwv2.WebSocketStage(stackClass, `${api.name}_stage`, {
                        autoDeploy: true,
                        stageName: props.environment,
                        webSocketApi: wsApi
                    });
                    apis[api.name] = wsApi;

                } else { 
                    console.error(`Unsupported api type '${api.type}'.`);
                }
            }
        }
        return apis;
    }


    static addApiEndpointEnvironmentVariablesToLambdas(stackClass, props, specs, lambdas, apis) {
        const lambdaNames = Object.keys(lambdas);

        if (specs.apis) {
            for (let apiSpec of specs.apis) {
                const apiName = apiSpec.name;
                const api = apis[apiName];

                for (let lambdaName of lambdaNames) {
                    const lambda = lambdas[lambdaName];
                    lambda.addEnvironment(apiName.toUpperCase() + "_API_ENDPOINT", api.apiEndpoint);
                    if (apiSpec.keyEnv && apiSpec.keyEnv[props.environment] && apiSpec.authorizerFunction && lambdaName == apiSpec.authorizerFunction.name) { 
                        lambda.addEnvironment("X_API_KEY", apiSpec.keyEnv[props.environment]);
                    }
                }
            }
        }
    }


    static integrateLambdasToApis(stackClass, specs, lambdas, apis, props) {
        const graph = new Graph();

        if (specs.apis && specs.lambdaSpecs) {
            for (let lambdaSpec of specs.lambdaSpecs) {
                const lambda = lambdas[lambdaSpec.name];
                const fullLampdaName = getFullName(lambdaSpec.name, props);

                if (StackHelpers.debug) console.log(`Integrating lambda ${fullLampdaName} to api`);

                let lambdaIntegration;
                if (lambdaSpec.apis) {
                    for (let apiSpec of lambdaSpec.apis) {
                        const api = apis[apiSpec.name];
                        switch (apiSpec.type) {
                            case 'http':
                                // api->lambda
                                if (apiSpec.path && apiSpec.methods) {
                                    for (let method of apiSpec.methods) {
                                        const route = `${method} ${apiSpec.path}`;
                                        graph.addNode("Route", route);
                                        graph.addEdge(route, "belongs_to", apiSpec.name);
                                        graph.addEdge(route, "calls", lambdaSpec.name);
                                    }


                                    // for example, lambda authorizer doesn't have api.path or api.methods properties.
                                    lambdaIntegration = new HttpLambdaIntegration('LambdaIntegration', lambda);
                                    let route = {
                                        path: apiSpec.path,
                                        methods: apiSpec.methods,
                                        integration: lambdaIntegration,
                                    }
                                    if (lambdaSpec.activateAuthorizerFunction && apis[apiSpec.name].authorizerFunction) {
                                        route.authorizer = apis[apiSpec.name].authorizerFunction;
                                    }
                                    api.addRoutes(route);
                                    if (StackHelpers.debug) console.log(`Added route ${apiSpec.name}->${lambdaSpec.name}`);
                                }
                                break;

                            case 'ws':
                                // lambda->api
                                //lambdaIntegration = new integration.WebSocketLambdaIntegration('LambdaIntegration', lambda);
                                graph.addEdge(lambdaSpec.name, "invokes", apiSpec.name);

                                lambda.role.attachInlinePolicy(
                                    new Iam.Policy(stackClass, `${lambdaSpec.name}-invoke-wsapi-${apiSpec.name}-policy`, {
                                        statements: [new Iam.PolicyStatement({
                                            actions: ["execute-api:ManageConnections", "execute-api:Invoke"],
                                            resources: [ "arn:aws:execute-api:*:*:*/@connections/*" ]
                                        })],
                                    }),
                                );
                                break;

                            default:
                                console.error("Unrecognized api type ", apiSpec.typ );
                                break;
                        }

                    }
                }
            }
        }
    }

}

function getDuration(eventSource) {
    switch (eventSource.units) {
        case "milliseconds":
            return cdk.Duration.milliseconds(eventSource.interval);
            break;

        case "seconds":
            return cdk.Duration.seconds(eventSource.interval);
            break;
    
        case "minutes":
            return cdk.Duration.minutes(eventSource.interval);
            break;

        case "hours":
            return cdk.Duration.hours(eventSource.interval);
            break;

        case "days":
            return cdk.Duration.days(eventSource.interval);
            break;

        default:
            console.error(`Unsupported schedule duration units '${eventSource.units}'`);
            break;
    }
}


function dynamodbAttributeTypeOf(type) { 
    switch (type) {
        case 'string':
            return dynamodb.AttributeType.STRING;
            break;

        case 'number':
            return dynamodb.AttributeType.NUMBER;
            break;

        case 'binary':
            return dynamodb.AttributeType.BINARY;
            break;

        default:
            console.error(`Unsupported index key type ${type}`);
            break;
    }
}


function bucketEvents(events) {
    let result = [];
    for (let event of events) {
        result.at(bucketEvent(event))
    }
    return result;
}

function bucketEvent(event) {
    switch (event) {
        case "object_created":
            return s3.EventType.OBJECT_CREATED_PUT;
            break;

        case "object_removed":
            return s3.EventType.OBJECT_REMOVED_DELETE;
            break;

        default:
            break;
    }
}


function UUID() {
    var S4 = function () {
        return (((1 + Math.random()) * 0x10000) | 0).toString(16).substring(1);
    };
    return (S4() + S4() + "-" + S4() + "-" + S4() + "-" + S4() + "-" + S4() + S4() + S4());
}

function getFullName(name, props, separator = '_') { 
    return `${props.prefix}${separator}${props.environment}${separator}${name}`;
}

module.exports = { StackHelpers };
