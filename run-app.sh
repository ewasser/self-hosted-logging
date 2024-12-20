#!/bin/bash

configuration="Development"
DEBUG_OPTION='--debug'

########################################################################

export PATH=$(pwd)/bin:$PATH
hostname=$(hostname --long)

########################################################################

if [[ $hostname = 'wasser.family' ]] ; then
    configuration="Production"
    DEBUG_OPTION=''
fi

########################################################################
export APP_SETTINGS="project.server.config.${configuration}Config"
export FLASK_APP=project.server.startup:create_app
flask $DEBUG_OPTION "$@"

