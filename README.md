ZIBMolPy
========

![ZIBMolPy](https://github.com/CMD-at-ZIB/ZIBMolPy/raw/master/docu/zgf_logo_trans_small.png)

What's this?
------------

<p align="justify">The core of the ZIBMolPy package is an implementation of the efficient, adaptive sampling algorithm ZIBgridfree, designed for characterizing the conformational space of molecules.</p>

<p align="justify">The original ZIBgridfree algorithm was designed by Marcus Weber and Holger Meyer in 2005, and, over the years, has been enhanced by Alexander Riemer, Susanna Röblitz and Lionel Walter. The theoretical framework of ZIBgridfree is provided by Conformation Dynamics, an idea coined by Peter Deuflhard and Christoph Schütte.</p>

<p align="justify">This implementation represents an evolution of the original ZIBgridfree as it couples the original algorithm to the state-of-the-art molecular dynamics engine <a href="http://www.gromacs.org">Gromacs</a>. This creates the possibility to apply ZIBgridfree to very large molecular systems.</p>

License
-------

This software package is released under the LGPL 3.0, see LICENSE file.

Installation
------------

#### Prerequisites

You have to install a bunch of packages. On Ubuntu/Debian you can simply type:

`sudo apt-get install python-numpy python-scipy python-matplotlib python-gtk2 gromacs`

#### Download

1. Download the current 'master' version as [zipball](https://github.com/CMD-at-ZIB/ZIBMolPy/zipball/master) or [tarball](https://github.com/CMD-at-ZIB/ZIBMolPy/tarball/master), or use git: <br />
`git clone git://github.com/CMD-at-ZIB/ZIBMolPy.git`

2. Extract it with e.g. <br />
`tar -xvzf CMD-at-ZIB-ZIBMolPy-80c927a.tar.gz`

3. Go into the the directory: <br />
`cd CMD-at-ZIB-ZIBMolPy-xxxxxx`

#### System-wide installation

Simply run: <br />
`sudo make install`

#### Installation into home directory

1. Run <br />
`make install-home`

2. Add the following lines to your .bashrc:

`export PYTHONPATH=$PYTHONPATH:~/libXX/pythonX.X/site-packages/` <br />
`export PATH=$PATH:~/bin/`

Testing
-------

You can run some tests to make sure everything is working as intended.

1. Go into the tests/ directory, which is located either in <br />

`/usr/share/zibmolpy/tests`

or <br />

`~/share/zibmolpy/tests`.

2. Chose one of the tests cases. The pentane_quick test takes the least amount of time to run.

3. Depending on your gromacs version run either <br />

`zgf_test test-desc-seq-gromacs-4.0.7.xml` <br />

or <br />

`zgf_test test-desc-seq-gromacs-4.5.5.xml`

4. You can take a look at the results by starting zgf_browser.

If the tests fail due to differences in numerical values, you may be using a different Gromacs version.

Documentation
-------------

For documentation, please refer to the wiki at:

[github.com/CMD-at-ZIB/ZIBMolPy/wiki](https://github.com/CMD-at-ZIB/ZIBMolPy/wiki)

The API documentation can be found here:

[cmd-at-zib.github.com/ZIBMolPy/apidocs/](http://cmd-at-zib.github.com/ZIBMolPy/apidocs/)
