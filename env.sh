# Sourced by prepare.sh / kbuild.sh / vmbuild.sh / tools: toolchain image (docker/Dockerfile:
# CentOS 7 + GNU gcc 4.8.3, built from source, so any docker host arch works; tested on x86_64).
IMAGE=${IMAGE:-tivo-kbuild:gcc-4.8.3}
# the release the submodule is pinned to (patches/ and the fragment are made for it); named here
# rather than from `git describe` because a --shallow-submodules clone has no tags
STBLINUX_TAG=stblinux-3.3-2.5
if [ -z "$DOCKER" ]; then docker info >/dev/null 2>&1 && DOCKER=docker || DOCKER="sudo docker"; fi
KTREE=stblinux/linux

# hash of everything prepare.sh / vmbuild.sh put into a tree: patches, config fragment, symvers.
# Part of the tree stamps, so editing any of them forces a clean re-prepare / re-extract.
inputs_hash() {
  cat patches/*.patch config/roamio_fragment.config symvers/Module.symvers.* | sha256sum | cut -c1-16
}
# stamp of the prepared module tree: toolchain image id, defconfig, inputs
tree_stamp() {
  echo "$($DOCKER image inspect -f '{{.Id}}' "$IMAGE" 2>/dev/null) ${DEFCONFIG:-bcm7429b0_defconfig} $(inputs_hash)"
}
