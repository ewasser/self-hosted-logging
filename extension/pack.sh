#!/bin/bash

NAME=$(basename $(pwd))
NAME="Self Hosted Logging"

NAME=$(echo "$NAME" | tr '[:upper:]' '[:lower:]' | sed 's/ /-/g')

VERSION=0.2

zip_name=$NAME-$VERSION.zip

if [[ -e $zip_name ]] ; then
    echo "$zip_name already exists, I'm aborting..."
    exit 1
fi

rm -f $NAME-$VERSION.zip

cd extension

zip -r -FS ../$zip_name * --exclude '*.git*'.

