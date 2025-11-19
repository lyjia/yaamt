Navigating to a directory with lots of files (100+) is very slow, as we need to read metadata for each one before we can display the whole list. During this time the user must stare at an empty pane and that aspect of the program is useless.

We should be able to handle folders with tens or hundreds of thousands of files without skipping a beat, which means we need to optimize this process. 

While it is good that the program is not blocked due to this loading process, we want the user to be able to select and work with files with regards to what information is available.

I think we should take two approaches towards making the file pane more performant:

1. We should break down this loading processes into subprocesses, from fastest to slowest, and we should display the data we have ASAP.
2. Rather than trying to load an entire folder at once in sequential order, we should prioritize reading data for files that are visible in the file browser. This should adjust as the user scrolls through the list. Once all visible data has been loaded, we can proceed with loading metadata for unseen files in the background.

 For point 1, I propose breaking it down into the following phases:
 * First, we retreive path data (file/directory) about each file in the folder. This data is really already known, so its mainly just updating the relevant path-related columns in the model and allowing the file view to render. I think that this phase of loading should not be subject to the optimizations of approach #2, as otherwise the user has a view with completely empty rows, which we should avoid doing.
 * Second, we retrieve filesystem data (ctime/mtime/size/etc) about each file in the folder, prioritizing the files that are in view.
 * Third, we retreive metadata from each file in the folder, again prioritizing the files that are in view.

The record of which files are visible should be updated whenever the user scrolls the file listing, though we should be sure to debounce this sufficiently so that user actions are not generating unneeded load from constantly updating this list. Perhaps limiting it to once per second.

The file view itself should be updated with new results on a relatively short interval, say once or twice per second.
