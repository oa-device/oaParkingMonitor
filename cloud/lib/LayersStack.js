const cdk = require('aws-cdk-lib');
const fs = require('fs');
const { StackHelpers } = require('./StackHelpers.js');

class LayersStack extends cdk.Stack {
  
  layers = {};

  /**
   *
   * @param {Construct} scope
   * @param {string} id
   * @param {StackProps=} props
   */
  constructor(scope, id, props) {
    super(scope, id, props);

    let specs;
    try {
      specs = JSON.parse(fs.readFileSync(`./lib/${this.constructor.name}.json`, 'utf8'));
    } catch (error) {
      console.error(error);
      return;
    }

    this.createStack(specs, props);
  }

  createStack(specs, props) { 
    for (let layerSpec of specs.layers) {
      this.layers[layerSpec.name] = StackHelpers.createLayer(this, layerSpec, props);
    }
  }

}

module.exports = { LayersStack };