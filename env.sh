# Sourced by prepare.sh / kbuild.sh / vmbuild.sh / tools: toolchain image (docker/Dockerfile:
# CentOS 7 + GNU gcc 4.8.3, built from source, so any docker host arch works; tested on x86_64).
IMAGE=${IMAGE:-tivo-kbuild:gcc-4.8.3}
# the release the submodule is pinned to (patches/ and the fragment are made for it); named here
# rather than from `git describe` because a --shallow-submodules clone has no tags
STBLINUX_TAG=stblinux-3.3-2.5
if [ -z "$DOCKER" ]; then docker info >/dev/null 2>&1 && DOCKER=docker || DOCKER="sudo docker"; fi
KTREE=stblinux/linux
