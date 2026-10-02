"""Record today's episode, prune old ones, and render the podcast feed + web page into _site/.

Env: EP_DATE (YYYY-MM-DD), EP_TAG (release tag), MP3_FILE, SITE_URL.
MP3s are stored as release assets and served from Pages under audio/ (see daily.yml).
Writes out/prune_tags.txt with release tags of episodes that dropped out of the window.
data/deals.json is the permanent deal tracker (never pruned).
"""
import datetime as dt
import html
import json
import os
import shutil
from email.utils import format_datetime
from pathlib import Path

from mutagen.mp3 import MP3

CONFIG = json.load(open("config.json"))
EPISODES = Path("data/episodes.json")
COVERAGE = Path("data/coverage.json")
DEALS = Path("data/deals.json")
OUTCOMES = {"blocked": "Blocked", "conditions": "Conditions", "withdrawn": "Withdrawn",
            "divestment": "Divestment", "pending": "Pending"}
SITE = Path("_site")


def load(path: Path) -> list:
    return json.loads(path.read_text())


def save(path: Path, data: list) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def record_episode(date: str) -> None:
    ep = json.loads(Path("out/episode.json").read_text())
    mp3 = Path("out/episode.mp3")
    published = dt.datetime.now(dt.timezone.utc)
    record = {
        "date": date,
        "tag": os.environ["EP_TAG"],
        "title": ep["title"],
        "summary": ep["summary"],
        "file": os.environ["MP3_FILE"],
        "bytes": mp3.stat().st_size,
        "duration_s": round(MP3(mp3).info.length),
        "published": format_datetime(published),
        "items": [{"headline": i["headline"], "jurisdiction": i["jurisdiction"],
                   "outcome": (i.get("deal") or {}).get("outcome"),
                   "sources": i["sources"]} for i in ep["items"]],
    }
    # Re-runs on the same day replace that day's episode and coverage.
    save(EPISODES, [e for e in load(EPISODES) if e["date"] != date] + [record])
    coverage = [c for c in load(COVERAGE) if c["date"] != date]
    coverage += [{"date": date, **i} for i in ep["items"]]
    save(COVERAGE, coverage)
    record_deals(date, ep["items"])


def record_deals(date: str, items: list) -> None:
    """Upsert deals by story_key so a pending deal is updated when its outcome lands."""
    deals = {d["story_key"]: d for d in load(DEALS)}
    for item in items:
        if not item.get("deal"):
            continue
        old = deals.get(item["story_key"], {})
        deals[item["story_key"]] = {
            "story_key": item["story_key"],
            "first_reported": old.get("first_reported", date),
            "updated": date,
            "jurisdiction": item["jurisdiction"],
            "headline": item["headline"],
            **item["deal"],
            "sources": list(dict.fromkeys(old.get("sources", []) + item["sources"])),
        }
    save(DEALS, sorted(deals.values(), key=lambda d: d["updated"], reverse=True))


def prune(today: dt.date) -> None:
    ep_cutoff = (today - dt.timedelta(days=CONFIG["keep_episodes_days"])).isoformat()
    cov_cutoff = (today - dt.timedelta(days=CONFIG["keep_coverage_days"])).isoformat()
    episodes = load(EPISODES)
    Path("out/prune_tags.txt").write_text(
        "".join(e["tag"] + "\n" for e in episodes if e["date"] < ep_cutoff))
    save(EPISODES, [e for e in episodes if e["date"] >= ep_cutoff])
    save(COVERAGE, [c for c in load(COVERAGE) if c["date"] >= cov_cutoff])


def notes_html(ep: dict) -> str:
    rows = []
    for item in ep["items"]:
        links = " · ".join(f'<a href="{html.escape(u)}">source {n}</a>'
                           for n, u in enumerate(item["sources"], 1))
        tag = OUTCOMES.get(item.get("outcome") or "", "")
        tag = f" <i>[Deal: {tag}]</i>" if tag else ""
        rows.append(f"<li><b>{html.escape(item['jurisdiction'])}</b> – "
                    f"{html.escape(item['headline'])}{tag} ({links})</li>")
    return f"<p>{html.escape(ep['summary'])}</p><ul>{''.join(rows)}</ul>"


def render(site_url: str) -> None:
    episodes = sorted(load(EPISODES), key=lambda e: e["date"], reverse=True)
    e = html.escape
    items = []
    for ep in episodes:
        ep["url"] = f"{site_url}/audio/{ep['file']}"
        d = ep["duration_s"]
        items.append(f"""
    <item>
      <title>{e(ep['date'])} · {e(ep['title'])}</title>
      <description><![CDATA[{notes_html(ep)}]]></description>
      <enclosure url="{e(ep['url'])}" length="{ep['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{e(ep['url'])}</guid>
      <pubDate>{ep['published']}</pubDate>
      <itunes:duration>{d // 60}:{d % 60:02d}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{e(CONFIG['show_title'])}</title>
    <link>{site_url}/</link>
    <atom:link href="{site_url}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>{e(CONFIG['show_description'])}</description>
    <language>{CONFIG['language']}</language>
    <itunes:author>{e(CONFIG['author'])}</itunes:author>
    <itunes:image href="{site_url}/cover.png"/>
    <itunes:category text="News"/>
    <itunes:explicit>false</itunes:explicit>
    <itunes:block>Yes</itunes:block>{''.join(items)}
  </channel>
</rss>
"""
    SITE.mkdir(exist_ok=True)
    (SITE / "feed.xml").write_text(feed)
    shutil.copy("site/cover.png", SITE / "cover.png")

    cards = "".join(f"""
    <article>
      <h2>{e(ep['date'])} · {e(ep['title'])}</h2>
      <audio controls preload="none" src="{e(ep['url'])}"></audio>
      {notes_html(ep)}
    </article>""" for ep in episodes)
    page = (Path("site/index.template.html").read_text()
            .replace("{{TITLE}}", e(CONFIG["show_title"]))
            .replace("{{FEED_URL}}", f"{site_url}/feed.xml")
            .replace("{{EPISODES}}", cards or "<p>No episodes yet.</p>"))
    (SITE / "index.html").write_text(page)
    render_deals()


def render_deals() -> None:
    e = html.escape
    rows = []
    for d in load(DEALS):
        links = " ".join(f'<a href="{e(u)}">[{n}]</a>' for n, u in enumerate(d["sources"], 1))
        rows.append(f"""
      <tr class="o-{e(d['outcome'])}">
        <td>{e(d['updated'])}</td>
        <td><span class="pill">{e(OUTCOMES.get(d['outcome'], d['outcome']))}</span></td>
        <td>{e(d['jurisdiction'])}</td>
        <td><b>{e(d['acquirer'])}</b> ({e(d['acquirer_country'])}) → <b>{e(d['target'])}</b> ({e(d['target_country'])})
          <div class="muted">{e(d['sector'])} · {e(d['authority'])}</div></td>
        <td>{e(d['detail'])} {links}</td>
      </tr>""")
    page = (Path("site/deals.template.html").read_text()
            .replace("{{TITLE}}", e(CONFIG["show_title"]))
            .replace("{{COUNT}}", str(len(rows)))
            .replace("{{ROWS}}", "".join(rows) or '<tr><td colspan="5">No deals recorded yet.</td></tr>'))
    (SITE / "deals.html").write_text(page)


def main() -> None:
    date = os.environ["EP_DATE"]
    if Path("out/episode.mp3").exists():
        record_episode(date)
    prune(dt.date.fromisoformat(date))
    render(os.environ["SITE_URL"].rstrip("/"))


if __name__ == "__main__":
    main()
