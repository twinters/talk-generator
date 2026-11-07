# Fonts

Two kinds of fonts are here: twins, to measure fonts that nearly every computer has, and open fonts that themes use
themselves, which travel inside every .pptx that uses them. `talkgenerator.design.fonts` measures texts with both, so
font sizes come out the same on every computer, also where none of these fonts are installed (such as a Linux
server). Only the regular and bold styles are here: those are what the layout engine measures with.

## Twins to measure with

Open fonts with the same metrics (the same width for every character) as fonts that themes use. The slides
themselves name the originals (Arial, Calibri, ...), which PowerPoint shows.

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

The other fonts themes use (Arial Black, Verdana, Trebuchet MS, Impact, Comic Sans MS) have no open twin. For them,
`widths.json` has every character's width (in pixels, in text 100 pixels high), measured from their own files on
Windows 11 by `scripts/font_widths.py`: ASCII, Latin-1, Latin Extended-A and the rest of Windows' code page 1252,
339 characters in each of their regular and bold files. Where those fonts aren't installed, texts in them are measured
with these widths, which come out as wide as the fonts themselves; only a character outside the table is estimated,
generously (`ESTIMATE_MARGIN`). The table holds numbers, not the fonts: no outlines, nothing to draw or install with.
Run the script again on a computer with the fonts when a theme gets a font without a twin, or the fonts change (the
tests compare the table with the fonts where they're installed).

## Open fonts that themes use

Fonts with more personality than the ones every computer has, from [Google Fonts](https://github.com/google/fonts),
all under the SIL Open Font License 1.1, unmodified. A themed .pptx carries the ones it uses inside it, as PowerPoint
does when it embeds fonts (`talkgenerator.render.embedding`), so PowerPoint shows them where they aren't installed;
talkgenerator.com loads them from Google Fonts. All are static TrueType fonts that allow embedding (fsType 0). The
ones with only a regular are heavy display faces, used only for headings that aren't made bolder.

All from google/fonts at commit [`86aced9`](https://github.com/google/fonts/tree/86aced91de05cd4f96a06838124cca45be337b2b/ofl)
(6 November 2026), in `ofl/` and the folder named here; each family's `OFL.txt` is here as `OFL-<file name>.txt`.

| Files | Font | Version | By | Folder | License |
| --- | --- | --- | --- | --- | --- |
| `AbrilFatface-Regular.ttf` | Abril Fatface | 1.001 | TypeTogether | `abrilfatface` | `OFL-AbrilFatface.txt` |
| `ArchivoBlack-Regular.ttf` | Archivo Black | 1.006 | Omnibus-Type | `archivoblack` | `OFL-ArchivoBlack.txt` |
| `AtkinsonHyperlegible-Regular.ttf`, `AtkinsonHyperlegible-Bold.ttf` | Atkinson Hyperlegible | 1.006 | Braille Institute, Applied Design Works | `atkinsonhyperlegible` | `OFL-AtkinsonHyperlegible.txt` |
| `Audiowide-Regular.ttf` | Audiowide | 1.003 | Astigmatic | `audiowide` | `OFL-Audiowide.txt` |
| `Barlow-Regular.ttf`, `Barlow-Bold.ttf` | Barlow | 1.408 | Jeremy Tribby | `barlow` | `OFL-Barlow.txt` |
| `ChakraPetch-Regular.ttf`, `ChakraPetch-Bold.ttf` | Chakra Petch | 1.000 | Cadson Demak | `chakrapetch` | `OFL-ChakraPetch.txt` |
| `CourierPrime-Regular.ttf`, `CourierPrime-Bold.ttf` | Courier Prime | 3.018 | Alan Dague-Greene | `courierprime` | `OFL-CourierPrime.txt` |
| `CrimsonText-Regular.ttf`, `CrimsonText-Bold.ttf` | Crimson Text | 1.100 | Sebastian Kosch | `crimsontext` | `OFL-CrimsonText.txt` |
| `IBMPlexMono-Regular.ttf`, `IBMPlexMono-Bold.ttf` | IBM Plex Mono | 2.3 | Mike Abbink, Bold Monday | `ibmplexmono` | `OFL-IBMPlexMono.txt` |
| `Lato-Regular.ttf`, `Lato-Bold.ttf` | Lato | 2.015 | Łukasz Dziedzic | `lato` | `OFL-Lato.txt` |
| `Mali-Regular.ttf`, `Mali-Bold.ttf` | Mali | 1.000 | Cadson Demak | `mali` | `OFL-Mali.txt` |
| `Poppins-Regular.ttf`, `Poppins-Bold.ttf` | Poppins | 4.004 | Indian Type Foundry, Jonny Pinhorn, Ninad Kale | `poppins` | `OFL-Poppins.txt` |
| `Sniglet-Regular.ttf` | Sniglet | 2.000 | Haley Fiege, Brenda Gallo, Pablo Impallari | `sniglet` | `OFL-Sniglet.txt` |
| `SpaceMono-Regular.ttf`, `SpaceMono-Bold.ttf` | Space Mono | 1.003 | Colophon Foundry | `spacemono` | `OFL-SpaceMono.txt` |
| `Spectral-Regular.ttf`, `Spectral-Bold.ttf` | Spectral | 2.005 | Production Type | `spectral` | `OFL-Spectral.txt` |
| `TitilliumWeb-Regular.ttf`, `TitilliumWeb-Bold.ttf` | Titillium Web | 1.002 | Accademia di Belle Arti di Urbino | `titilliumweb` | `OFL-TitilliumWeb.txt` |

Where a deck's fonts aren't used (PowerPoint for the web replaces embedded fonts, and Keynote most likely does too),
a stand-in shows instead: so each of these fonts has one of the fonts nearly every computer has as its stand-in
(`talkgenerator.design.fonts.OPEN_FONTS`), and texts are fitted to both. Lato and Poppins are also Office cloud fonts,
which PowerPoint for the web shows.
