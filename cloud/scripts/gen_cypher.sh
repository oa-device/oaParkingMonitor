#!/bin/bash

export AWS_PROFILE=kampusmedia
 
# Check if ATLASAUDIO_ROOT is defined
if [ -z "$ATLASAUDIO_ROOT" ]; then
  echo "Error: ATLASAUDIO_ROOT environment variable is not defined."
  exit 1
fi

export ATLASAUDIO_ROOT=/Users/eboily/git/AtlasAudio
export ATLASAUDIO_CYPHERFILE=${ATLASAUDIO_ROOT}/cloud/doc/graph-`date "+%Y%m%d%H%M%S"`.cypher
export outfile=${ATLASAUDIO_CYPHERFILE}

# clear the previous run
[ -e $outfile ] && rm $outfile

# go to the proper directory
pushd ${ATLASAUDIO_ROOT}/cloud

# generate the cypher code
npx cdk diff

# remove duplicate lines
awk '!seen[$0]++' $outfile > ${outfile}.final; mv ${outfile}.final $outfile

# return to the original directopry
popd
