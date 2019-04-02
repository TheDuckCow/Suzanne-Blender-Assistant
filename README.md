# The Suzanne Blender Assistant Addon

## Purpose of addon

[Directly download the addon here](https://github.com/TheDuckCow/Suzanne-Blender-Assistant/archive/master.zip).

Let's be clear. This is an April Fool's joke made in conjunction with [Theory Studios](http://theorystudios.com).

That being out of the way, this addon "enhances" Blender (2.7 or 2.8, both should work!) by giving the user a helpful assistant that will give advice or provide suggested changes.

### But could this be like, actually helpful?

Yes. In fact, the plan is to have a toggle setting (default off) for being actually useful. This removes any suggestions/comments that are ridiculous, or adjusts the behavior to be actually useful.

### Can I submit new suggestions?

Please! Fill out [this form here](https://forms.gle/5KPyzQynnXWVbKzC6) with your ideas, and see [all results here](https://docs.google.com/spreadsheets/d/1QC-s3UjMsrqdpdjbknPL3bgV5xxSqgso8R8H2zNqtAA/). Not everything will be implemented, but any ideas are more than welcome.


## Technical implementation

The suggestions and tips are all located in a tab-separated file (tsv). Each tip has the following structure by column:

- unique id: Unique identifier for the suggestion
- condition: What it requires to trigger
	- To have multiple conditions, the column in the tsv file will have space separated individual conditions, and within a single condition (format of type:value), there could be an array of OR'd together sub options, which are separated by commas.
	- Example condition value: "prev:tut_02,tut_03 elapsed:10s", this has two conditions. First is "only trigger if the previous suggestion detected had the unique id tut_02 OR tut_03", and the second is "Only trigger this suggestion if 10 seconds have elapsed since the last triggered popup".
- icon: Optionally indicate specific icon to use of the assistant
- suggestion: Text that the assistant will have in popup
- buttons: Sets the type of buttons to show in the popup
  - Either "ok", "none", "dismiss", or "ok,dismiss"
  - "ok": Means display an OK with the suggestion popup, which furthermore implies a specific action to take when pressed (ie the suggestion itself)
  - "dismiss": means a tick box with show allowing user to dismiss this suggestion for the rest of the session
  - "none": Means don't show the OK or a dismiss tick box, good for one-off message
- button_action: function name, with additional arguments are inputs (separated by spaces). This general purpose field can be used to specific the operator to run by placing the name of the operator (everything after bpy.ops.)

When a suggestion action is completed (where a button applies and dismiss is enabled), the unique ID is appended to a persistent log file for the addon. This is primarily used to verify if an action/state has already been shown before, e.g. only showing the tutorial intro suggestions once. An option should be implemented to reset this, taking the form of clearing out/deleting this file and starting anew.

Checks for states are ran at a max of every n seconds (can be fraction), setting could be added to user preferences in the future.


### Showing recommendations

To be effective, this addon must check for a large number of different configurations in the background without slowing down Blender. Each suggestion has a trigger_condition, which come in one of two types:

**Current-state checks**: These are any conditions which can be determined by checking current settings in the file. Examples: render resolution or what objects are in the scene.

**Operator sequencing**: These conditions which are checked for by looking at the recent sequence of completed operators.

**Combination**: Some suggestions might be the result of both of the above, e.g. only triggered after a specific operator has just been run (e.g. deleted object) *and* another state is positive in the file (0 objects left).

**Ignore operators**: These are operators to be ignored while doing operator sequence checks. By default, the following are excluded: select (all/none/etc), any translation/rotation/scaling, changing mode (object, pose, etc).

Each of these types of triggers are implemented through pre-written functions. Where relevant, results are cached. New states are only calculated after infrequent refreshes using timers.
