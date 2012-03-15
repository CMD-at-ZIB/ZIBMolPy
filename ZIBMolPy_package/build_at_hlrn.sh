#!/bin/bash
source ${MODULESHOME}/init/sh;

python -c "import sys; sys.exit(sys.hexversion < 0x02060000)"
if [ "$?" -eq 1 ] ; then 
	module load local
fi

set -x
rm -rvf ./build/
cd ..
make install-home

#EOF

