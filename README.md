# photrix
Photometric trickery for PLANNING and DATA REDUCTION supporting the **New Mexico Mira Project**'s programs in variable-star photometry, largely to support lightcurves administered by the [AAVSO](https://aavso.org%20%22), the American/Awesome/Allgemeine Association of Variable Star Observers.

The photrix code base has two functions:

**1. Planning:** this is in pretty good shape. After the SAS/AAVSO meeting mid-June 2017, I'll duplicate my poster in this repo. It tells all. Essentially, the code generates a roster of LPV and eclipser variable-star targets that:

 - are **available** tonight, for long enough above the horizon, and
   with no moon too close, *and*
 - have sufficient **priority**. This is a dynamic priority, which is lowered for a target if it has been recently observed according to AAVSO's WebObs database.

Then the user drags-and-drops star names from the daily roster to a planning spreadsheet and juggles the names at will. When the .txt summary sheet is sweetened to taste, the ACP (Astronomer's Control Panel) machine-readable plan files written at the same time can be uploaded directly to the telescope PC.

**2. Data reduction:** This new python code is ported from R code in old repo 'Photometry-R'). It was ported to python, tested, late July 2017 and has bee in daily use since then

## The code, such as it is

All code in photrix is based on python 3.5. To be clear right up front, it does depend on some packages: 

 - **ephem**: for base astronomical calculations that I have no patience to reinvent (not compatible with all python versions)
 - **pandas**: this package makes python almost as good as R is with no packages at all
 - **pytest**: skin-pricklingly-shiver-inducingly-awesome unit testing. Python's best feature.
 - **requests**: polls AAVSO's databases when needed
 - **beautifulsoup4**: parse raw data that 'requests' downloads
 - **matplotlib**: primitive graphics
 - **statsmodels**: mixed-model regression. Like R's lmer, but without all that bothersome clarity and accurate documentation

You might well ask: why port to python at all, given all my whinging & wailing. Yes, it's true, sometimes I throw manuals out the office window (impressive, as they are PDFs). 

The only reason to port from R to python is unit testing. Well, OK, true object orientation. Probably other stuff. Go ahead and read of my py-ecstasy and py-agony in Python-Love-Hate.md (this repo).

## Status of this repository

**Planning sections** of this repository are functioning now. Not to say they couldn't be improved. They certainly will be.

**Data-reduction sections** functioning now. Based on mixed-model regression.

No other sections are expected. (The above two are plenty to deal with.)




