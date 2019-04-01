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


import csv
import os
import threading
import time

import bpy


# -----------------------------------------------------------------------------
# Globals for state tracking
# -----------------------------------------------------------------------------

# Configuration
CHECK_INTERVAL = 5 # time in seconds
SCENE_POPUP_INTERVAL = 7 # min time in seconds before allowing another popup to generate
LAST_N_ACTIONS = 20 # cache of last number of operators/prop changes to check
VERBOSE = True # extra printouts

# global state saving with appropriate initial values
LAST_CHECK = 0 # last check for suggestions
UI_LAST_CHECK = 0
#LAST_POPUP_TIME = 0
BACKGROUND_THREAD = None # registration of the background thread object
STOP_SERVER = False # global message used to stop background thread
SUGGESTION_BANK = [] # list of template suggestions
SUGGESTIONS = {} # dict of details for active suggestion
OPS_SEQUENCE = [] # list of recent operators, last entry is most recent run
PREVIOUS_SUGGESTION = None # csv id text of previous suggestion, for state tracking
PREVIOUS_POPUP = None # to help 'debounce' popup UIs
DISMISSED = {} # all suggestions that have been dismissed

# actions to ignore when looking back at recent user driven changes
IGNORE_ACTIONS = ["Warning:", "bpy.ops.object.select_all",
	"bpy.context.area.type =", "bpy.context.space_data.context =",
	"bpy.ops.object.location_clear", "bpy.ops.assist.suggestion_action"]

# -----------------------------------------------------------------------------
# Compatibility functions
# -----------------------------------------------------------------------------


def log(statement):
	"""General purpose simple logging function."""
	if VERBOSE:
		print("[assistant] "+str(statement))


def make_annotations(cls):
	"""Add annotation attribute to class fields to avoid Blender 2.8 warnings"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return cls
	bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
	if bl_props:
		if '__annotations__' not in cls.__dict__:
			setattr(cls, '__annotations__', {})
		annotations = cls.__dict__['__annotations__']
		for k, v in bl_props.items():
			annotations[k] = v
			delattr(cls, k)
	return cls


def get_preferences(context=None):
	"""Function to easily get general user prefs in 2.7 and 2.8 friendly way"""
	if not context:
		context = bpy.context
	if hasattr(context, "user_preferences"):
		return context.user_preferences
	elif hasattr(context, "preferences"):
		return context.preferences
	return None


def get_addon_preferences(context=None):
	"""Intermediate method for pre and post blender 2.8 grabbing preferences"""
	if not context:
		context = bpy.context
	prefs = None
	if hasattr(context, "user_preferences"):
		prefs = context.user_preferences.addons.get(__package__, None)
	elif hasattr(context, "preferences"):
		prefs = context.preferences.addons.get(__package__, None)
	if prefs:
		return prefs.preferences
	return None


def layout_split(layout, factor=0.0, align=False):
	"""Intermediate method for pre and post blender 2.8 split UI function"""
	if not hasattr(bpy.app, "version") or bpy.app.version < (2, 80):
		return layout.split(percentage=factor, align=align)
	return layout.split(factor=factor, align=align)


def ui_scale():
	"""Returns scale of UI for width drawing. Compatible down to blender 2.72"""
	prefs = get_preferences()
	if not hasattr(prefs, "view"):
		return 1
	elif hasattr(prefs.view, "ui_scale") and hasattr(prefs.view, "pixel_size"):
		return prefs.view.ui_scale * prefs.system.pixel_size
	elif hasattr(prefs.system, "dpi"):
		return prefs.system.dpi/72
	else:
		return 1


# -----------------------------------------------------------------------------
# Threading and interval infrastructure
# -----------------------------------------------------------------------------


def load_suggestions():
	"""Load (and rename from update) the tab-delimited suggestions file"""
	global SUGGESTION_BANK

	# overwrite/rename updated suggestion file to final format
	tsv_update = os.path.join(os.path.dirname(__file__), "suggestions_update.tsv")
	tsv = os.path.join(os.path.dirname(__file__), "suggestions.tsv")
	if os.path.isfile(tsv_update):
		if os.path.isfile(tsv):
			os.remove(tsv)
		os.rename(tsv_update, tsv)
	if not os.path.isfile(tsv):
		log("Suggestions file not found")
		return

	# load csv with tab delineation (tsv) into dictionary format
	suggestion = []
	with open(tsv, mode='r') as infile:
		lines = infile.readlines()
		reader = csv.DictReader(lines, delimiter='\t')
		for entry in reader:
			suggestion.append(entry)

	# pivot from item in single row in list, to key for that dict within dict
	SUGGESTION_BANK = suggestion # {itm['id']:itm for itm in suggestion}
	log("Found {} suggestions from tsv file".format(len(SUGGESTION_BANK)))


def start_background_thread_if_none():
	"""Initializes the primary running background thread, to avoid UI blocks.

	Note this is triggered constantly by UI redrawing, end quickly wherever
	possible.
	"""
	if STOP_SERVER is True:
		return

	global BACKGROUND_THREAD
	global LAST_CHECK
	now = time.time()
	if BACKGROUND_THREAD and BACKGROUND_THREAD.is_alive():
		# log("Is alive.. so all good")
		return
	if BACKGROUND_THREAD and not BACKGROUND_THREAD.is_alive():
		BACKGROUND_THREAD = None  # thread died/ended
	if LAST_CHECK and now < LAST_CHECK + CHECK_INTERVAL:
		return # interval not passed, failsafe to not constantly create threads
	if not LAST_CHECK:
		LAST_CHECK = now # to prevent double execution

	log("Starting new background assistant thread")
	BACKGROUND_THREAD = threading.Thread(target=assistant_thread)
	BACKGROUND_THREAD.daemon = True # re-uncoment?
	BACKGROUND_THREAD.start()


def assistant_thread():
	"""Long-running function in background thread to perform state checks"""
	global STOP_SERVER
	global LAST_CHECK
	global SUGGESTIONS

	if not SUGGESTION_BANK:
		load_suggestions()

	first_live = time.time()

	# primary never ending loop
	while STOP_SERVER is False:
		now = time.time()
		if LAST_CHECK and now < LAST_CHECK + CHECK_INTERVAL:
			time.sleep(LAST_CHECK + CHECK_INTERVAL - now)

		LAST_CHECK = time.time()
		log("Checking now for suggetions")
		update_ops_sequence()
		log("Finished checking for suggestions")
		log("First live:"+str(first_live))

		generate_suggestions()

		# temporary override to execute once
		# TODO: in future, use signals or others so that a single ongoing
		# living thread won't hang blender on quit if not deliberatly stopped
		break

	log("Stopping assistant thread")
	global BACKGROUND_THREAD
	BACKGROUND_THREAD = None


def update_ops_sequence():
	"""Gets the most recent operators ran using text util (slightly hacky)"""
	global OPS_SEQUENCE

	# generate text block of recent actions (operators & prop changes)
	text_list = list(bpy.data.texts)
	res = bpy.ops.ui.reports_to_textblock()
	if res != {'FINISHED'}:
		OPS_SEQUENCE = []
		return
	new_text_list = list(bpy.data.texts)
	new_texts = list(set(new_text_list) - set(text_list))
	if not new_texts:
		log("Error getting new text list for ops")
	OPS_SEQUENCE = []

	# copy the last 10 actions
	for line in reversed(new_texts[0].lines):
		if not line.body:
			continue
		for itm in IGNORE_ACTIONS:
			if itm in line.body:
				continue
		OPS_SEQUENCE.append(line.body)
		if len(OPS_SEQUENCE) >= LAST_N_ACTIONS:
			break

	# clean up the generated text
	bpy.data.texts.remove(new_texts[0])
	log("Loaded {} actions".format(len(OPS_SEQUENCE)))


def get_dismissed_suggestions():
	"""Returns list of past dismissed suggestions"""
	return list(DISMISSED)


def save_dismissed_suggestion(idname, disk=False):
	"""Saves the fact that a suggestion was just dismissed"""
	DISMISSED[idname] = disk

	if disk is True:
		log("Saving dismissed tips to file is not implemented yet")


# -----------------------------------------------------------------------------
# Suggestion conditional functions
# -----------------------------------------------------------------------------


def generate_suggestions():
	"""The primary function to set the next suggestion, from background thread

	As new suggestions are added, they shoudl be accounted for here.
	"""
	global SUGGESTIONS

	context = bpy.context

	# go through types of conditions, order matters
	local_sugg = {}
	if PREVIOUS_SUGGESTION:
		prev_id = PREVIOUS_SUGGESTION
	else:
		prev_id = "n/a"
	for sugg_set in SUGGESTION_BANK:
		log("Checking condition: {} (prev:{})".format(
			sugg_set["id"], prev_id))
		if sugg_set["id"] in get_dismissed_suggestions():
			continue

		# iterate through space-separate set of conditions
		conditions = sugg_set["condition"].split(" ")
		log("Conditions for set {}: {}".format(sugg_set["id"], str(conditions)))
		condition_met = True

		# check each sub condition for being a match
		for cond in conditions:
			if cond == "not_dismissed":
				continue # already accounted for by being here
			elif cond == "no_prev": # essentially only used by first tutorial
				if PREVIOUS_SUGGESTION is not None:
					condition_met = False
					break
			elif cond.startswith("prev:"):
				any_of = cond[5:].split(",")
				if PREVIOUS_SUGGESTION not in any_of:
					condition_met = False
					break
			elif cond.startswith("elapsed:"):
				interval = cond[8:-1] # assumes s at end for seconds
				if int(interval) > time.time() - UI_LAST_CHECK:
					condition_met = False
					break
			elif cond.startswith("ops_last:"):
				# check if last operator was this one
				if cond[9:] not in OPS_SEQUENCE[-1]:
					condition_met = False
					break
			elif cond.startswith("ops_recent:"):
				# check if operator was used recently
				op_used = False
				for one_op in OPS_SEQUENCE:
					if cond[11:] in OPS_SEQUENCE:
						op_used = True
						break
				if not op_used:
					condition_met = False
					break
			elif cond.startswith("object_exists:"):
				if cond[14:] not in bpy.data.objects:
					condition_met = False
					break
			elif cond.startswith("no_object_exists:"):
				if cond[17:] in bpy.data.objects:
					condition_met = False
					break
			elif cond == "is_void":
				if not is_void(context):
					condition_met = False
					break
			elif cond == "no_camera":
				if not has_no_camera(context):
					condition_met = False
					break
			else: # others or not implemented
				log("Condition type not recognized:"+str(cond))
				condition_met = False

		if condition_met is True:
			local_sugg = sugg_set
			log("Condition met, assigning")
			break
		else:
			continue

	SUGGESTIONS = local_sugg
	# finished


def is_void(context):
	"""Checks to see that the current scene is empty, ie a void"""
	if not context.scene.objects:
		return True
	return False


def has_no_camera(context):
	"""Checks if there is no camera in scene"""
	for ob in context.scene.objects:
		if ob.type == "CAMERA":
			return False
	return True



# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


def register():
	global STOP_SERVER
	STOP_SERVER = False


def unregister():
	global STOP_SERVER
	global SUGGESTIONS
	global SUGGESTION_BANK
	STOP_SERVER = True
	SUGGESTIONS = {}
	SUGGESTION_BANK = []
