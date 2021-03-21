#!/bin/bash

if [ "$1" != "" ]; then
    exec "$@"
    exit
fi

exec /bin/bash