# CentOS 7 + GNU gcc 4.8.3 / binutils 2.24, mipsel cross (C only, no libc: kernel and modules only)
# for the TiVo Roamio kernel. The device banner is "gcc version 4.8.3 (GCC)" -- no pkgversion, i.e.
# an unmodified release build, and this one prints exactly that.
# Tarball hashes pinned after checking the GNU signatures (gcc: Richard Guenther 3AB00996FC26A641,
# binutils: Tristan Gingold C3126D3B4AE55E93) against ftp.gnu.org/gnu/gnu-keyring.gpg.
# CentOS 7 also keeps 3.3-era host tools: perl 5.16 (kernel/timeconst.pl breaks on perl >= 5.22).
FROM centos:7 AS base
# CentOS 7 is EOL: the mirrorlist is gone, packages live on vault.centos.org
RUN set -eux; \
    sed -i -e 's/^mirrorlist=/#mirrorlist=/' -e 's|^#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|' \
        /etc/yum.repos.d/CentOS-*.repo; \
    yum -y update; \
    yum -y install make gcc perl bc bzip2 tar which diffutils patch gmp mpfr libmpc; \
    yum clean all; rm -rf /var/cache/yum

FROM base AS build
RUN yum -y install gcc-c++ gmp-devel mpfr-devel libmpc-devel && yum clean all
RUN set -eux; cd /tmp; \
    curl -fsSL --retry 3 -o binutils.tar.bz2 https://ftp.gnu.org/gnu/binutils/binutils-2.24.tar.bz2; \
    curl -fsSL --retry 3 -o gcc.tar.bz2 https://ftp.gnu.org/gnu/gcc/gcc-4.8.3/gcc-4.8.3.tar.bz2; \
    printf '%s\n' 'e5e8c5be9664e7f7f96e0d09919110ab5ad597794f5b1809871177a0f0f14137  binutils.tar.bz2' \
                  '6a8e4f11b185f4fe2ed9d7fc053e80f8c7e73f800c045f51f9d8bea33f080f1e  gcc.tar.bz2' | sha256sum -c -; \
    tar xjf binutils.tar.bz2; tar xjf gcc.tar.bz2
ARG PREFIX=/opt/toolchains/gcc-4.8.3
ARG TARGET=mipsel-linux
RUN set -eux; mkdir /tmp/b-binutils && cd /tmp/b-binutils; \
    /tmp/binutils-2.24/configure --target=$TARGET --prefix=$PREFIX --disable-nls --disable-werror \
        --disable-multilib MAKEINFO=true; \
    make -j$(nproc) MAKEINFO=true; make install MAKEINFO=true
RUN set -eux; mkdir /tmp/b-gcc && cd /tmp/b-gcc; export PATH=$PREFIX/bin:$PATH; \
    /tmp/gcc-4.8.3/configure --target=$TARGET --prefix=$PREFIX --enable-languages=c \
        --without-headers --disable-shared --disable-threads --disable-nls --disable-multilib \
        --disable-libssp --disable-libgomp --disable-libmudflap --disable-libquadmath \
        --disable-libatomic --disable-libitm --disable-libsanitizer MAKEINFO=true; \
    make -j$(nproc) all-gcc MAKEINFO=true; make install-gcc MAKEINFO=true

FROM base
COPY --from=build /opt/toolchains/gcc-4.8.3 /opt/toolchains/gcc-4.8.3
ENV PATH=/opt/toolchains/gcc-4.8.3/bin:$PATH ARCH=mips CROSS_COMPILE=mipsel-linux-
RUN mipsel-linux-gcc -v 2>&1 | tail -1 | grep -qx 'gcc version 4.8.3 (GCC) '
WORKDIR /kbuild
