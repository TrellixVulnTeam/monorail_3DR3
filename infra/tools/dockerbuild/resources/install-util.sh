# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Generic utility functions used by other installation scripts.

set -e
set -x
set -o pipefail

# Ensure that our mandatory environment variables are set:
#
# - LOCAL_PREFIX is the prefix to use for host installation.
# - CROSS_TRIPLE is the cross-compile host triple.
if [ -z "${LOCAL_PREFIX}" -o -z "${CROSS_TRIPLE}" ]; then
  echo "ERROR: Missing required environment."
  exit 1
fi

# Augment our PATH to include our local prefix's "bin" directory.
export PATH=${LOCAL_PREFIX}/bin:${PATH}

# Snapshot the cross-compile environment so we can toggle between them.
CROSS_AS=$AS
CROSS_AR=$AR
CROSS_CC=$CC
CROSS_CPP=$CPP
CROSS_CXX=$CXX
CROSS_LD=$LD

# Create and augment our CFLAGS and LDFLAGS.
CROSS_CFLAGS="$CFLAGS"
CROSS_LDFLAGS="$LDFLAGS"
CROSS_PYTHONPATH="$PYTHONPATH"
CROSS_CMAKE_TOOLCHAIN_FILE="$CMAKE_TOOLCHAIN_FILE"

CROSS_C_INCLUDE_PATH="$C_INCLUDE_PATH"
CROSS_CPLUS_INCLUDE_PATH="$CPLUS_INCLUDE_PATH"
CROSS_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
CROSS_LIBRARY_PATH="$LIBRARY_PATH"

toggle_host() {
  AS=
  AR=
  CC=
  CPP=
  CXX=
  LD=

  CFLAGS=
  LDFLAGS=
  PYTHONPATH=
  CMAKE_TOOLCHAIN_FILE=

  C_INCLUDE_PATH=
  CPLUS_INCLUDE_PATH=
  LD_LIBRARY_PATH=
  LIBRARY_PATH=
}

toggle_cross() {
  AS=${CROSS_AS}
  AR=${CROSS_AR}
  CC=${CROSS_CC}
  CPP=${CROSS_CPP}
  CXX=${CROSS_CXX}
  LD=${CROSS_LD}

  CFLAGS="${CROSS_CFLAGS}"
  LDFLAGS="${CROSS_LDFLAGS}"
  PYTHONPATH="${CROSS_PYTHONPATH}"
  CMAKE_TOOLCHAIN_FILE="${CROSS_CMAKE_TOOLCHAIN_FILE}"

  C_INCLUDE_PATH="${CROSS_C_INCLUDE_PATH}"
  CPLUS_INCLUDE_PATH="${CROSS_CPLUS_INCLUDE_PATH}"
  LD_LIBRARY_PATH="${CROSS_LD_LIBRARY_PATH}"
  LIBRARY_PATH="${CROSS_LIBRARY_PATH}"
}

abspath() {
  local P=$1; shift
  echo $(readlink -f ${P})
}

get_archive_dir() {
  local ARCHIVE_PATH=$1; shift
  echo $(tar tf ${ARCHIVE_PATH} | head -n1 | sed  's#\(.*\)/.*#\1#')
}

if [ ! `which nproc` ]; then
  nproc() {
    grep processor < /proc/cpuinfo | wc -l
  }
fi
