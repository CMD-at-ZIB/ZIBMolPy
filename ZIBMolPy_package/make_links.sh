#!/bin/bash
# for all py-files in tools/ creates convenient links (and drops extension '.py') 

# removing extra slash from $1
LINKDEST=${1%\/}

if [ ! -d $LINKDEST ] ; then
	echo $LINKDEST" is not a directory."
	exit 1
fi

cd ../tools/

for file in *.py;
do
	# check if file is a file
	if [ -f $file ] ; then
		# get name without extension
		name=${file%\.*}

		if [ -e $LINKDEST/$name ] ; then
			# remove old link
			rm $LINKDEST/$name
		fi

		echo "Making link for "${name}" ..."
		ln -s $PWD/$file $LINKDEST/$name
	fi
done

#EOF
