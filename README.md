# It's Not Just Unicode, It's Hemi-Semi-Demicode!

Demicode is a Python command line tool to explore the current, broken state of
fixed-width rendering for [Unicode](https://home.unicode.org) in terminals.
Those same problems occur in other widely used tools, notably code editors. But
terminals support styling a program’s output with [ANSI escape
sequences](https://en.wikipedia.org/wiki/ANSI_escape_code) and hence are more
amenable to visualization.


## Introducing Fixed-Width Character Blots

At demicode’s core is the **fixed-width character blot**, which visualizes a
single grapheme’s or character's fixed-width rendering. Since the current
state-of-the-art uses two columns of the fixed-width grid at most, each blot is
three columns wide. The additional padding makes instances where theoretical and
actual width diverge glaringly obvious.

The following screenshot shows an example for **demicode's output
`--with-curation`**, which selects a select few graphemes for output, when
running in Apple's Terminal.app. Individual character blots may and do differ
when running in different terminals. For example, unlike Apple’s Terminal.app,
many other terminals get the width of the zero width space `​​` U+200B right.
Surprisingly, it really should be zero columns wide.

![Demicode's output in the default one-grapheme-per-line format and light
mode](https://raw.githubusercontent.com/apparebit/demicode/boss/docs/terminal.app.png)

To tease out the difference between expected and actual width, Demicode uses a
**clever choice of padding characters**, relying on space ` ` U+0020 with a
color different from the default background color to highlight bits of a
grapheme that are longer than they should be and on full block `█` U+2588 to
obstruct those same bits. For example, look for the quadruple integral operator
`⨌` U+2A0C or the long rightwards arrow from bar `⟼` U+27FC in the above
screenshot.

Demicode computes the **expected width of a grapheme by using the same basic
algorithm as Markus Kuhn** described in [his
implementation](https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c) of the [POSIX
extension
`wcwidth`](https://pubs.opengroup.org/onlinepubs/9699919799/functions/wcwidth.html),
except that demicode and Kuhn's implementation usually rely on different Unicode
versions. In particular, Kuhn's implementation includes inline tables for
Unicode 5.0.0. In contrast, demicode supports any version starting with 4.1.0
and downloads files from the Unicode Character Database (UCD) as needed. It
defaults to the latest version, which is 15.0.0 at the time of this writing in
August 2023.

By default, demicode displays **one grapheme per line**. Each line starts with
the background and foreground blot for a primary Unicode code point and then
continues with hopefully informative metadata:

  * The code point;
  * The number of the subsequent variation selector (if any);
  * The general category of the code point;
  * Its East Asian width;
  * Binary properties by the short aliases;
  * The age, i.e., the Unicode version that first assigned the code point;
  * The name followed by the parenthesized block.

While not all binary properties are supported, properties relating to
pictographs and emoji are included. They are `Emoji`, `Emoji_Component`,
`Emoji_Modifier`, `Emoji_Modifier_Base`, `Emoji_Presentation`, and
`Extended_Pictographic`. The short aliases are `Emoji`, `EComp`, `EMod`,
`EBase`, `EPres`, and `ExtPict`.

Demicode also supports the **more compact `--in-grid` format**, which omits all
metadata and lines up as many blots per line as window width and good taste
allow. While demicode uses absolute cursor positioning to prevent cumulative
display artifacts when theory and practice diverge, some terminals still manage
to get confused.

Since character blots only display a single grapheme at a time, **all character
blots are formatted left-to-right**, even for right-to-left scripts. My
apologies to affected Middle Eastern and Asian readers, but the benefits of a
uniform direction outweigh the benefits (and effort) for supporting both.

Demicode also **pages its output**. As stated in the hint at the bottom of the
screen, you need to press ‹return› to proceed to the next page. If you type `q`
or `quit` before pressing ‹return›, demicode exits. Pressing ‹control-c› has the
same effect.


> ## Sidebar: Unicode Terminology
>
> Character encodings are complex beasts and the language for talking about
> character encodings reflects some of that complexity. In Unicode, a *code
> point* is a number between U+0000 and U+1FFFFF inclusive. In that notation,
> the `U+` is a prefix indicating that this is a Unicode code point indeed. It
> must be followed by four to six hexadecimal digits, which provide the code
> point's numeric value.
>
> Almost all assigned Unicode code points also correspond to human-readable
> characters, such as the number sign `#` U+0023. However, some code points are
> meaningful only in combination with other code points. For example, adding
> variation selector 16 U+FE0F directly after the number sign changes its
> presentation to `#️` emoji presentation. (Your browser probably won't render
> the latter number sign differently from the former one.) Similarly, the
> combining enclosing keycap U+20E3 is not meaningful on its own, as the name
> "*combining* enclosing keycap" so clearly announces. But when we append that
> code point to the previous two, we get a keycap number sign `#️⃣` U+0023
> U+FE0F U+20E3. (Your browser better render the latest number sign
> differently from the former two.)
>
> In Unicode, a *grapheme* is a maximally long sequence of code points that
> nonetheless is an atomic unit of text. The "maximally long" ensures that when
> the three code points of the keycap number sign appear in text, the program
> processing that text doesn't ignore the second and third code point. The
> visual representation of a grapheme is a distinct concern and called a
> *glyph*. Glyphs may vary substantially, think different fonts, some of which
> may be serif and some sans-serif. But the differences in appearances do not
> change the underlying meaning.


## Theme Park

While I personally prefer light mode and am somewhat befuddled by the current
vogue of dark modes and Brandons, I also have deep respect for other people's
strongly-felt eccentricities. Hence, demicode uses the techniques described in
answers [to this StackOverflow
question](https://stackoverflow.com/questions/65294987/detect-os-dark-mode-in-python)
and by the [darkdetect
package](https://github.com/albertosottile/darkdetect/tree/master) to detect the
current mode and then defaults to that same mode. If you find that mode
detection is flaky, **`--in-dark-mode` forcibly enables demicode's dark color
theme** and **`--in-light-mode` forces  the light color theme**.

Demicode provides a second knob for **enlivening its visual presentation
`--in-more-color`**. By default, both background and foreground blots use
inoffensive shades of grey. If you prefer a little pizzazz with your Unicode
character blots, add one `--in-more-color` or two `--in-more-color
--in-more-color` for some nice yellow and orange in light mode and beautiful
purples in dark mode.

Demicode has a **slightly effusive naming convention for command line options**:

  * `--with-something` selects a pre-configured group of code points. Though you
    can always provide characters or code points in U+ notation as well.
  * `--in-something` changes the presentation of demicode's character blots.
  * `--ucd-something` controls demicode's use of the Unicode Character Database
    (UCD).

Since I find typing `--in-dark-mode` or, gasp, `--in-more-color --in-more-color`
a bit much myself, demicode also accepts **a few single letter options**,
turning the previous two incantations into `-d` and `-cc`, respectively.

The collage of screenshots below, again showing demicode's output in Apple's
Terminal.app, illustrates demicode's display themes for light and dark mode,
each with default greys, more color, and doubly more color. I do not expect to
add more themes, except I am interested in **supporting high contrast mode**.
However, high contrast mode, by design, amps up the contrast to a maximum. In
contrast (hah!), demicode's output leverages graduated contrast. If you have
some insight into overcoming this fundamental disagreement, I'd love to hear
from you.

![A collage of Demicode's output in the default one-grapheme-per-line format
showing both light and dark mode as well as increased and doubly increased
brightness](https://raw.githubusercontent.com/apparebit/demicode/boss/docs/terminal.app-mode-vs-brightness.png)


## It Ain't Pretty

While using demicode, please keep in mind that demicode's output is designed to
help you explore the interplay between Unicode code points, their Unicode
properties, and fixed-width rendering. That's why it uses ANSI escape codes for
lining up character blots. That's also why it uses ANSI escape codes for styling
many elements in its user interface. That's why it accommodates users' display
preferences. In other words, **demicode's output is designed to look calm and
pleasing**.

That is not necessarily the case when rendering very wide fixed-width characters
in real terminals. To determine **how terminals handle such text**, let's see
what happens when we display a three-em dash `⸻` U+2E3B followed immediately by
a quadruple integral operator `⨌` U+2A0C. Since Unicode classifies both code
points as having an East_Asian_Width of Neutral, every terminal I know treats
them as one column wide. But most fonts with those glyphs (six font families on
my laptop) have glyphs that are far wider than one fixed-width column.

```sh
% echo "\u2E3B\u2A0C"
```

I captured  **screenshots for the output from this trivial shell command** in
Hyper, iTerm, Kitty, Terminal.app, Visual Studio Code's terminal, Warp, and
WezTerm, using the latest version of each terminal as of this writing in August
2023. The operating system still is macOS. The results for Hyper, iTerm, Kitty,
and Terminal.app look like this:

![Collage of output from the previous echo
command](https://raw.githubusercontent.com/apparebit/demicode/boss/docs/em-integral1.png)

The results for Visual Studio Cold's terminal, Warp, and WezTerm look like this:

![Collage of output from the previous echo
command](https://raw.githubusercontent.com/apparebit/demicode/boss/docs/em-integral2.png)

Let's review the observed behavior:

  * iTerm and Terminal.app render each glyph correctly, but due to divergent
    widths they also render them fully overlapped. The result is still readable
    in this case but need not in other cases.
  * In contrast, Hyper and Visual Studio Code's terminal, which are both based
    on xterm.js, both cut off the part of glyphs sticking out past two column
    widths. That avoids potential overlap but introduces its own visual
    artifacts. I am not a fan.
  * Kitty and WezTerm try to avoid overlapping glyphs altogether by scaling wide
    glyphs down into a single column. That's a neat idea. But in practice very
    small type isn't particularly readable either, as the screenshots
    illustrate.
  * WezTerm further fails to render the three-em dash, but at least shows a
    placeholder.
  * Warp is the only standalone commercial product in this comparison and,
    ironically, does the worst. It tries to render glyphs like iTerm and
    Terminal do, but fails by dropping and flashing glyphs. The latter happened
    reliably every time I ran demicode.

In short, all terminals render fixed-width text such that code points with
divergent widths are bound to exhibit some visual artifacts. That's not a very
satisfactory state of affairs!


## Installation

Demicode is written in Python and distributed through
[PyPI](https://pypi.org/project/demicode/), the Python Packaging Index. Since it
utilizes recent language and library features, it **requires Python 3.11** or
later. You install demicode just like you install other Python code. For
example, using bash or zsh on Linux or macOS:

```sh
% python --version
Python 3.11.1
% python -m venv .venv
% source .venv/bin/activate
% pip install demicode
Collecting demicode
  Downloading demicode-0.2.0-py3-none-any.whl (18 kB)
Installing collected packages: demicode
Successfully installed demicode-0.2.0
% demicode --with-curation
```

The output of the last command should look something like the first screenshot.

When you first run demicode or request a previously unused Unicode version,
demicode needs to **download several files from the *Unicode Character Database*
(UCD)**. Depending on your location and internet connection, that may take a
moment. On subsequent runs, demicode reuses these locally mirrored files. Please
do not delete them. You can control the version and the local path used by
demicode with the `--ucd-version` and `--ucd-path` command line options. Without
them, demicode uses the latest Unicode version and mirrors files into the `ucd`
subdirectory of the current working directory.


## Demicode vs Python's unicodedata

Python makes key properties from the UCD available through the standard
library's `unicodedata` module. Demicode **does *not* use the standard library
module** for two reasons. First, the module's data is incomplete and lacks
properties needed by demicode, notably age and block of a code point. Second,
Python is limited to two versions of the UCD, 3.2 and a fairly recent version.
Furthermore, due to the release cadences of the two projects, the latter version
may just lag behind the most recent Unicode version by one or two versions.

Instead, **demicode downloads and locally mirrors necessary files from the
Unicode Character Database**. That does require a parser, but the format of the
UCD files is uniform and simple enough that parsing does not require undue
effort. The parser in `demicode.parser` is supported by lightweight classes
representing code points, ranges of code points, and sequences of code points in
`demicode.codepoint`. It is used by the higher-level `UnicodeCharacterDatabase`
class in `demicode.ucd`, which has methods for easily querying the data. In
other words, demicode already contains significant parts of a more general
package for accessing UCD data. At the same time, its code has not been
optimized and likely isn't particularly performant. Furthermore, Demicode's UCD
representation still lacks several key properties. But nonetheless, demicode may
just grow into a more general library for accessing the UCD.


## Versions

  - **v0.3.0** (2033/08/??) Expose binary emoji properties, log server accesses,
    add tests, and improve property count statistics.
  - **v0.2.0–0.2.3** (2023/08/13) First advertised release, with more robust UCD
    mirroring, more elaborate output, and support for dark mode. Alas,
    screenshot links and README still needed some TLC.
  - **v0.1.0** (2023/08/06) First, downlow release


## Etc

The **project name is a play on the name Unicode**: Fixed-width rendering of
Unicode can't get by with a single *uni*-column—from the Latin *unus* for
one—but requires at the very least a *demi*-view—from the Latin *dimidius* for
half via the French *demi* also for half. As so happens, *hemi* and *semi* mean
half as well, tracing back to Greek and Latin origin, respectively.

Alas, the real question is whether **hemisemidemi-anything is cumulative, i.e.,
<sup>1</sup>&frasl;<sub>8</sub>, or just reinforcing, i.e., still
<sup>1</sup>&frasl;<sub>2</sub>**.

I am **working on a technical blog post** to provide more on motivation,
technical background, and first findings after blotting far too many Unicode
code points. One unexpected outcome is a test that should identify the Unicode
version supported by a terminal just by displaying a bunch of emoji.  😳

I 💖 Unicode!

---

Demicode is © 2023 [Robert Grimm](https://apparebit.com) and has been released
under the Apache 2.0 license.
