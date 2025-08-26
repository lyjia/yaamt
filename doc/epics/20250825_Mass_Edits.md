The next set of changes are somewhat complicated and interrelated, but they all support workflows for editing and analyzing media file metadata. I want to make sure that the systems implementing these above features are congruent and harmonious with each other and that we have a solid architecture for expanding the system outwards. These objectives represent some significant changes and will be some of the most important features of this program.

The objectives are as follows:

* Add a new edit-in-place feature to the file pane in MainWindow:
  * Double-clicking the value in a column should pop open a small textbox, showing the current value, and allow the user to make edits. 
  * The text inside the textbox should be highlighted when the textbox is opened. Once the textbox loses focus, or the user hits Enter, it should (optionally) persist the value that was entered into the appropriate metadata tag that that column represents. 
  * Note that this feature should only be available where the writer for the selected tag defines it as write-enabled. 

* Add a new feature called "Autosave" to MainWindow. 
  * When autosave is enabled, changes to metadata showin in MainWindow (either through the above feature) are immediately persisted to disk. 
  * The option to control this should be in the File menu, as a toggle labeled "Autosave".
  * When autosave is disabled, changes should be staged pending a user pressing "Commit":
    * which is either an entry in File menu called "Commit changes", 
    * or a new toolbar button (shaped as a check mark). 
  * Additionally, a "Reset changes" button is also available, which clears staged changes and reverts the UI to show the original data. 
  * Both Commit and Reset options should only be enabled when Autosave is disabled and there are changes staged.

* Users should be able to select multiple files and edit tags en masse. 
  * This should be able to occur both in the file pane of MainWindow, or in PropertiesWindow: 
    * For MainWindow, the selected files should remain highlighted after the edit-in-place textbox appears and continue to be highlighted after editing is complete. The workflow for this should be otherwise identical to single-file edit-in-place, which each column edited highlighted if Autosave is disabled. 
    * For PropertiesWindow, there are two possibilities, based on whether values for a given tag differ between all files:
      * If they differ, text boxes should display "<< multiple values >>" slightly grayed-out. 
        * If the user wants to edit that tag in all files and clicks the textbox, then the textbox becomes blank and wait for input, then stage that change for all selected files; 
      * If they are all the same, it should display that value for editing.
        * Behavior here should have the same workflow as editing a single file.

* Build the foundations for a new feature called "analyzers": 
  * which are specialized modules that read the media file's data stream and produce some sort of metadata output. 
  * For example: a BPM detector or Musicbrainz ID detector. 
  * Analyzers will be implemented similar to Providers, in that there is a base class defining an interface and individual analyzers inherit from that base class. 
    * For performance reasons, I would prefer the audio streams only be stored in memory once, and that analyzers are passed a reference to read the stream as opposed to each analyzer reading it themselves. (What they do with it beyond that is beyond the scope of this objective.) 
  * Users activate analyzers through the right-click menu, the File menu, or dedicated toolbar buttons. 
  * We will also make an extremely simple 'analyzer', which will read the audio stream and return the peak volume level 

