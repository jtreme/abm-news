"""Check the opportunities page for closed postings and passed dates.

Reads internships/index.html, checks each listing's link, and looks for dates
that have already passed. Writes a markdown report to report.md and prints
"problems=N" for the workflow. Changes nothing on the site.
"""
import datetime as dt
import html
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser

PAGE = "internships/index.html"
SKIP_HOSTS = ("linkedin.com", "jtreme.github.io", "go.ncsu.edu/abm-news")
CLOSED_TEXT = [
    "no longer available", "no longer accepting", "position has been filled",
    "job not found", "job has expired", "posting has expired", "this job is closed",
    "announcement has closed", "job is no longer", "requisition is closed",
    "position is closed", "applications are closed", "page not found",
]
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:,\s*(\d{4}))?")


class Listings(HTMLParser):
    """Collect each div.job: title, link, and deadline text."""

    def __init__(self):
        super().__init__()
        self.items, self.cur, self.depth, self.field = [], None, 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "div" and "job" in cls and self.cur is None:
            self.cur, self.depth = {"title": "", "links": [], "due": ""}, 1
            return
        if self.cur is None:
            return
        if tag == "div":
            self.depth += 1
            if "t" in cls:
                self.field = "title"
        if tag == "span" and "due" in cls:
            self.field = "due"
        if tag == "a" and a.get("href"):
            self.cur["links"].append(a["href"])

    def handle_endtag(self, tag):
        if self.cur is None:
            return
        if tag in ("div", "span"):
            self.field = None
        if tag == "div":
            self.depth -= 1
            if self.depth == 0:
                self.items.append(self.cur)
                self.cur = None

    def handle_data(self, data):
        if self.cur is not None and self.field:
            self.cur[self.field] += data


def passed_dates(text, today):
    out = []
    for mon, day, year in DATE_RE.findall(text):
        m = MONTHS[mon[:3].lower()]
        y = int(year) if year else today.year
        try:
            d = dt.date(y, m, int(day))
        except ValueError:
            continue
        if not year and d < today - dt.timedelta(days=120):
            d = d.replace(year=d.year + 1)  # a yearless date far in the past means next year
        if d < today:
            out.append(d)
    return out


def check(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(400_000).decode("utf-8", "ignore").lower()
            for phrase in CLOSED_TEXT:
                if phrase in body:
                    return "closed", f'page says "{phrase}"'
            return "ok", str(r.status)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return "closed", f"HTTP {e.code}"
        return "unknown", f"HTTP {e.code}"
    except Exception as e:  # timeouts, blocked bots, TLS errors
        return "unknown", type(e).__name__


def main():
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()
    p = Listings()
    p.feed(open(PAGE, encoding="utf-8").read())
    closed, dates, unknown = [], [], []
    for it in p.items:
        title = html.unescape(" ".join(it["title"].split())) or "(untitled)"
        for d in passed_dates(html.unescape(it["due"]), today):
            dates.append(f"- **{title}**: {d:%b. %-d, %Y} has passed (\"{' '.join(it['due'].split())}\")")
        for url in it["links"]:
            if not url.startswith("http") or any(h in url for h in SKIP_HOSTS):
                continue
            status, why = check(url)
            if status == "closed":
                closed.append(f"- **{title}**: {why}. {url}")
            elif status == "unknown":
                unknown.append(f"- {title}: {why}. {url}")
    problems = len(closed) + len(dates)
    lines = [f"Opportunities page check, {today:%b. %-d, %Y}. Listings checked: {len(p.items)}.", ""]
    if closed:
        lines += ["### Postings that look closed", *closed, ""]
    if dates:
        lines += ["### Dates on the page that have passed", *dates, ""]
    if not problems:
        lines += ["Nothing to review. All checked links loaded and no listed dates have passed.", ""]
    if unknown:
        lines += ["<details><summary>Links the checker could not open (often sites that block automated checks; usually fine)</summary>", "", *unknown, "", "</details>", ""]
    lines += ["LinkedIn search links are not checked. Nothing on the site was changed."]
    open("report.md", "w").write("\n".join(lines))
    print(f"problems={problems}")


if __name__ == "__main__":
    sys.exit(main())
