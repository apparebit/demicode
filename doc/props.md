# Computing the Width of Text

To determine the width of a string for fixed-width display, the implementation
needs to break the text into extended grapheme clusters and then determine the
width of each grapheme cluster.


## Grapheme Cluster Breaks

To determine extended grapheme clusters according to Unicode 15.0, the
implementation requires access to the following Unicode properties:

  * `Extended_Pictographic`
  * `Grapheme_Cluster_Break`

For Unicode 15.1, it additionally requires access to the following properties:

  * `Canonical_Combining_Class`
  * `Indic_Syllabic_Category`
  * `Script`

However, if the previous three properties aren't otherwise needed, Unicode 15.1
also defines a more lightweight derived property:

  * `Indic_Conjunct_Break`


## Widths

Computing the width of grapheme clusters requires access to the following
properties:

  * `East_Asian_Width`
  * `General_Category`

The implementation currently uses `Emoji_Sequence`, i.e., an enumeration of all
emoji sequences recommended for general interchange to determine which grapheme
clusters are emoji. That should be replaced with the following property:

  * `Emoji_Presentation`

Notably, if an extended pictographic grapheme cluster includes a character with
emoji presentation or the emoji variation selector U+FE0F, then it should be
treated as a double-width grapheme cluster.


## Taken Together

Taken together, the following properties are required for Unicode 15.1:

  * `Canonical_Combining_Class`
  * `East_Asian_Width`
  * `Emoji_Presentation`
  * `Extended_Pictographic`
  * `General_Category`
  * `Grapheme_Cluster_Break`
  * `Indic_Syllabic_Category`
  * `Script`

Or preferably:

  * `East_Asian_Width`
  * `Emoji_Presentation`
  * `Extended_Pictographic`
  * `General_Category`
  * `Grapheme_Cluster_Break`
  * `Indic_Conjunct_Break`

With the `--stats` option, demicode prints statistics for both sets.
