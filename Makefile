#http://ghantoos.org/2008/10/19/creating-a-deb-package-from-a-python-setuppy/#comment-252

all:
	@echo "make install - Install on local system"
	@echo "make install-home - Install for this user"
	@echo "make debuild - Generate a deb package"
	@echo "make clean - Get rid of scratch and byte files"
	@echo "make docu - Generate API documentation"
	@echo "make upload-docu - Upload API-docu to webserver"
	@echo "make todo - Show all TODOs"
	@echo "make pylint - Run pylint"

docu:
#	use python-modules from source - not the ones installed on the system
	@export PYTHONPATH=./ZIBMolPy_package/:$(PYTHONPATH); epydoc --conf=epydoc.conf

upload-docu:
	# removeing old files prevents permission problems 
	ssh nums11.zib.de rm /www/Abt-Numerik/cmd-debian/ZIBMolPy/apidocs/* || true
	scp -r ./apidocs nums11.zib.de:/www/Abt-Numerik/cmd-debian/ZIBMolPy

install-home:
	cd ZIBMolPy_package; ./setup.py install --prefix=$(HOME)
	
install:
	cd ZIBMolPy_package; ./setup.py install --root $(DESTDIR)/ $(COMPILE)
	mkdir -vp $(DESTDIR)/usr/bin/
	mkdir -vp $(DESTDIR)/usr/share/zibmolpy/
	cp -v tools/*.py $(DESTDIR)/usr/bin/

#TODO: remove test-pools and temp-files
	rsync -av --exclude='*/.svn*' tests $(DESTDIR)/usr/share/zibmolpy/
	
debuild:
	debuild  -eCOMPILE="--no-compile"

clean:
	rm -rvf ZIBMolPy_package/build
	rm -rvf ./apidocs

todo:
	grep --color -r --exclude-dir="build" --exclude-dir=".svn" --include="*.py" "TODO" *

pylint:
	cd tools; pylint --rcfile=../pylintrc `find ../ZIBMolPy_package/ZIBMolPy/ -name \*.py` ./zgf_*.py 

# tag:
# - svn copy to create a tag
# - svn commit mit passendem comment
# - debian changelog akutuallisieren


# upload-deb:
#	# - debian changelog akutuallisieren
#	reprepro -Vb /global/www/Abt-Numerik/cmd-debian/ubuntu  includedeb lucid ../zibmolpy*.deb

# release:
# tag
# install-home
# docu
# upload-docu
# debuild
# upload-deb

.PHONY: all docu upload-docu install install-home debuild clean todo pylint 
#EOF