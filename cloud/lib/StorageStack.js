const cdk = require('aws-cdk-lib');
const fs = require('fs');
const { StackHelpers } = require('./StackHelpers.js');

class StorageStack extends cdk.Stack {

  tables = {};
  buckets = {};
  ledgers = {};
  elastics = {};
  notifications = {};

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

    if (specs.tables) {
      for (let tableSpec of specs.tables) {
        this.tables[tableSpec.name] = StackHelpers.createTable(this, tableSpec, props);
      }
    }

    if (specs.buckets) {
      for (let bucketSpec of specs.buckets) {
        this.buckets[bucketSpec.name] = StackHelpers.createBucket(this, bucketSpec, props, this.buckets);
      }
    }

    if (specs.ledgers) {
      for (let lergerSpec of specs.ledgers) {
        this.ledgers[lergerSpec.name] = StackHelpers.createLedger(this, lergerSpec, props);
      }
    }

    if (specs.elastics) {
      for (let elasticSpec of specs.elastics) {
        console.warn(`WARNING: StackHelpers.createElastic() is not implemented.`);
        //this.elastics[elasticSpec.name] = StackHelpers.createElastic(this, elasticSpec, props);
      }
    }

    // if (specs.notifications) {
    //   for (let notificationSpec of specs.notifications) {
    //     this.notifications[notificationSpec.topic] = StackHelpers.createSNS(this, notificationSpec, props);
    //   }
    // }

  }

}

module.exports = { StorageStack };
