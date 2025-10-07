const cdk = require('aws-cdk-lib');
const fs = require('fs');
const { StackHelpers } = require('./StackHelpers.js');

// import * as cdk from 'aws-cdk-lib';
// import fs from 'fs';
// import StackHelpers from "./StackHelpers.js"

class DeviceApiStack extends cdk.Stack {

    lambdas = {};
    apis = {};

    /**
     *
     * @param {Construct} scope - the parent construct, the app or a nested stack
     * @param {string} id - the construct id
     * @param {StackProps=} props - stack properties
     * @param {string} lambdasSubdir - subdirectory in .lib/assets/lambdas/ where the lambda code is located (e.g. "device" or "dashboard")
     */
    constructor(scope, id, props, lambdasSubdir) {
        super(scope, id, props);

        this.lambdasSubdir = lambdasSubdir;

        var specs;
        try {
            specs = JSON.parse(fs.readFileSync(`./lib/${this.constructor.name}.json`, 'utf8'));
        } catch (error) {
            console.error(error);
            return;
        }

        this.createStack(props, specs)
    }


    createStack(props, specs) {

        const lambdasProps = StackHelpers.allLambdasProps(this, props, specs.layers);
        if (specs.lambdaSpecs) {
            for (let lambdaSpec of specs.lambdaSpecs) {
                let lambda = StackHelpers.createLambda(this, lambdaSpec, lambdasProps, props);
                this.lambdas[lambdaSpec.name] = lambda;
                StackHelpers.grantTableAccess(this, lambda, lambdaSpec, props);
                //StackHelpers.addLayers(this, lambda, lambdaSpec, props);
            }

            for (let lambdaSpec of specs.lambdaSpecs) {
                StackHelpers.grantPermissionToInvokeLambda(this, lambdaSpec, this.lambdas);
                StackHelpers.grantPermissionsToBucket(this, lambdaSpec, this.lambdas, props);
                StackHelpers.setEventSources(this, lambdaSpec, this.lambdas, props);
            }

        }

        this.apis = StackHelpers.createApis(this, specs, this.lambdas, props);

        StackHelpers.addApiEndpointEnvironmentVariablesToLambdas(this, props, specs, this.lambdas, this.apis);

        StackHelpers.integrateLambdasToApis(this, specs, this.lambdas, this.apis, props);

    }
}

module.exports = { DeviceApiStack };