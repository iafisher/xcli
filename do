#!/bin/bash

set -eu

main() {
  if [[ $# -lt 1 ]]; then
    usage
  fi

  subcommand="$1"
  shift
  if [[ "$subcommand" = test ]]; then
    python3 -m unittest "$@"
  elif [[ "$subcommand" = publish ]]; then
    echo "Not implemented yet!"
  else
    usage
  fi
}

usage() {
  echo "Expected subcommand: test or publish"
  exit 1
}

main "$@"
