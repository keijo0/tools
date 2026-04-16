#!/bin/bash

xhost +si:localuser:steam2
sudo -u steam2 bwrap \
  --bind / / \
  --dev-bind /dev /dev \
  --proc /proc \
  --tmpfs /tmp \
  --tmpfs /dev/shm \
  --unshare-pid \
  --unshare-ipc \
  --setenv HOME /m/steam2 \
  --setenv DISPLAY "$DISPLAY" \
  --setenv XAUTHORITY "$XAUTHORITY" \
  -- steam -applaunch 730 "$@"
