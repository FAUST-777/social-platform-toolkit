#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
hot-products run --config config/sources.yml
