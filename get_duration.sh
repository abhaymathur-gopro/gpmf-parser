#!/bin/bash
# Usage: ./get_duration.sh <path_to_video> [options]
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_video> [options]"
    exit 1
fi

VIDEO_PATH=$1
shift
./demo/gpmfdemo "$VIDEO_PATH" "$@" | grep -E "VIDEO DURATION|RESULT_METADATA"
