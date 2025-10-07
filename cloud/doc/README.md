# Graph

To generate the graph, just do

```bash
# this script is ${ATLASAUDIO_ROOT}/cloud/scripts/gen_cypher.js
# to use: node ${ATLASAUDIO_ROOT}/cloud/scripts/gen_cypher.js

export ATLASAUDIO_ROOT=/Users/eboily/git/AtlasAudio
export ATLASAUDIO_CYPHERFILE=${ATLASAUDIO_ROOT}/cloud/doc/graph-`date "+%Y%m%d%H%M%S"`.cypher
export outfile=${ATLASAUDIO_CYPHERFILE}
pushd ${ATLASAUDIO_ROOT}/cloud
npx cdk diff
awk '!seen[$0]++' $outfile > ${outfile}.final; mv ${outfile}.final $outfile
popd
```

This will create the file `$outfile`. Import this content in neo4j.

## Neo4j commands

### Delete all nodes and edges

```cypher
MATCH (n)
DETACH DELETE n;
```

### Display all

```cypher
MATCH p=()-[]->() RETURN p 
```

### Display sub-graph

```cypher
MATCH path = (startNode:Route {name: 'GET /actors'})-[*]->(relatedNode)
RETURN path
```
