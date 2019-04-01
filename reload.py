#!/usr/local/bin/python3
###
# DO NOT DISTRIBUTE WITH ADDON
# This is a convenience script for reloading files into blender and packaging
# the different versions together.
#
# Simply run this python script in its own working directory
#
###

"""
todo
Make it auto-install into the blender source files
"""

from datetime import datetime
from subprocess import Popen, PIPE
import os
import codecs
import sys
import shutil
import zipfile


# Global vars, the things to change
stagepath = "blender-assistant"
name_var = "$VERSION"  # search for this in each, string
name_array = []
verbose_var = "$VERBOSE" # turn line from 'v = True # $VERBOSE" to 'v = False'
addonpaths = ["/Users/patrickcrawford/Library/Application Support/Blender/2.80/scripts/addons/",
			"/Users/patrickcrawford/Library/Application Support/Blender/2.79/scripts/addons/"]
build_dir = "../compiled/"
files = ["__init__.py","assistant_tools.py","assistant_ui.py",
		"README.md", "suggestions_update.tsv", "load_modules.py",
		"icons"]
build_dir = "../blender-assistant-compiled"


def main():

	if len(sys.argv) < 2:
		# no input args, just assume the basic level which includes
		# installing fresh
		publish()
		fresh_install()
		build_zip()
		run_cleanups()
	else:
		print("Not configured for other setups/builds")


def publish(target=""):
	print("preparing project for publishing")
	if target not in name_array:
		print("Building all")

	if os.path.isdir(build_dir)==True:
		shutil.rmtree(build_dir)
	os.mkdir(build_dir)
	prepare_build("", install=False)
	print("Build finished")


def prepare_build(version, install=False):
	# make the staging area
	print("Building target: "+stagepath)

	if os.path.isdir(stagepath)==True:
		shutil.rmtree(stagepath)
	os.mkdir(stagepath)

	# file by file, copy and do replacements
	for fil in files:
		if os.path.isdir(fil)==True:
			newdirname = os.path.join(stagepath, fil)
			shutil.copytree(fil, newdirname,
				ignore=shutil.ignore_patterns(".DS_Store")) # will have some .DS_store's
		else:
			newname = os.path.join(stagepath, fil)
			if not os.path.isdir(os.path.dirname(newname)):
				os.mkdir(os.path.dirname(newname))
			inFile = codecs.open(fil, "r", "utf-8")
			outFile = codecs.open(newname, "w", "utf-8")
			for line in inFile:
				newline = do_replacements_on(line,version)
				outFile.write(newline)
			inFile.close()
			outFile.close()

def build_zip():
	# zip and remove
	p = Popen(['zip','-r',stagepath+'.zip',stagepath],
				stdin=PIPE,stdout=PIPE, stderr=PIPE)
	stdout, err = p.communicate(b"")
	os.rename(stagepath+'.zip',os.path.join(build_dir,stagepath+'.zip'))


def do_replacements_on(line,version):
	# replace all variables as appropriate, including verbose build
	# including custom setup for demo version and
	tmp = ""
	if name_var in line:
		nline = line.split(name_var)
		for index in range(len(nline)-1):
			tmp+= nline[index]+version.capitalize()
		tmp+= nline[-1]
	else:
		tmp = line

	return tmp

def fresh_install():
	for i, path in enumerate(addonpaths):
		print("Copying build to: ",path)
		try:
			if os.path.isdir(os.path.join(path,stagepath)):
				shutil.rmtree(os.path.join(path,stagepath))
		except:
			print("> issue removing existing addon path:")
		try:
			shutil.copytree(stagepath,os.path.join(path, stagepath))
		except:
			print("> issue copying directory to install for: ")
			print(os.path.join(path, stagepath))

def run_cleanups():
	shutil.rmtree(stagepath)


# run main
main()
