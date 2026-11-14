#!/usr/bin/env bash
# Process every Card; existing morphology is preserved unless --force is passed.
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$project_dir"

exec python compute_morphology.py "$@"
