#!/usr/bin/env bash

VERSION=$(sentry-cli releases propose-version || exit)

docker buildx build --platform linux/amd64 --push -t "as207960/support-django:$VERSION" . || exit

sentry-cli releases --org as207960 new -p as207960-support "$VERSION" || exit
sentry-cli releases --org as207960 set-commits --auto "$VERSION"
