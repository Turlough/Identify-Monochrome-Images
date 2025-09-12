# Monochrome detector
A PyQt6 app for converting selected JPG files to G4 TIFF.
## Purpose
All pages have been scanned in colour. 
The user manually identifies monochrome pages. 
The user clicks Convert when done. The selected files are converted, and the source list updated.
## Use
The menu bar has a "File" menu with two options: "Load List" and "Convert".
The app has two panels:
- Left: A scrollable grid of thumbnails(8 * 4). 
Each cell displays the filename in a small font underneath the thumnail, 
and a tickbox over the top right of the thumbnail. The user may also click on the image itself without ticking the tickbox.
- Right: A larger view of the selected thumbnail, fit to the panel size.
Ticking the tickbox or clicking the image will show the larger view.

This app enables the user to:
- Load a text file describing the document structure. 
- Displays a scrollable grid of thumbnails of all listed jpgs from all the listed documents
 (but excludes .tif, as these have already been converted).
- The user ticks the images that are to be converted to monochrome. 
- At any time the user may select "Convert". The ticked items are converted to G4 TIFFs (.tif) 
and the source text file is updated with the new filename. 
The ticked items (i.e. the tiffs) are removed from the thumbnail grid.

## The input file
See (sample_import_file.txt)

The input file is a text file (.txt, .csv) with a comma separated list.
The first item in each row is the filename (without extension) of the final document. For now, disregard this.
It is followed by the list of files (jpg and tif) that will form the pages of the final document. 

For the JPGs that have been converted to G4 tif, the corresponding filename in the list is updated to .tif instead of .jpg
Tif files are not included in thumbnails as they have already been converted.