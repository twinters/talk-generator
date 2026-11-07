"""Images for talks (docs/v5-plan.md, section 10): what a slide asks for, and how it's found.

- `licenses`: the license classes of images, and the policies that pick the classes a talk allows.
- `slots`: what a slide asks of an image (`ImageSlot`), as data rather than a call to a source.
- `profiles`: aesthetic profiles, named looks with their sources, filters and treatments, and the flavour packs.
- `analysis`: local analysis of thumbnails with Pillow: colours, brightness, grayscale, detail, a perceptual hash.
- `catalog`: the image sources as the finder sees them: their license classes and the filters they take.
- `finder`: finding the image for a slot: search, filter, score, check and pick.
"""
