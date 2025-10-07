#!/usr/bin / env node

const cdk = require('aws-cdk-lib');
const lambda = require('aws-cdk-lib/aws-lambda');

const { StorageStack } = require('../lib/StorageStack.js');
const { LayersStack } = require('../lib/LayersStack.js');
const { DeviceApiStack } = require('../lib/DeviceApiStack.js');
const { DashboardApiStack } = require('../lib/DashboardApiStack.js');
const { SystemStack } = require('../lib/SystemStack.js');

const { execSync } = require('child_process');
const { exit } = require('process');

// get the environment from the git branch
let branch = execSync('git rev-parse --abbrev-ref HEAD', (err, stdout, stderr) => {
  if (err) {
    // handle your error
    console.error(err);
  }
  console.log(typeof stdout);
  if (typeof stdout === 'string') {
    return stdout.trim();
  }
});
branch = branch.slice(0, -1)
if (!["dev", "test", "prod"].includes(`${branch}`)) { 
  console.error(`Invalid branch name ${branch}. Must be one of dev, test, prod.`);
  exit(1);
}

const account = '304906330428';
//const region = 'us-east-1';
const region = 'ca-central-1';
const project = 'parking001';

let props = {
  env: {
    account,
    region
  },
  account,
  region,
  MasterSignKey: "c07f32d3-3535-44a6-9c90-f2d4e3f97f61",
  MasterCryptKey: "691e3092-e48b-494a-a86a-73aa38f735f2",
  prefix: project,
  environment: `${branch}`,
  version: '1.0',
  assetsDir: "./lib/assets/",
  runtime: lambda.Runtime.NODEJS_20_X,
  architecture: lambda.Architecture.ARM_64,
  handler: "index.handler",
  timeout: cdk.Duration.seconds(60),
  logRetention: cdk.Duration.days(3),
  memorySize: 512,
  defaultDebug: "true",
  layerVersion: {
    "awsHelpers": {
      "dev": 5,
      "test": 1,
      "prod": 1
    }
  },
  multistackVersion: 1.0,
  tables: {},
  buckets: {},
  layers: {},
  apis: {},
  lambdas: {},
  elastics: {}
};

const app = new cdk.App();

props.storageStack = new StorageStack(app, `${props.prefix}-StorageStack-${props.environment}`, props);


props.layersStack = new LayersStack(app, `${props.prefix}-LayersStack-${props.environment}`, props);

props.deviceApiStack = new DeviceApiStack(app, `${props.prefix}-DeviceApiStack-${props.environment}`, props, "device");
props.deviceApiStack.addDependency(props.storageStack);
props.deviceApiStack.addDependency(props.layersStack);


props.dashboardApiStack = new DashboardApiStack(app, `${props.prefix}-DashboardApiStack-${props.environment}`, props, "dashboard");
props.dashboardApiStack.addDependency(props.storageStack);
props.dashboardApiStack.addDependency(props.layersStack);


props.systemStack = new SystemStack(app, `${props.prefix}-SystemStack-${props.environment}`, props, "system");
props.systemStack.addDependency(props.storageStack);
props.systemStack.addDependency(props.layersStack);
