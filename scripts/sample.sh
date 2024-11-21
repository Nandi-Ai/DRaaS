#!/bin/bash

usage() { echo "Usage: $0 <code_deleted|code_created|node_pool_stopped|node_pool_start>" 1>&2; exit 1; }

# unless there are 2 arguments, print the "usage" and exit
[ ! $# -eq 2 ] && usage

# Functions
delete_code() {
    echo "code deleted test"
}

create_code() {
    echo "code created test"
}

stop_node_pool() {
    echo "node pool stopped test"
}

start_node_pool() {
    echo "node pool start test"
}

# Execution
for i in "$@"
do

    case "$i" in

        code_deleted)
            delete_code &
            ;;

        code_created)
            create_code &
            ;;

        node_pool_stopped)
            stop_node_pool &
            ;;

        node_pool_start)
            start_node_pool &
            ;;

        *)
            usage
            ;;
    esac
done
wait
