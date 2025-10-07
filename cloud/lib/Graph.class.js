const fs = require('fs');
const defaultCypherFile = process.env.ATLASAUDIO_CYPHERFILE;

const AWSTypes = ['API', 'Route', 'Lambda', 'Table', 'Bucket', 'Event'];
const DEBUG = false;

class Graph {
    creationDate = null;
    currentNodeId = 0;
    currentEdgeId = 0;
    cypherFile = null;

    static Type = {
        'API': 'API',
        'ROUTE': 'Route',
        'LAMBDA': 'Lambda',
        'TABLE': 'Table',
        'BUCKET': 'Bucket',
        'EVENT': 'Event'
    }

    constructor(cypherFile = defaultCypherFile) {
        this.cypherFile = cypherFile;
        this.creationDate = new Date();

        if (this.cypherFile && !fs.existsSync(this.cypherFile)) {
            // Create the file (empty or with initial content)
            fs.writeFileSync(this.cypherFile, '', 'utf8');  // Create an empty file
            console.log(`File created at ${this.cypherFile}`);
        }
    }

    addNode(type, label, properties) {
        if (this.cypherFile) {
            // CREATE(api1: API { name: 'editor_http' })
            const id = this.#labelToId(label);
            //properties.name = label;
            //this.#addCypherLine(`CREATE (${id}:${type} ${properties}'})`);
            let line = `CREATE (${id}:${type} {name: '${label}'})`;
            if (properties) {
                line = `CREATE (${id}:${type} ${this.#jsonToProperties(label, properties)})`;
            }
            if (DEBUG) console.log(line);
            this.#addCypherLine(line);
        }
    }

    addEdge(sourceNodeLabel, edgeLabel, targetNodeLabel) {
        if (this.cypherFile) {
            // CREATE (api1)-[:has]->(r1)
            const sourceId = this.#labelToId(sourceNodeLabel);
            const targetId = this.#labelToId(targetNodeLabel);
            const line = `CREATE (${sourceId})-[:${edgeLabel}]->(${targetId})`;
            if (DEBUG) console.log(line);
            this.#addCypherLine(line);
        }
    }

    #labelToId(label) {
        if (label) {
            // remove spaces, '/', '{', '}'
            return label.replace(/[ /{}]/g, '');
        }
        return "";
    }

    #addCypherLine(line) {
        try {
            fs.appendFileSync(this.cypherFile, line+"\n");
            //console.log('Successfully appended to file.');
        } catch (err) {
            console.error('Error appending to file:', err);
        }
    }

    #jsonToProperties(label, obj) {
        obj.name = label; // we may have extended the label to prevent collision, so keep the extension
        // for example, we have a bucked named toto and we also have a table with this nname. 
        // In the StackHelper, we did augment the bucket to toto_bucket.

        const transformedEntries = Object.entries(obj).map(([key, value]) => {
            // Remove single quotes from the value
            if (typeof value === 'string') {
                value = value.replace(/'/g, '');
            }

            let transformedKey = key.includes("'") ? `'${key}'` : key;
            let transformedValue;

            if (typeof value === 'boolean' || typeof value === 'number') {
                transformedValue = `'${value}'`;
            } else if (Array.isArray(value)) {
                transformedValue = `'[${value.join(', ')}]'`;
            } else {
                transformedValue = `'${value}'`;
            }

            return `${transformedKey}: ${transformedValue}`;
        });

        return `{ ${transformedEntries.join(', ')} }`;
    }
}
module.exports = Graph;