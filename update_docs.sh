#!/bin/sh -e
# generates the API docs and uploads them to github pages
# for help on github pages see: http://pages.github.com/
# https://github.com/JetBrains/kotlin/blob/master/updatedoc.sh

set -x 

make docu || exit 1

echo "Cloning/pulling latest gh-pages branch"

if [ ! -e gh-pages ]; then
ec git clone -b gh-pages git@github.com:CMD-at-ZIB/ZIBMolPy.git gh-pages
    cd gh-pages
else
	cd gh-pages
	git checkout gh-pages
    git pull --rebase
fi
git rm -r apidoc
cp -r ../apidocs .
git add apidocs
git commit -m "latest apidocs"
git push

echo "Updated github pages for apidocs"