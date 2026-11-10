from __future__ import annotations

import argparse
import base64
import calendar
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import html
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ACCENT, INK, SLATE = "#ff2867", "#fff3e8", "#c7bec5"
SURFACE = "#302b31"
E = lambda value: html.escape(str(value), quote=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def refresh(config, destination, today=None):

    today = today or datetime.now(timezone.utc).date()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("--refresh requires GH_TOKEN or GITHUB_TOKEN; ordinary rendering is offline")
    query = """query($login:String!, $from:DateTime!, $to:DateTime!) {
      user(login:$login) { login contributionsCollection(from:$from,to:$to) {
        contributionCalendar { totalContributions weeks {
          contributionDays { date contributionCount }
        } }
      } }
    }"""
    payload = {"query": query, "variables": {
        "login": config["username"],
        "from": f"{today.year}-01-01T00:00:00Z", "to": f"{today.isoformat()}T23:59:59Z"}}
    request = Request("https://api.github.com/graphql", data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
        "User-Agent": "profile-svg-cards", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=45) as response:
        result = json.load(response)
    if result.get("errors") or not result.get("data", {}).get("user"):
        raise ValueError("GitHub GraphQL did not return contribution data: " +
                         json.dumps(result.get("errors", [])))
    user = result["data"]["user"]
    if user["login"].lower() != config["username"].lower():
        raise ValueError("Contribution response belongs to another user")
    graph = user["contributionsCollection"]["contributionCalendar"]
    data = {"username": config["username"], "as_of": today.isoformat(),
            "from": f"{today.year}-01-01", "source": "GitHub GraphQL contributionCalendar (UTC)",
            "days": [{"date": day["date"], "count": day["contributionCount"]}
                     for week in graph["weeks"] for day in week["contributionDays"]]}
    days = validate(data, config["username"])
    if sum(d["count"] for d in days) != graph["totalContributions"]:
        raise ValueError("Calendar total differs from daily counts; previous JSON preserved")
    data["days"] = days
    write_json(destination, data)
    print(f"Refreshed {len(days)} days in {destination}")


def validate(data, username):

    if data["username"].lower() != username.lower():
        raise ValueError("JSON username does not match profile.json")
    start, end = date.fromisoformat(data["from"]), date.fromisoformat(data["as_of"])
    if start != date(end.year, 1, 1) or end < start:
        raise ValueError("Expected a current-year calendar from January 1 through as_of")
    days = data["days"]
    found = {}
    for day in days:
        current, count = date.fromisoformat(day["date"]), day["count"]
        if current in found or type(count) is not int or count < 0 or not start <= current <= end:
            raise ValueError("Invalid count, duplicate, or out-of-range calendar date")
        found[current] = count
    expected = (end - start).days + 1
    if len(found) != expected:
        raise ValueError(f"Calendar is incomplete: expected {expected} days, found {len(found)}")
    return [{"date": d.isoformat(), "count": found[d]} for d in sorted(found)]


def statistics(days):
    months = Counter()
    longest = running = 0
    for day in days:
        months[day["date"][:7]] += day["count"]
        running = running + 1 if day["count"] else 0
        longest = max(longest, running)

    index = len(days) - 1
    if index >= 0 and days[index]["count"] == 0:
        index -= 1
    streak = 0
    while index >= 0 and days[index]["count"] > 0:
        streak += 1
        index -= 1
    busiest = max(days, key=lambda d: (d["count"], d["date"]))
    return {"total": sum(d["count"] for d in days), "active": sum(d["count"] > 0 for d in days),
            "streak": streak, "longest": longest, "busiest": busiest, "months": dict(sorted(months.items()))}


def text(x, y, value, size=18, color=INK, cls="", **attrs):
    extra = " ".join(f'{k.replace("_", "-")}="{E(v)}"' for k, v in attrs.items())
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" class="{cls}" {extra}>{E(value)}</text>'


def label(x, y, value, color=SLATE):
    return text(x, y, value, 12, color, "label", letter_spacing="2", font_weight="700")


def arrow(x, y, color=ACCENT, scale=1):
    return (f'<g transform="translate({x} {y}) scale({scale})" fill="none" stroke="{color}" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M0 16 16 0M0 0h16v16"/></g>')


def well(x, y, width, height, radius=18):
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{SURFACE}" filter="url(#inset)"/>'


def glyph(kind, x, y, color=ACCENT, size=24):
    paths = {
        "web": '<rect x="2" y="3" width="20" height="18" rx="3"/><path d="M2 8h20M6 5.5h.1m3 0h.1"/>',
        "code": '<path d="m8 5-6 7 6 7m8-14 6 7-6 7M14 2l-4 20"/>',
        "os": '<rect x="1" y="2" width="22" height="16" rx="3"/><path d="M8 22h8m-4-4v4"/>',
        "hardware": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/>',
        "sketch": '<path d="m4 17 13-13 4 4L8 21H4Zm10-10 4 4M4 17l4 4"/>',
    }
    return (f'<g transform="translate({x} {y}) scale({size/24})" fill="none" stroke="{color}" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{paths[kind]}</g>')


def button(cx, cy, radius=24):
    return f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{SURFACE}" filter="url(#button)"/>'


def straw_hat(cx, cy):

    return (f'<g transform="translate({cx:.2f} {cy:.2f})"><g class="hat"><g transform="rotate(12) scale(-.6 .6)">'
            '<ellipse cx="0" cy="2" rx="47" ry="10" fill="#d9a64d" stroke="#8c5d28" stroke-width="1.4"/>'
            '<ellipse cx="0" cy="0" rx="47" ry="8" fill="#edc778" stroke="#a77833" stroke-width="1"/>'
            '<path d="M-28-4Q-29-35 0-35Q29-35 28-4Q0 5-28-4Z" fill="#efc976" stroke="#a77833" stroke-width="1.3"/>'
            '<path d="M-27-13Q0-6 27-13L28-5Q0 4-28-5Z" fill="#c73536" stroke="#a7282b" stroke-width=".8"/>'
            '<path d="M-19-25Q0-30 19-25M-23-19Q0-24 23-19M-39 1Q0 10 39 1" stroke="#bd934e" stroke-width=".9" fill="none"/>'
            '<path d="m-15-31-3 9m17-12v10m17-7 3 9M-34-3l-2 7m15-4-1 6m44-6 1 6m12-9 2 7" stroke="#cda659" stroke-width=".7"/>'
            '</g></g></g>')


class Renderer:
    def __init__(self, config, output, static):
        self.config, self.output, self.static = config, output, static
        self.fonts = {}
        self.cards = []
        self.temp = tempfile.TemporaryDirectory(prefix="profile-fonts-")
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
        for family, filename, weight in [("Display", "Arimo.ttf", 700), ("Body", "Arimo.ttf", 400)]:
            source = ROOT / "assets/fonts" / filename
            font = TTFont(source)
            if "fvar" in font:
                axes = {axis.axisTag: weight if axis.axisTag == "wght" else axis.defaultValue
                        for axis in font["fvar"].axes}
                font = instantiateVariableFont(font, axes, inplace=True)
            font.recalcTimestamp = False
            dest = Path(self.temp.name) / (family + ".ttf")
            font.save(dest)
            self.fonts[family] = dest

    def font_css(self, body):
        glyphs = "".join(ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>').itertext())
        glyph_path = Path(self.temp.name) / "glyphs.txt"
        glyph_path.write_text(glyphs, encoding="utf-8")
        css = []

        cli = [shutil.which("pyftsubset")] if shutil.which("pyftsubset") else [sys.executable, "-m", "fontTools.subset"]
        for family, source in self.fonts.items():
            target = Path(self.temp.name) / (family + ".woff")
            subprocess.run(cli + [str(source), f"--text-file={glyph_path}", f"--output-file={target}",
                           "--flavor=woff", "--no-recalc-timestamp", "--canonical-order"], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            encoded = base64.b64encode(target.read_bytes()).decode()
            css.append(f"@font-face{{font-family:{family};src:url(data:font/woff;base64,{encoded}) format('woff');font-weight:400 800;font-display:block}}")
        return "".join(css)

    def write(self, filename, height, body, title, description, delay=0, width=1000):
        css = self.font_css(body)
        css += "text{font-family:Body,Arial,sans-serif}.display{font-family:Display,Arial,sans-serif}.heavy{font-weight:700}"
        if not self.static:
            css += f"""
@keyframes arrive{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes hatSwish{{
 0%{{opacity:0;transform:translate(-500px,15px) rotate(-500deg) scale(.8,.35)}}
 12%{{opacity:1;transform:translate(-385px,-28px) rotate(-380deg) scale(1,.8)}}
 34%{{opacity:1;transform:translate(-235px,-48px) rotate(-210deg) scale(1.15,.28)}}
 55%{{opacity:1;transform:translate(-100px,-30px) rotate(-90deg) scale(1,.95)}}
 73%{{opacity:1;transform:translate(35px,-42px) rotate(30deg) scale(1,.55)}}
 88%{{opacity:1;transform:translate(8px,-18px) rotate(-12deg) scale(1,.95)}}
 96%{{opacity:1;transform:translate(-1px,-3px) rotate(4deg) scale(1)}}
 100%{{opacity:1;transform:translate(0,0) rotate(0) scale(1)}}
}}
@keyframes windSwish{{0%{{opacity:0;transform:translateX(-100px)}}25%{{opacity:.25}}65%{{opacity:.16}}100%{{opacity:0;transform:translateX(160px)}}}}
.wind{{opacity:0}}

@keyframes grow{{from{{transform:scaleY(.02);opacity:.2}}to{{transform:scaleY(1);opacity:1}}}}
@media(prefers-reduced-motion:no-preference){{
 .wind{{animation:windSwish 2.6s ease .1s both}}
 .hat{{transform-box:fill-box;transform-origin:center bottom;animation:hatSwish 2.8s cubic-bezier(.38,.05,.4,1) .1s both}}
 .reveal{{animation:arrive .65s cubic-bezier(.2,.7,.2,1) {delay}s both}}
 .late{{animation:arrive .65s ease {delay+.18:.2f}s both}}
 .bar{{transform-box:fill-box;transform-origin:center bottom;animation:grow .9s cubic-bezier(.2,.7,.2,1) calc({delay}s + var(--i,0)*.055s) both}}
}}
@media(prefers-reduced-motion:reduce){{
 *,*::before,*::after{{animation:none!important;transition:none!important}}
 .reveal,.late,.bar,.hat{{opacity:1!important;transform:none!important}}
 .smil-motion,.wind{{display:none!important;opacity:0!important}}
}}
"""
        else:

            body = re.sub(r'<g class="smil-motion">.*?</g>', '', body, flags=re.S)
        bg = SURFACE
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
               f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
               'aria-labelledby="title description">'
               f'<title id="title">{E(title)}</title><desc id="description">{E(description)}</desc>'
               f'<defs><style><![CDATA[{css}]]></style>'
               '<linearGradient id="magma" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#ffc51b"/><stop offset="1" stop-color="#ff2867"/></linearGradient>'
               '<filter id="raised" x="-25%" y="-50%" width="150%" height="200%" color-interpolation-filters="sRGB">'
               '<feDropShadow dx="7" dy="7" stdDeviation="7" flood-color="#171319" flood-opacity=".85"/>'
               '<feDropShadow dx="-7" dy="-7" stdDeviation="7" flood-color="#433740" flood-opacity=".38"/></filter>'
               '<filter id="button" x="-60%" y="-60%" width="220%" height="220%" color-interpolation-filters="sRGB">'
               '<feDropShadow dx="4" dy="4" stdDeviation="4" flood-color="#171319" flood-opacity=".85"/>'
               '<feDropShadow dx="-4" dy="-4" stdDeviation="4" flood-color="#433740" flood-opacity=".38"/></filter>'
               '<filter id="inset" x="-20%" y="-40%" width="140%" height="180%" color-interpolation-filters="sRGB">'
               '<feComponentTransfer in="SourceAlpha" result="inverse"><feFuncA type="table" tableValues="1 0"/></feComponentTransfer>'
               '<feGaussianBlur in="inverse" stdDeviation="4" result="blur"/>'
               '<feOffset in="blur" dx="4" dy="4" result="dark"/>'
               '<feComposite in="dark" in2="SourceAlpha" operator="in" result="dark-mask"/>'
               '<feFlood flood-color="#17151b" flood-opacity=".7" result="dark-color"/>'
               '<feComposite in="dark-color" in2="dark-mask" operator="in" result="inner-dark"/>'
               '<feOffset in="blur" dx="-4" dy="-4" result="light"/>'
               '<feComposite in="light" in2="SourceAlpha" operator="in" result="light-mask"/>'
               '<feFlood flood-color="#433740" flood-opacity=".38" result="light-color"/>'
               '<feComposite in="light-color" in2="light-mask" operator="in" result="inner-light"/>'
               '<feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="inner-dark"/><feMergeNode in="inner-light"/></feMerge></filter>'
               '</defs>'
               f'<rect width="{width}" height="{height}" fill="{bg}"/>'
               f'<rect x="16" y="16" width="{width-32}" height="{height-32}" rx="28" fill="{bg}" filter="url(#raised)"/>'
               f'{body}</svg>')
        ET.fromstring(svg)
        self.output.mkdir(parents=True, exist_ok=True)
        (self.output / filename).write_text(svg + "\n", encoding="utf-8")
        self.cards.append(filename)

    def hero(self):
        c = self.config
        body = ''
        if not self.static:
            body += ('<g class="wind" fill="none" stroke="#c7bec5" stroke-width="1.2" stroke-linecap="round">'
                     '<path d="M-60 77C10 33 78 70 145 47M-30 102C45 57 118 91 190 64M8 120Q74 93 133 101"/></g>')
        body += '<g class="reveal">' + text(48, 58, '@' + c["username"], 14, SLATE)
        body += text(45, 137, c["name"], 64, INK, "display")
        if c.get("straw_hat", True) and c["name"].endswith("D"):
            from fontTools.ttLib import TTFont
            font = TTFont(self.fonts["Display"])
            cmap, metrics, units = font.getBestCmap(), font["hmtx"].metrics, font["head"].unitsPerEm
            before = sum(metrics[cmap[ord(char)]][0] for char in c["name"][:-1])
            center = 45 + 64 * (before + metrics[cmap[ord("D")]][0]/2) / units
            cap_top = 137 - 64 * font["OS/2"].sCapHeight / units
            body += straw_hat(center + 7, cap_top - 1)

        body += text(48, 183, c["tagline"], 20, SLATE)
        body += '<path d="M48 218h44" stroke="#ff2867" stroke-width="3" stroke-linecap="round"/></g>'
        body += '<g class="late">' + well(727, 47, 211, 189, 32)
        if c.get("portrait"):
            path = (ROOT / c["portrait"]).resolve()
            mime = {".png":"image/png", ".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".webp":"image/webp"}.get(path.suffix.lower())
            if not mime:
                raise ValueError("portrait must be a local PNG, JPEG, or WebP")
            encoded = base64.b64encode(path.read_bytes()).decode()
            body += '<defs><clipPath id="portrait"><circle cx="832" cy="141" r="76"/></clipPath></defs>'
            body += f'<image x="756" y="65" width="152" height="152" preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait)" href="data:{mime};base64,{encoded}"/>'
        else:
            body += button(832, 141, 61) + glyph("code", 801, 110, "#ffc51b", 62)
            body += button(731, 207, 23) + glyph("hardware", 719, 195, "#9bf23b")
            body += button(929, 63, 23) + glyph("sketch", 917, 51, "#ffc51b")
        body += '</g>'
        self.write("01-hero.svg",284,body,c["name"],c["tagline"],0)

    def tiles(self):
        for index, tile in enumerate(self.config["tiles"]):
            color = tile["color"]
            body = '<g class="reveal">' + button(55, 55, 22)
            body += glyph(["web", "code", "os"][index],43,43,color)
            body += text(36,118,tile["title"],22,INK,"display")
            body += arrow(264,103,color,.65) + '</g>'
            self.write(f'02-tile-{index+1}.svg',156,body,tile["title"],tile["title"],3.1+index*.13,width=320)

    def activity(self, data, stats):
        year = data["as_of"][:4]
        body = '<g class="reveal">' + text(48,62,"Contributions",30,INK,"display")
        body += text(48,87,year,14,SLATE)
        body += text(946,65,f'{stats["total"]:,}',42,ACCENT,"display",text_anchor="end")
        body += text(946,88,"total",12,SLATE,text_anchor="end") + '</g>'
        body += well(48,113,904,198,22)
        baseline, max_height = 268, 108
        maximum = max(1, *stats["months"].values())
        ceiling = max(5, int((maximum+4)//5)*5)
        for tick in [0, ceiling//2, ceiling]:
            y = baseline - tick/ceiling*max_height
            body += f'<path d="M92 {y:.2f}H922" stroke="#484048" stroke-dasharray="3 6"/>'
            body += text(80,y+4,tick,11,SLATE,text_anchor="end")
        months = list(stats["months"].items())
        step = 824/len(months)
        for i,(month,count) in enumerate(months):
            x,bw = 96+i*step+step*.12,min(48,step*.62)
            bh = count/ceiling*max_height
            body += f'<g class="bar" style="--i:{i}"><rect x="{x:.2f}" y="{baseline-bh:.2f}" width="{bw:.2f}" height="{bh:.2f}" rx="6" fill="url(#magma)"/></g>'
            body += text(x+bw/2,baseline-bh-9,str(count),12,ACCENT,text_anchor="middle",font_weight="700")
            body += text(x+bw/2,292,calendar.month_abbr[int(month[-2:])],12,SLATE,text_anchor="middle")
        busiest = stats["busiest"]
        busiest_label = date.fromisoformat(busiest["date"]).strftime("%d %b").lstrip("0") if busiest["count"] else "—"
        metrics = [(f'{stats["streak"]} days',"CURRENT STREAK"),(str(stats["active"]),"ACTIVE DAYS"),
                   (f'{stats["longest"]} days',"LONGEST STREAK"),(busiest_label,"BUSIEST DAY")]
        body += '<g class="late">'
        for i,(value,name) in enumerate(metrics):
            x = 48+i*232
            body += well(x,336,208,104,18)
            body += text(x+19,378,value,29,[ACCENT,"#ffc51b","#ff7945","#9bf23b"][i],"display")
            body += text(x+19,411,name,10,SLATE,letter_spacing="1.3",font_weight="700")
        body += text(48,467,f'UTC · {data["as_of"]} · current month is partial',11,SLATE)
        body += text(946,467,f'Busiest day: {busiest["count"]} contributions',11,SLATE,text_anchor="end") + '</g>'
        self.write("03-activity.svg",494,body,"Contributions by month",json.dumps(stats,ensure_ascii=False),3.6)

    def repository(self, repo, index):
        accent = repo["color"]
        body = '<g class="reveal">' + text(48,63,repo["name"],30,INK,"display")
        for j,line in enumerate(textwrap.wrap(repo["description"],width=77)):
            body += text(48,98+j*23,line,17,SLATE)
        body += f'<circle cx="52" cy="124" r="3" fill="{accent}"/>'
        body += text(63,129,repo["language"],12,SLATE) + '</g>'
        body += '<g class="late">' + button(925,78,26) + arrow(919,72,accent,.75) + '</g>'
        self.write(f'04-repo-{index+1:02}-{repo["name"].lower()}.svg',168,body,repo["name"],repo["description"],4.0+index*.32)

    def graph(self, data, stats):
        days = data["days"]
        start = date.fromisoformat(data["from"])
        offset = (start.weekday()+1)%7
        cell,pitch,left,top = 12,16.3,84,135
        body = '<g class="reveal">' + text(48,65,"Contribution graph",28,INK,"display")
        body += text(946,63,str(stats["total"])+" contributions",15,SLATE,text_anchor="end") + '</g>'
        body += well(48,91,904,179,22)
        first_seen = set()
        maximum = max(1,*[d["count"] for d in days])
        colors = ["#43353d","#702c48","#a82554","#dc235b",ACCENT]
        body += '<g class="late">'
        for i,day in enumerate(days):
            d = date.fromisoformat(day["date"])
            col,row = divmod(i+offset,7)
            x,y = left+col*pitch,top+row*pitch
            if d.month not in first_seen:
                first_seen.add(d.month)
                body += text(x,120,calendar.month_abbr[d.month],11,SLATE)
            level = 0 if not day["count"] else min(4,1+(day["count"]-1)*4//maximum)
            body += f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell}" height="{cell}" rx="3" fill="{colors[level]}"><title>{day["date"]}: {day["count"]} contributions</title></rect>'
        for row,name in [(1,"M"),(3,"W"),(5,"F")]:
            body += text(63,top+row*pitch+10,name,10,SLATE)
        body += text(48,303,f'{data["from"]} — {data["as_of"]} · UTC',12,SLATE)
        body += text(799,303,"Less",11,SLATE,text_anchor="end")
        for i,color in enumerate(colors):
            body += f'<rect x="{811+i*19}" y="292" width="13" height="13" rx="3" fill="{color}"/>'
        body += text(946,303,"More",11,SLATE,text_anchor="end") + '</g>'
        if not self.static:
            delay = 4.4+len(self.config["featured"])*.32
            body += ('<g class="smil-motion"><path d="M48 321H952" fill="none" stroke="#ffc51b" stroke-width="1.5" '
                     'stroke-dasharray="904" stroke-dashoffset="0">'
                     f'<animate attributeName="stroke-dashoffset" from="904" to="0" begin="{delay:.2f}s" dur="1.1s" fill="freeze"/>'
                     '</path></g>')
        self.write("05-contribution-graph.svg",348,body,"Contribution graph",f'{stats["total"]} contributions across {stats["active"]} active days. {data["from"]} through {data["as_of"]}.',4.4+len(self.config["featured"])*.32)

    def documents(self, data, stats, write_readme):
        c = self.config
        folder = os.path.relpath(self.output,ROOT).replace(os.sep,"/")
        def img(filename, alt, width="100%"):
            return f'<img src="{E(folder)}/{filename}" alt="{E(alt)}" width="{width}">'
        blocks = [img("01-hero.svg",f'{c["name"]} — {c["tagline"]}')]
        tiles = []
        for i,tile in enumerate(c["tiles"]):
            tiles.append(f'<a href="{E(tile["url"])}">'+img(f'02-tile-{i+1}.svg',tile["title"],"32.5%")+'</a>')
        blocks.append('<p>'+''.join(tiles)+'</p>')
        b = stats["busiest"]
        blocks.append(img("03-activity.svg",f'{stats["total"]} contributions; current streak {stats["streak"]} days; {stats["active"]} active days; longest streak {stats["longest"]} days; busiest day {b["date"]}: {b["count"]} contributions.'))
        for i,repo in enumerate(c["featured"]):
            filename = f'04-repo-{i+1:02}-{repo["name"].lower()}.svg'
            blocks.append(f'<a href="{E(repo["url"])}">'+img(filename,repo["name"]+" — "+repo["description"])+"</a>")
        blocks.append(img("05-contribution-graph.svg",f'{data["as_of"][:4]} contribution graph in the Magma Mandy palette; {stats["total"]} contributions through {data["as_of"]}.'))
        blocks.append(f'<sub>Updated {data["as_of"]} · GitHub contributions · UTC · <a href="{E(c["website"])}">Visit my website</a></sub>')
        if write_readme:
            sections = list(blocks[:-1])
            sections[1] = ''.join(tiles)
            markup = '<p align="center">' + '<br>'.join(sections) + '</p>\n\n' + blocks[-1] + '\n'
            (ROOT/"README.md").write_text(markup,encoding="utf-8")
        preview = '\n'.join(blocks)

        for card in self.output.glob("*.svg"):
            version = hashlib.sha256(card.read_bytes()).hexdigest()[:12]
            preview = preview.replace(f'/{card.name}"', f'/{card.name}?v={version}"')
        document = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(c["name"])} / profile preview</title>
<style>body{{margin:0;padding:32px 16px;background:#302b31;color:#fff3e8;font:14px Arial,sans-serif}}main{{max-width:1000px;margin:auto}}img{{display:block;height:auto;max-width:100%}}p{{display:flex;gap:1.25%;margin:0}}p a{{display:contents}}p img{{width:32.5%}}main>a,main>img{{display:block;margin:0}}sub{{display:block;text-align:center;margin:24px}}a{{color:#ff2867}}@media(max-width:600px){{body{{padding:10px 5px}}}}</style>
<main>{preview.replace(E(folder)+"/", "")}</main></html>'''
        (self.output/"preview.html").write_text(document,encoding="utf-8")
        def embed(match):
            filename = match.group(1)
            encoded = base64.b64encode((self.output/filename).read_bytes()).decode()
            return f'src="data:image/svg+xml;base64,{encoded}"'
        standalone = re.sub(r'src="([^"/]+\.svg)\?v=[^"]+"',embed,document)
        name = "preview-static.html" if self.static else "preview.html"
        (ROOT/name).write_text(standalone,encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh",action="store_true",help="refresh JSON from GitHub GraphQL, then exit")
    parser.add_argument("--data",type=Path,default=ROOT/"data/contributions.json")
    parser.add_argument("--output",type=Path,default=ROOT/"cards")
    parser.add_argument("--no-readme",action="store_true",help="keep README unchanged for separate previews")
    args = parser.parse_args()
    config = read_json(ROOT/"profile.json")
    if args.refresh:
        refresh(config,args.data)
        return
    data = read_json(args.data)
    data["days"] = validate(data,config["username"])
    stats = statistics(data["days"])
    renderer = Renderer(config,args.output.resolve(),os.environ.get("STATIC")=="1")
    try:
        renderer.hero()
        renderer.tiles()
        renderer.activity(data,stats)
        for index,repo in enumerate(config["featured"]):
            renderer.repository(repo,index)
        renderer.graph(data,stats)
        renderer.documents(data,stats,not args.no_readme)

        for path in renderer.output.glob("*.svg"):
            if re.match(r"0[1-5]-",path.name) and path.name not in renderer.cards:
                path.unlink()
        print(f'Rendered {len(renderer.cards)} {"static" if renderer.static else "animated"} cards in {renderer.output}')
    finally:
        renderer.temp.cleanup()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError) as error:
        sys.exit(f"Error: {error}")
