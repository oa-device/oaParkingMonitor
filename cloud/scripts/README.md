
# Create a backup

This backups the tables and the entrepot bucket.

```bash
./scripts/backup
```


# Generate new permissions table

 * Export google sheet https://docs.google.com/spreadsheets/d/1VD6r_wzEsrY5uVbc6eLc-w8L2hUQozVA7RVSYLoERlU/edit#gid=1008473271 as tsv file
 * Delete atlas_dev_permissions table content (I'll provide a script for this)

```bash
./permissions_tsv2json.js -f permissions.tsv > permissions.json
export AWS_PROFILE=kampusmedia
./tablePut.js -f permissions.json -t atlas_dev_permissions
```

# Generate cypher graph

A cypher file documenting the entire deployment can be generated.
To do so, you must define the environment variable `ATLASAUDIO_CYPHERFILE`.

```bash
export ATLASAUDIO_CYPHERFILE=/Users/eboily/git/AtlasAudio/cloud/doc/graph.cypher
```

This file will be appended with cypher commands every time you make a `cdk diff` or `cdk deploy`.
To generate a clean file, delete it first:

```bash
export ATLASAUDIO_CYPHERFILE=/Users/eboily/git/AtlasAudio/cloud/doc/graph.cypher
rm $ATLASAUDIO_CYPHERFILE
npx cdk diff
cat $ATLASAUDIO_CYPHERFILE
```

To prevent this file to be generated, just unset the environment variable:

```bash
unset ATLASAUDIO_CYPHERFILE
```
