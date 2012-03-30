#http://ghantoos.org/2008/10/19/creating-a-deb-package-from-a-python-setuppy/#comment-252

all:
	@echo "make install - Install on local system"
	@echo "make install-home - Install for this user"
	@echo "make uninstall - Remove ZIBMolPy from system"
	@echo "make clean - Get rid of temporary and bytecode files"
	@echo "make docu - Generate API documentation"
	@echo "make upload-docu - Upload API-docu to webserver"
	@echo "make todo - List all TODOs"
	@echo "make pylint - Run pylint"


install:
ifdef prefix
	./scripts/installer.py install --prefix=$(prefix)
else
	./scripts/installer.py install
endif


install-home:
	make prefix=$(HOME) install
	
uninstall:
	./scripts/installer.py uninstall
	
docu:
#	use python-modules from source - not the ones installed on the system
	@export PYTHONPATH=./ZIBMolPy_package/:$(PYTHONPATH); epydoc --conf=./scripts/epydoc.conf
	./scripts/epydoc_postprocessing.py
	
upload-docu:
	./scripts/upload_docu.sh	
	
todo:
	grep --color -r --exclude-dir="build" --exclude-dir=".*" --include="*.py" "TODO" *
	
pylint:
# TODO: check all tools not just zgf_*.py
	cd tools; pylint --rcfile=../scripts/pylintrc `find ../ZIBMolPy_package/ZIBMolPy/ -name \*.py` ./zgf_*.py 
	
clean:
	rm -rvf ZIBMolPy_package/build
	rm -rvf ./apidocs
	find . -name "*~" -exec rm -v {} \;


.PHONY: all install install-home uninstall docu upload-docu todo pylint clean 
#EOF
