# Your animated profile cards

Copy this folder's contents, including `.github/`, into the public repository
`koushikrajd2011-rgb/koushikrajd2011-rgb`. The profile repository was not publicly
available during this build, so this is a ready-to-review replacement bundle.
Nothing has been pushed. The public profile, live personal site, site source,
site README, pinned repositories and project READMEs supplied the content.

## Render and preview

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python render_cards.py
python -m http.server 8000
```

Open `http://localhost:8000/cards/preview.html`. The HTML previews the same SVGs
through `<img>` tags. It is a local preview; GitHub reads README.md instead.

For a screenshot with no animation, retain your animated cards and render a
separate final-frame copy:

```sh
STATIC=1 python render_cards.py --output cards-static --no-readme
```

Open `http://localhost:8000/cards-static/preview.html` and take your screenshot.
`STATIC=1 python render_cards.py` is also supported: it writes the final frames
directly to `cards/`. Re-run `python render_cards.py` before pushing to restore
animation. On PowerShell set `$env:STATIC='1'` before running the command.

## Customize

Edit `profile.json`, then run the renderer. It contains the bio, three tile
links, featured repositories and their summaries. The six featured projects
match the profile's pinned repos at build time. Links wrap the images in the
README because links inside an SVG do not work when embedded as an image.
Each navigation image has `width="32.5%"`. The SVGs contain no JavaScript,
foreignObject, external font URLs, or external image dependencies.

To add a portrait, save a PNG/JPEG/WebP under `assets/` and set `portrait` to its
relative path, for example `assets/portrait.png`. It is embedded in the hero as
a data URI. No portrait or monogram appears by default.

The neumorphic design uses Magma Mandy-inspired charcoal, vivid pink-red,
molten yellow and crystal green. The hero places a hand-drawn straw hat with
a red band over the final D in Koushik RD. Its position is calculated from
the embedded font metrics. Set `straw_hat` to false in profile.json to hide it.
The hat is mirrored horizontally; the name stays normal. It flies in from
the left, tumbles and drifts, then lands over the D. The remaining cards
reveal after the hat lands. Reduced-motion and static modes show it at rest.
Arimo regular and bold are subset and embedded as base64 WOFF in every SVG.

`preview.html` is a self-contained animated preview using real SVG img tags.
Open it in a browser and reload to replay. `preview-static.html` shows the
final frame. These previews require no server or network connection.

## Contribution data and daily refresh

`data/contributions.json` contains one record for every UTC date from January 1
through `as_of`, including zero days. The supplied snapshot was read from
GitHub's public contribution calendar, not fabricated. The script validates
the dates and refuses incomplete, duplicate, negative or mismatched data.

The workflow runs daily at 01:17 UTC (09:17 Singapore), on manual dispatch, and
when the renderer/configuration changes on `main`. Scheduled runs use the
default branch; update the push branch filter if yours is named differently.
GitHub may delay scheduled runs and can disable schedules on inactive public
repos; a manual dispatch can restart the refresh.

The first data step calls GitHub GraphQL with the built-in `GITHUB_TOKEN`.
The second step runs the renderer. The last step commits the JSON, README,
and generated cards only when they changed. Repository Actions must allow
write permissions; branch protection must allow the bot's push. No third-party
contribution service or additional secret is required for public data. If a
repository or organization restricts the built-in token's access to the user
contribution query, use a suitable token secret in that refresh step. The
renderer preserves the last snapshot when refresh fails; the workflow stops
and reports the failure instead of committing invented zeros.

For a local refresh:

```sh
python render_cards.py --refresh
python render_cards.py
```

Monthly totals, total contributions, active days, current/longest streak, the
busiest date, and the heatmap all use that same JSON. These are contributions,
not just commits. The current month is partial. The current streak may end
yesterday while today is still in progress. Busiest-day ties choose the latest
date. Streaks are limited to the displayed calendar year. Public data may omit
private activity; the screenshot faithfully displays the stored data date.

## Animation and accessibility

Each image is self-contained. CSS keyframes reveal cards and grow bars once, with increasing delays from top to bottom. SMIL
draws the final calendar's decorative underline. There is no continuous loop.
Under `prefers-reduced-motion: reduce`, CSS animations and transitions are
disabled, final transforms/opacity are restored, and the entire SMIL layer is
hidden; the complete calendar remains visible. Static exports omit all
keyframes, animation rules and SMIL nodes entirely. Titles, descriptions and
README alt text describe the content outside the pixels.

The delays are relative to each image's load time. GitHub controls image
loading/caching, so exact synchronization across separate images is not
guaranteed. The static final state remains readable when animation is not
supported. Rendering is offline and deterministic for the same data and font
tool versions.

## Sources

- Profile and pinned projects: https://github.com/koushikrajd2011-rgb
- Live website: https://koushikrajd2011-rgb.github.io/MyPersonalSite/
- Website source and README: https://github.com/koushikrajd2011-rgb/MyPersonalSite
- Font sources: https://github.com/google/fonts/tree/main/ofl/arimo
- Contribution refresh API: https://docs.github.com/en/graphql/reference/objects#contributioncalendar
