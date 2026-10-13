# Ten photographs for Clef Atlas

Upload-ready photos across ten countries, with a mixture of recognisable and ambiguous clues. Difficulty labels are presenter estimates, not measured model results.

## Use in the existing web app

1. Extract this archive. Start the Clef Atlas project as usual.
2. Expand **Use your own photograph**, then upload any `images/round-XX.jpg`.
3. Choose **Live API** to get an actual model prediction. Offline mode uses invented fixtures and does not classify these photographs.
4. From `answers.csv`, enter the known country and camera latitude/longitude for reveal. Leave the optional clue field empty for a fair vision-only round. Ensure the actual country is in the candidate list.
5. Make your guess, run the model, then reveal. Repeat with the next photo.

All ten countries are already in the app's supported shortlist. No code changes are required. The images are not automatically added to the app's practice-round selector; use the upload control.

## Use in the notebook

Set `PHOTO_PATH` to the path of one image, set the candidate list to include its country, then explicitly enable `RUN_LIVE`. Do not pass the answer key or source filename/title as model evidence. The notebook defaults to no live inference.

## Contents

- `images/`: 10 neutral filenames, JPEGs under 4 MiB each, maximum side 1280 pixels.
- `answers.csv`: quick country/location lookup. Presenter only; contains spoilers.
- `answers.json`: detailed machine-readable metadata, original source URLs and attribution.
- `CREDITS.md`: author/source/licence links, including modification notices. Keep with shared copies.
- `presenter-contact-sheet.jpg`: preview with city labels. Contains spoilers.

GPS/EXIF metadata has been removed from the JPEGs. Coordinates in the answer key are camera locations supplied by Commons contributors, not independently verified survey points. A country guess is the core benchmark; the app's AI map pins are capitals, not exact photo predictions.

The source photos are licensed CC BY-SA 4.0, CC BY 3.0 or CC0, as listed individually in CREDITS.md. Real photo inference has not been run on this collection.
