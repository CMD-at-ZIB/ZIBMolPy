#!/bin/bash
source ${MODULESHOME}/init/sh;

python -c "import sys; sys.exit(sys.hexversion < 0x02060000)"
if [ "$?" -eq 1 ] ; then 
	module load local
fi

# find out the correct prefix for this build
tag=`python -c "import os; print os.getcwd().split('/')[-2]"`
prefix="~/libs_"$tag

echo "Building libraries in "$prefix"..."

set -x
rm -rf ./build/
./setup.py install --prefix=$prefix

#EOF

