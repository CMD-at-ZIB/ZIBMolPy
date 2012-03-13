#!/bin/bash
# generates the API docs and uploads them to github pages
# for help on github pages see: http://pages.github.com/
# derived from: https://github.com/JetBrains/kotlin/blob/master/updatedoc.sh

set -x 

make docu || exit 1

echo "Cloning/pulling latest gh-pages branch"

if [ ! -e gh-pages ]; then
	git clone -b gh-pages git@github.com:CMD-at-ZIB/ZIBMolPy.git gh-pages
	cd gh-pages
else
	cd gh-pages
	git checkout gh-pages
	git pull --rebase
fi

git rm -r apidocs
cp -r ../apidocs .
git add apidocs
git commit -m "latest apidocs"
git push

echo "Updated github pages for apidocs"

#EOF