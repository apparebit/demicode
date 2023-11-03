#!/usr/bin/env bash

# See https://imagemagick.org/Usage/crop/#trim_noisy

size_image() {
    magick $1 -fuzz 1% -trim -bordercolor white -border 10 \
        -format '%wx%h+%[fx:page.x-10]+%[fx:page.y-10]' info:
}

magick $1 -crop `size_image $1` +repage meh-${1#term-}
