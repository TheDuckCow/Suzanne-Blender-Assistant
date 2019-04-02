# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Author: Patrick W. Crawford, Google LLC. Not an official Google product.


bl_info = {
	"name":        "Suzanne Blender Assistant",
	"description": "Enjoy using Blender with a 'helpful' assistant",
	"author":      "Patrick W. Crawford, Theory Studios",
	"version":     (1, 0, 1),
	"blender":     (2, 80, 0),
	"location":    "Info Header, right-hand side",
	"warning":     "This is an April Fool's Joke addon!",
	"wiki_url":    "https://forms.gle/5KPyzQynnXWVbKzC6",
	"tracker_url": "https://github.com/TheDuckCow/Suzanne-Blender-Assistant/issues",
	"category":    "System"
	}

import importlib

if "load_modules" in locals():
	importlib.reload(load_modules)
else:
	from . import load_modules
import bpy


def register():
	load_modules.register(bl_info)


def unregister():
	load_modules.unregister(bl_info)


if __name__ == "__main__":
	register()
