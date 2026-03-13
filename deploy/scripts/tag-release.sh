#!/usr/bin/env bash
# Auto-tag semver release: bump patch/minor/major
# Usage: tag-release.sh [patch|minor|major]
set -euo pipefail

BUMP="${1:-patch}"

# Get latest tag
LATEST=$(git describe --tags --abbrev=0 --match "v*" 2>/dev/null || echo "v0.0.0")
echo "Latest tag: ${LATEST}"

# Parse
IFS='.' read -r MAJOR MINOR PATCH <<< "${LATEST#v}"

case "${BUMP}" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
  *) echo "Unknown bump type: ${BUMP}"; exit 1 ;;
esac

NEW_TAG="v${MAJOR}.${MINOR}.${PATCH}"
echo "New tag: ${NEW_TAG}"

git tag -a "${NEW_TAG}" -m "Release ${NEW_TAG}"
git push origin "${NEW_TAG}"
echo "Tagged and pushed: ${NEW_TAG}"
