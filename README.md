# It's Not Just Unicode, It's Hemi-Semi-Demicode!

Demicode is a Python command line tool to explore the current, broken state of
fixed-width rendering for [Unicode](https://home.unicode.org) in terminals and
code editors. However, because terminals support styling a program's output with
[ANSI escape sequences](https://en.wikipedia.org/wiki/ANSI_escape_code), they
also are more amenable to helpful visualization than code editors.

  - [Fixed-Width Character Blots](#fixed-width-character-blots)
  - [Features](#features)
  - [Installation](#installation)
  - [Versions](#versions)
  - [Etc](#etc)


## Fixed-Width Character Blots

Demicode's core functionality is the **fixed-width character blot**, which
visualizes a single grapheme cluster's fixed-width rendering. Since the current
state-of-the-art uses two fixed-width columns at most, each blot is one more
column, that is, three columns wide. That extra padding makes glaringly obvious
when theoretical and actual width diverge. For terminals, said padding comes in
two forms, with the first using ` ` U+0020 space in a different color to
highlight any overlap and the second using `█` U+2588 full block to obstruct
those same bits.

The following screenshot shows an example for **demicode's output
`--with-curation`** when running in Terminal.app on macOS. Out of the seven
terminals I have been testing—[Hyper](https://hyper.is),
[iTerm2](https://iterm2.com), [Kitty](https://sw.kovidgoyal.net/kitty/),
[Terminal.app](https://en.wikipedia.org/wiki/Terminal_(macOS)), [Visual Studio
Code's terminal](https://code.visualstudio.com/docs/terminal/basics),
[Warp](https://www.warp.dev), and
[wezTerm](https://wezfurlong.org/wezterm/index.html)—it generates middling
output: I find Terminal.app's and iTerm2's handling of overly wide glyphs the
least bad. However, even with demicode using ANSI escape codes to line up
columns, Terminal.app still manages to distort the column grid, as the lines for
the technologist, person: red hair, and rainbow flag emoji in the screenshot
below illustrate. I haven't found an effective work-around, despite trying
several alternatives such as rendering character information first and blots
second.


![Demicode's output in the default one-grapheme-per-line format and light
mode](https://raw.githubusercontent.com/apparebit/demicode/boss/docs/terminal.app.png)


## Features

Demicode supports the following features:

  * Display fixed-width **character blots together with helpful metadata** one
    grapheme per line.
  * Or, **display `--in-grid`/`-g`** to fit many more graphemes into the same
    window, albeit without metadata.
  * For code points that combine with variation selectors, **automatically show
    the code point without and with applicable variation selectors**.
  * Optionally **display blots `--in-more-color`/`-c` and
    `--in-dark-mode`/`-d`**. The first option may be given twice for even more
    color. The second option usually is superfluous because demicode
    automatically detects dark mode. See screenshot below.
  * Run `--with-curation` and `--with-…` other **carefully selected groups of
    graphemes**. Or provide your own graphemes as regular command line
    arguments. Both literal strings and Unicode's `U+…` notation are acceptable.
    Quote several `U+…` forms to group them into a grapheme.
  * **Automatically download necessary files** from the [Unicode Character
    Database](https://unicode.org/ucd/) (UCD) and [Common Locale Data
    Repository](https://cldr.unicode.org/) (CLDR) and then cache them locally.
  * **Automatically detect the most recent version of the UCD and the CLDR**.
    Since CLDR data serves one, non-normative purpose only, emoji sequence
    names, demicode always utilizes the latest version. But `--ucd-version` lets
    you pick older UCD versions at will.
  * In interactive mode, **page the output**. Let user control whether to **go
    backward or forward** while also **automatically adjusting to terminal
    window size**.
  * On Linux and macOS, **page backward and forward with the left and right
    arrow keys**. On other operating systems, use `b` or `p` followed by
    `‹return›` to page backward; just `‹return›` or alternatively `f` or `n`
    followed by `‹return›` to page forward; and just `‹control-c›` or
    alternatively `q` or `x` followed by `‹return›` to terminate demicode. All
    of these, no `‹return›` required, work on Linux and macOS, too. Plus
    `‹delete›` or `‹shift-tab›` to page backward; `‹space›` or `‹tab›` to page
    forward; and `‹escape›` to terminate. So which triple is yours?
  * In batch mode, i.e., with standard in or out redirected, **emit all
    character blots at once and consecutively**.


![Demicode's themes for light and dark mode and with more colors and doubly more
colors](https://raw.githubusercontent.com/apparebit/demicode/boss/docs/terminal.app-mode-vs-brightness.png)


## Installation

Demicode is written in Python and distributed through
[PyPI](https://pypi.org/project/demicode/), the Python Packaging Index. Since it
utilizes recent language and library features, it **requires Python 3.11** or
later. The best option for installing demicode is using
[pipx](https://pypa.github.io/pipx/). If you haven't installed `pipx` yet,
`brew` makes that easy on Linux or macOS:

```sh
% brew install pipx
==> Fetching pipx
==> Downloading https://ghcr.io/v2/homebrew/core/pipx/manifests/1.2.0
...
🍺  /usr/local/Cellar/pipx/1.2.0: 885 files, 11.2MB
==> Running `brew cleanup pipx`...
Disable this behavior by setting HOMEBREW_NO_INSTALL_CLEANUP.
Hide these hints with HOMEBREW_NO_ENV_HINTS (see `man brew`).
%
```

Once you have `pipx` installed, installing `demicode` is trivial:

```sh
% python --version
Python 3.11.1
% pipx install demicode
  installed package demicode 0.5.0, installed using Python 3.11.5
  These apps are now globally available
    - demicode
done! ✨ 🌟 ✨
% demicode --with-curation
...
```

The output of the last command should look something like the first screenshot.


## Versions

  - **v0.8.0** (2023/09/12):
      - In interactive mode, render every page from scratch, taking terminal
        size into account. This enables paging forward *and* backward. On Linux
        and macOS, use left and right arrow keys to control paging.
      - In batch mode, i.e., when standard input or output are redirected, emit
        all character blots without paging.
      - Test file loading and property look up for  every supported UCD version
        to squash any remaining crashing bugs. Nonetheless, advise in tool help
        that default, i.e., latest version produces best results.
      - In preparation of Unicode 15.1, add support for the
        Canonical_Combining_Class, Indic_Syllabic_Category, and Script
        properties. Remove support for unused Dash, Noncharacter_Code_Point,
        Variation_Selector, and White_Space properties again.
      - Clean up UCD file loading. Eliminate most boilerplate and private helper
        functions in `demicode.ucd`.
      - Eliminate global instance of `UnicodeCharacterDatabase`. Leverage
        independent instance for collecting statistics, eliminating need for two
        tool runs to collect all data.
  - **v0.7.0** (2023/09/06) Clearly distinguish between user errors and
    unexpected exceptions; print traceback only for the latter. Modularize test
    script using `unittest`. In preparation of Unicode 15.1, specify which
    versions to use for code generation.
  - **v0.6.0** (2023/09/05) Fix handling of emoji data for early versions of
    Unicode. Suppress blot for unassigned code points or sequences that are more
    than one grapheme cluster; add explanatory note.
  - **v0.5.0** (2023/09/04) Optimize range-based Unicode data for space and
    bisection speed. Improve built-in selections of graphemes; notably, the
    Unicode version oracle now displays exactly one emoji per detectable Unicode
    version.
  - **v0.4.0** (2023/09/01) Fix bug in URL creation for UCD files and move local
    cache to the OS-specific application cache directory. Restructure and
    simplify code to compute `width()`, renamed from `wcwidth()` due to changes.
  - **v0.3.0** (2023/09/01) Add support for grapheme clusters in addition to
    individual code points; account for emoji when calculating width; expose
    binary emoji properties; log server accesses; add tests; and improve
    property count statistics.
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
