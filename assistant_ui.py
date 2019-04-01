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

import os
import random
import textwrap
import time

import bpy
try:
	import bpy.utils.previews
	use_icons = True
except:
	use_icons = False
	print("[assistant] No custom icons in this blender instance")

from . import assistant_tools as tools


# -----------------------------------------------------------------------------
# Operators and classes
# -----------------------------------------------------------------------------


SUGGESTION_FORM_URL = "https://forms.gle/5KPyzQynnXWVbKzC6"
RANDOM_TICK = None  # used to display a random assistant icon


@bpy.app.handlers.persistent
def scene_update_handler(scene):
	"""Runs when scene updates, to see whether to display a suggestion.

	This will trigger constantly, be warned!
	"""
	if tools.SUGGESTIONS == {}:
		return
	if tools.get_addon_preferences().passive is True:
		return
	if tools.SUGGESTIONS["id"] in tools.DISMISSED:
		return
	if tools.PREVIOUS_POPUP == tools.SUGGESTIONS["id"]:
		return # don't retrigger the same suggestion
	if time.time() < tools.SCENE_POPUP_INTERVAL + tools.UI_LAST_CHECK:
		return  # don't trigger a new popup yet
	tools.UI_LAST_CHECK = time.time()
	tools.log("Suggestion found, triggering popup")
	bpy.ops.assist.suggestion_action('INVOKE_DEFAULT')
	tools.PREVIOUS_POPUP = tools.SUGGESTIONS["id"]


def word_wrap(element, text, width=400):
	"""Utility for wrapping text over multiple lines for UI drawing"""
	# context.user_preferences.system.pixel_size
	# width =
	label_lines = text.split("\n")
	for line in label_lines:
		sub_lns = textwrap.fill(line, width/5.5) # /5 in place of actual kerning
		spl = sub_lns.split("\n")
		for sub_line in spl:
			element.label(text=sub_line)


def get_suzanne_mood(self, context):
	"""Sets single item of UI List for icon display purpsoes"""
	global RANDOM_TICK
	if len(preview_collections["assistant_poses"]) >= RANDOM_TICK:
		RANDOM_TICK = 0
	use_set = sorted(list(preview_collections["assistant_poses"]))[RANDOM_TICK]
	thumbnails = []
	if not tools.SUGGESTIONS:
		thumbnails.append((
			"derp", # unused python access prop value
			"derp", # Display name
			"I'm here to help", # hover text
			preview_collections["assistant_poses"]["derp"].icon_id, # icon!
			0 # retain order
		))
	else:
		thumbnails.append((
			use_set, # unused python access prop value
			use_set, # Display name
			"I'm here to help", # hover text
			preview_collections["assistant_poses"][use_set].icon_id, # icon!
			0 # retain order
		))
	return thumbnails


class ASSIST_OT_assistant_suggestion_action(bpy.types.Operator):
	"""Let your Blender Assistant, Suzanne, share any current suggestions"""
	bl_idname = "assist.suggestion_action"
	bl_label = "Suzanne, your Blender Assistant"
	bl_options = {'REGISTER', 'UNDO'}

	assistant_mood = bpy.props.EnumProperty(
		items=get_suzanne_mood,
		options = {'HIDDEN'})

	dismiss = bpy.props.BoolProperty(
		name = "Dismiss this tip from showing again",
		description = "After ticking this box and pressing OK below, this tip will no longer display.",
		default = False)
	action = bpy.props.StringProperty(
		name = "",
		description = "The output action to take, displayed as a property like so in order to show up in oprator history",
		default = False,
		options = {'HIDDEN'})

	#action = None  # util used to avoid re-grabbing suggestion state (could change)
	suggestion_id = None
	suggestion_state = None

	def invoke(self, context, event):
		"""Show dialogue with OK button or not"""

		# copy suggestions at this point in time for correct results
		if tools.SUGGESTIONS:
			self.suggestion_state = tools.SUGGESTIONS.copy()
		else:
			self.suggestion_state = None

		# update the random tick for selecting assistant icon (once per show)
		global RANDOM_TICK

		RANDOM_TICK = random.randint(
			0, len(preview_collections["assistant_poses"]))

		# decide if showing an OK box or fleeting popup
		show_ok = True
		# self.dismiss = False # default to turn off
		# print("buttons a thing?", self.suggestion_state["buttons"])
		# if self.suggestion_state is not None and "ok" not in self.suggestion_state["buttons"]:
		# 	show_ok = False
		wm = context.window_manager
		if show_ok:
			return wm.invoke_props_dialog(self, width=400*tools.ui_scale())
		else:
			return wm.invoke_popup(self, width=400*tools.ui_scale())

	def draw(self, context):
		assistant_icon = preview_collections["assistant_poses"]["default"]
		row = self.layout.row()
		prefs = tools.get_addon_preferences()

		# if use_icons:
		split = tools.layout_split(row, factor=0.30)
		left = split.column()
		right = split.column()
		left.template_icon_view(
			self,
			'assistant_mood',
			show_labels=False
			#scale=1,
		)
		r_subcol = right.column()
		r_subcol.scale_y = 0.8
		if self.suggestion_state is None or self.suggestion_state == {}:
			text = "Oops! Looks like I'm fresh out of suggestions, but feel free to return the favor and help me learn.\n\nPress OK below to open the form in your web browser."
			buttons = "ok"
			dismiss = False
			self.action = "url:"+SUGGESTION_FORM_URL
			self.suggestion_id = None
		else:
			text = self.suggestion_state["suggestion"]
			buttons = self.suggestion_state["buttons"]
			dismiss = "dismiss" in self.suggestion_state["buttons"]
			if self.suggestion_state["action"]:
				self.action = self.suggestion_state["action"]
			else:
				self.action = None
			self.suggestion_id = self.suggestion_state["id"]

		word_wrap(r_subcol, text, 400*tools.ui_scale()*0.7)
		if dismiss:
			right.prop(self, "dismiss")

	def execute(self, context):
		tools.LAST_CHECK = time.time()
		if self.dismiss is True and self.suggestion_id:
			tools.save_dismissed_suggestion(self.suggestion_id)
		if not self.action:
			tools.log("No actions currently being taken")
			return {'FINISHED'}
		if self.suggestion_id:
			tools.PREVIOUS_SUGGESTION = self.suggestion_id

		# implement the different forms of actions here
		actions = self.action.split(" ")
		for act in actions:
			if act.lower().startswith("url:"):
				bpy.ops.wm.url_open(url=act[4:])
			elif act.lower().startswith("ops:"):
				tools.log("Triggering operator: "+act[4:])
				if "." not in act:
					tools.log("Invalid operator name, no period")
					continue
				atr = act[4:].split(".")
				if not hasattr(bpy.ops, atr[0]):
					tools.log("No base operator: bpy.ops." + atr[0])
					continue
				elif not hasattr(getattr(bpy.ops, atr[0]),atr[1]):
					tools.log("No operator: bpy.ops." + atr)
					continue
				getattr(getattr(bpy.ops, atr[0]),atr[1])('INVOKE_DEFAULT')
			elif act == "trigger_followup":
				# special case to force popup to show up sooner
				tools.LAST_CHECK -= 10
				tools.UI_LAST_CHECK = tools.LAST_CHECK

		return {'FINISHED'}


def update_verbose(self, context):
	"""Used to update printout logging verbosity"""
	tools.VERBOSE = self.verbose


class SBA_preferences(bpy.types.AddonPreferences):
	bl_idname = __package__

	verbose = bpy.props.BoolProperty(
		name = "Verbose",
		description = "Print out more logging information, for debugging",
		update = update_verbose,
		default = False)
	helpful = bpy.props.BoolProperty(
		name = "Helpful suggestions only",
		description = "If enabled, only realistic or actually useful suggestions are provided (ie the non April fools part of this addon)",
		default = False)
	passive = bpy.props.BoolProperty(
		name = "Be more passive",
		description = "If enabled, do not force showing popups and only indicate when suggestions are available via a change of icon in the INFO header",
		default = False)

	def draw(self, context):
		layout = self.layout
		if bpy.app.version < (2,80):
			row = layout.row()
			split = tools.layout_split(row, factor=0.5)
			left = split.column()
			right = split.column()
		else:
			left = layout.row()
			right = layout.row()

		col = left.column()
		col.scale_y = 0.8
		col.label(text="Happy April 1st (2019)!")
		col.label(text="")
		col.label(text="Yes, this addon has been made as a joke, alluding to")
		col.label(text="a certain famous paperclip. That being said, if you")
		col.label(text="somehow find this addon useful (or could be), feel")
		col.label(text="free to submit your suggestions here:")

		col = right.column()
		col.scale_y = 2
		if bpy.app.version < (2,80): # center better if not 2.8
			col.label(text="")
		col.operator("wm.url_open", text="Open suggestion form"
			).url = SUGGESTION_FORM_URL

		row = layout.row()
		row.prop(self, "verbose", text="Show verbose logging details")
		row.prop(self, "helpful", text="Show only 'helpful' suggestions")


# -----------------------------------------------------------------------------
# UI Classes
# -----------------------------------------------------------------------------


def header_draw(self, context):
	self.layout.operator(
		"assist.suggestion_action",
		icon='MONKEY',
		text='',
		emboss=False
	)
	# trigger loading of background thread if not
	tools.start_background_thread_if_none()


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------


classes = (
	SBA_preferences,
	ASSIST_OT_assistant_suggestion_action,
)


def register():
	for cls in classes:
		tools.make_annotations(cls)
		bpy.utils.register_class(cls)

	# append the suggestion draw code to the info window header
	bpy.types.INFO_HT_header.append(header_draw)
	if hasattr(bpy.types, "TOPBAR_MT_editor_menus"):
		bpy.types.TOPBAR_MT_editor_menus.append(header_draw)

	# setup icons
	global preview_collections
	preview_collections = {}
	icns = bpy.utils.previews.new()
	icns.folder = os.path.join(os.path.dirname(__file__), "icons")
	pngs = [png for png in os.listdir(icns.folder)
		if os.path.isfile(os.path.join(icns.folder, png))
		and png.lower().endswith(".png")]

	tools.log("Detected assistant icons: " +str(pngs))
	for png in pngs:
		icns.load(png[:-4], os.path.join(icns.folder, png), 'IMAGE')
	preview_collections["assistant_poses"] = icns

	# setup scene handler to trigger popups
	if bpy.app.version < (2, 80):
		bpy.app.handlers.scene_update_post.append(scene_update_handler)
	else:
		if hasattr(bpy.app.handlers, "depsgraph_update_post"):
			bpy.app.handlers.depsgraph_update_post.append(scene_update_handler)


def unregister():
	"""Clean up everything"""
	try:
		if bpy.app.version < (2, 80):
			bpy.app.handlers.scene_update_post.remove(scene_update_handler)
		else:
			if hasattr(bpy.app.handlers, "depsgraph_update_post"):
				bpy.app.handlers.depsgraph_update_post.remove(scene_update_handler)
	except:
		log("Issue trying to remove scene/depsgraph handlers on disable")
		pass

	bpy.types.INFO_HT_header.remove(header_draw)
	if hasattr(bpy.types, "TOPBAR_MT_editor_menus"):
		bpy.types.TOPBAR_MT_editor_menus.remove(header_draw)

	# remove icons
	if use_icons and preview_collections["assistant_poses"]:
		for pcoll in preview_collections.values():
			bpy.utils.previews.remove(pcoll)
		preview_collections.clear()

	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
