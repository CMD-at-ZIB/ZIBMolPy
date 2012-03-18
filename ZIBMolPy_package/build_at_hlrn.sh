#!/bin/bash
source ${MODULESHOME}/init/sh;

python -c "import sys; sys.exit(sys.hexversion < 0x02060000)"
if [ "$?" -eq 1 ] ; then 
	module load local
fi

# the libraries will go here
prefix=~

if [ ! -z $1 ] ; then
	prefix=$1
fi

# links to executables will go here
link_dest=~/bin

if [ ! -z $2 ] ; then
	link_dest=$2
fi

echo "Installing with --prefix="$prefix

rm -rf ./build/
./setup.py install --prefix=$prefix

echo "Creating links to executables in "$link_dest
./make_links.sh $link_dest

#EOF

