"""Design: themes and layouts (docs/v5-plan.md, section 9).

A layout is geometry only: named boxes on a 1920×1080 canvas. A theme is design tokens: colours, fonts, a
background, decoration. The layout engine (`talkgenerator.design.engine`) puts a deck's elements in their layout's
boxes, in the theme's style, at font sizes at which the texts fit: so a deck holds positioned elements, which every
renderer draws the same way (the PowerPoint renderer, previews, later the browser view).

The classic theme is the 2019 template, which the classic renderer fills as before; every other theme is drawn as
shapes on blank slides.
"""
