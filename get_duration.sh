#!/bin/bash
# Usage: ./get_duration.sh <path_to_video>
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_video>"
    exit 1
fi

./demo/gpmfdemo "$1" | grep "VIDEO DURATION"
