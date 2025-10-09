One of the key features of this YAAMT is its ability to analyze audio files for additional metadata that can be saved to a file's meta tags.

# UX for using an analyzer

The workflow for using an analyzer is as follows:

1. Right-click an audio file or group of audio files.
2. In the context menu is a submenu called "Analyze".
3. Pick the category of analyzer you want to use: analyzers can be run to determine MusicBrainz ID, ReplayGain values, song key, BPM, and more.
4. A dialog box pops up to let you select the specific analyzer and configure it. (See `AnalyzerSetupDialog`)
5. The analyzer runs and the results are saved to relevant meta tags in the selected file(s).

Metadata changes obey autosave settings. Analyzers stage their results to the MediaFile object just as if the user had manually entered the data. If autosave is enabled, each file is saved immediately after its analysis completes. If autosave is disabled, the user must manually save changes when ready.

# Analyzer workflow

* Analyzers run in a queue, potentially in the background and/or in parallel.
* Each analyzer has a single task: determine a single piece of data for a single file. Multiple files are enqueued and executed separately.
* Analyzers are run in the order they are added to the queue.
* While an analyzer is running, the user is shown a modal window that shows the progress of the analyzer. (See `AnalyzerProgressDialog`)
* When the queue is cleared, the user is presented with a summary dialog box reporting results of the analysis run. (See `AnalyzerSummaryDialog`)
* Analyzers obey user preferences if needed. For example: the user may want all key codes to be saved in Camelot notation.

## AnalyzerSetupDialog

* Shows available analyzers for the selected category (Categories are modules in the `providers.analysis` package)
* Allows the user to select which specific analyzer to run
* Presents the user with a panel of options specific to that analyzer
* Pre-selects the user's preferred analyzer for that category

## AnalyzerProgressDialog

* has a progress bar depicting total progress and a label showing the current file(s) being analyzed
* displays the name of the analyzer that is running.
* has a cancel button that can be used to cancel the analyzer and clear the queue. The user should be asked if they would like to keep existing analysis data or purge it.

## AnalyzerSummaryDialog

* Shows a count of files successfully analyzed, out of the total requested. 
* Shows a list of files that failed to analyze or were skipped, and why.
* Has a button that will highlight failed/skipped files in MainWindow to allow analysis to be retried.

# Design considerations

* Analyzers live in the `providers.analysis` package.
* All analyzers must inherit from a base class, `AnalyzerBase`.
* Analyzers should be presented with a `MediaFile` instance representing the file that is to be analyzed.
    * This `MediaFile` instance should be passed to the constructor of the analyzer.
    * The `MediaFile` instance has functions that allow analyzer will save its metadata to the file.
* Analyzers can be further categorized by the fields they seek to generate data for: for example, `providers.analysis.gain` or `providers.analysis.bpm`.
  * There can be more than one analyzer for a given kind of metadata.
  * In the preferences screen, the user should be able to select a preferred analyzer for each category.
* Analyzers use `providers.audio` to access audio data. It is important that they do not duplicate efforts here. Where possible the analyzer should perform its analysis with a stream reader that does not need to load the whole file into memory at once.
* Analyzers need to be able to run on very long audio files -- users may have files longer than 12 hours!
* Analyzers should be able to run concurrently
* Analyzers run in a background thread.
* A separate dispatcher handles the queueing, running, and threading of analyzers. For now it will run analyzers sequentially, but it should be able to handle running analyzers in parallel.