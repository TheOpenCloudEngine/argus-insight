#!/bin/sh

REGISTRY_URL="dev-server.dev.net:5000"
USER_PASS="admin:your-password"

# 리포지토리 목록 가져오기
REPOS=$(curl -sk -u $USER_PASS https://$REGISTRY_URL/v2/_catalog | jq -r '.repositories[]')

for REPO in $REPOS; do
  # 각 리포지토리의 태그 목록 가져오기
  TAGS=$(curl -sk -u $USER_PASS https://$REGISTRY_URL/v2/$REPO/tags/list | jq -r '.tags[]')
  for TAG in $TAGS; do
    echo "$REGISTRY_URL/$REPO:$TAG"
  done
done
