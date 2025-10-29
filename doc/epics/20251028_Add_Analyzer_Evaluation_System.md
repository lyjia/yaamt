We need a system to evaluate Analyzer performance against known/hand-reviewed key/bpm data.

I really like how MusicalKeyCNN has an evaluation script (eval.py) that can be run against a dataset and return "MIREX" scores for musical key analysis. (Note that we've added it as a submodule in @references/MusicalKeyCNN)

We need something similar, which:
* accepts a directory of audio files (and an accompanying reference CSV file with the hand-reviewed key/bpm data) -- see @tmp/consolidated_dataset_orig_20251022.csv
* accepts one or more CSV file containing analysis results -- see @tmp/analysis_report_key_librosa.csv as an example
  * there may be more than one analysis result file (e.g. one per analyzer or third-party program), it shou
* compares the reference to the analyzer outputs and calculates a MIREX score for each analyzer result sheet

We are comparing analyzers on two separate criteria:
* Key: We will use MIREX's audio key detection scoring system, specified at https://music-ir.org/mirex/wiki/2025:Audio_Key_Detection. 
  * In addition to scores, we will count the number of results that fall into each of the following categories expressing their relationship with the reference key: 
    * 'same key' (identical to reference), 
    * 'perfect fifth',  
    * 'relative major/minor', 
    * 'parallel major/minor', and 
    * 'other'  
* BPM: We will use our own scoring system for determining the accuracy of BPM detection results, with all results rounded to two decimal places:
  * 1 point: difference between reference and analyzed BPM is less than 1/100 BPM (e.g. 175.00 vs 175.003)
  * 0.5 point: analyzed BPM is accurate to 1/10 of the reference BPM (e.g. 175.00 vs 174.92)
  * 0.25 point: analyzed BPM is accurate to 1/5 of the reference BPM (e.g. 175.00 vs 174.84)
  * Any other result is 0 points.

Analyses will be calculated separately for each analyzer and/or third-party program, and this script should accept multiple analysis result files. It should only accept results from one criteria (key/bpm) at a time. 
After it has run its scoring, it should output a CSV file with results for the criteria it was run against.
It should use the column formats described in the CSV files linked in this document.

Note that the analysis file formats are determined by the "Generate Report" option in the Analyzer GUI, and the "consolidated dataset" format is defined by @scripts/consolidate_datasets.py.