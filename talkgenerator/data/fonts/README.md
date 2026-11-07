# Fonts to measure with

Open fonts with the same metrics (the same width for every character) as fonts that themes use, so that
`talkgenerator.design.fonts` measures texts the same way on every computer, also where the original fonts aren't
installed (such as a Linux server). The slides themselves still name the originals (Arial, Calibri, ...), which
PowerPoint shows. Only the regular and bold styles are here: those are what the layout engine measures with.

| File | Stands in for | Version | From | License |
| --- | --- | --- | --- | --- |
| `LiberationSans-Regular.ttf`, `LiberationSans-Bold.ttf` | Arial | 2.1.5 | [liberationfonts/liberation-fonts](https://github.com/liberationfonts/liberation-fonts/releases/tag/2.1.5) | SIL Open Font License 1.1 (`LICENSE-Liberation.txt`) |
| `LiberationSerif-Regular.ttf`, `LiberationSerif-Bold.ttf` | Times New Roman | 2.1.5 | the same | the same |
| `LiberationMono-Regular.ttf`, `LiberationMono-Bold.ttf` | Courier New | 2.1.5 | the same | the same |
| `Carlito-Regular.ttf`, `Carlito-Bold.ttf` | Calibri | 1.104 | [google/fonts, `ofl/carlito`](https://github.com/google/fonts/tree/main/ofl/carlito) | SIL Open Font License 1.1 (`OFL-Carlito.txt`) |
| `Caladea-Regular.ttf`, `Caladea-Bold.ttf` | Cambria | 1.002 | Chrome OS's `crosextrafonts-20130214.tar.gz` ([its mirror](https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/crosextrafonts-20130214.tar.gz)) | Apache License 2.0 (`LICENSE-Caladea.txt`) |
| `Gelasio-Regular.ttf`, `Gelasio-Bold.ttf` | Georgia | 1.008 | [SorkinType/Gelasio, `fonts/ttf`](https://github.com/SorkinType/Gelasio/tree/main/fonts/ttf) | SIL Open Font License 1.1 (`OFL-Gelasio.txt`) |

Caladea is the 2013 release from Chrome OS, as the one in google/fonts has been redrawn and is about 5% narrower
than Cambria. Measured on Windows' own fonts (a sentence at 100 pixels), every one of these comes out as wide as the
font it stands in for, within half a percent.

The other fonts themes use (Arial Black, Verdana, Trebuchet MS, Impact, Comic Sans MS) have no open twin: where
they aren't installed, their texts are estimated, generously (`ESTIMATE_MARGIN`).
