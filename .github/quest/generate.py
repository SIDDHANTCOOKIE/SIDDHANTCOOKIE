#!/usr/bin/env python3
"""Contribution Quest generator.

Fetches every merged PR authored by SIDDHANTCOOKIE via the GitHub search API,
classifies each into one of the four quest paths, and rewrites the
contribution-quest section of README.md between the markers:
  <!-- contribution-quest:begin --> ... <!-- contribution-quest:end -->

Runs hourly via .github/workflows/contribution-quest.yml (cron) or manually
via workflow_dispatch. GITHUB_TOKEN env var is used when present (Actions);
without it the unauthenticated rate limit still covers the 1-2 search calls.
"""
import json, os, re, sys, time, urllib.request, urllib.error

USER = "SIDDHANTCOOKIE"
BEGIN = "<!-- contribution-quest:begin -->"
END = "<!-- contribution-quest:end -->"

# --- classification -------------------------------------------------------
# Kinds of work:
#   mind   - ai & products that think (his own repos + research work)
#   blade  - security & hardening, anywhere (keyword match on title)
#   chain  - web3 & protocol engineering (StabilityNexus, healthyinc)
#   scroll - products & community (formstr suite, aossie, anything else)
SECURITY_KW = re.compile(
    r"securit|reentranc|vulnerab|exploit|audit|signature|sniping|overflow|spoof|forge",
    re.IGNORECASE,
)
# hand-verified exceptions the keywords miss (repo, pr#) -> path
OVERRIDES = {
    ("healthyinc/bio-block", 106): "blade",  # call-vs-transfer reentrancy-pattern fix
}

def classify(repo, number, title):
    if (repo, number) in OVERRIDES:
        return OVERRIDES[(repo, number)]
    if SECURITY_KW.search(title):
        return "blade"
    org = repo.split("/")[0]
    if org in ("StabilityNexus", "healthyinc"):
        return "chain"
    if org in ("SIDDHANTCOOKIE", "DemocratiseResearch"):
        return "mind"
    if org in ("formstr-hq", "AOSSIE-Org"):
        return "scroll"
    return "scroll"

# --- fetch ----------------------------------------------------------------
def http_json(url, token):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "contribution-quest-generator",
        **({"Authorization": f"Bearer {token}"} if token else {}),
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            raise

def fetch_merged_prs(token):
    prs, page = [], 1
    while True:
        q = f"author:{USER}+type:pr+is:merged"
        url = (f"https://api.github.com/search/issues?q={q}"
               f"&per_page=100&page={page}&sort=created&order=desc")
        data = http_json(url, token)
        items = data.get("items", [])
        for it in items:
            repo = it["repository_url"].split("https://api.github.com/repos/")[-1]
            merged = (it.get("pull_request") or {}).get("merged_at")
            if not merged:
                continue
            prs.append({
                "repo": repo,
                "number": it["number"],
                "title": it["title"].strip(),
                "merged_at": merged[:10],
                "url": f"https://github.com/{repo}/pull/{it['number']}",
            })
        if len(items) < 100 or len(prs) >= data.get("total_count", 0):
            break
        page += 1
        time.sleep(2)
    prs.sort(key=lambda p: p["merged_at"], reverse=True)
    return prs

# --- render ---------------------------------------------------------------
MONTHS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
def fdate(iso):
    y, m, d = iso.split("-")
    return f"{MONTHS[int(m)-1]} {int(d)}, {y}"

def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def short(t, n=72):
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"

def pr_line(p):
    return (f'<sub><a href="{p["url"]}"><b>#{p["number"]}</b> {esc(short(p["title"]))}</a>'
            f' · merged {fdate(p["merged_at"])}</sub><br>')

def repo_group(repo, prs):
    n = len(prs)
    lines = [f'<sub><b>{repo}</b> · {n} merged</sub><br>']
    lines += [pr_line(p) for p in prs]
    return "\n".join(lines)

INTRO = {
    "mind":   ("skillcheck, paperly &amp; research",
               "ai that shows its work. every merged pr on that road:"),
    "blade":  ("security work, merged upstream",
               "vulnerabilities cut out of live codebases, wherever they hid:"),
    "chain":  ("web3 &amp; protocol engineering",
               "chains, contracts and the tooling around them. every merged pr:"),
    "scroll": ("formstr, aossie &amp; community",
               "products and tools people use. every merged pr:"),
}
SHRINE_TITLE = {
    "mind": "skillcheck &amp; own products",
    "blade": "smart-contract security",
    "chain": "minichain &amp; web3",
    "scroll": "the formstr suite",
}

def shrine(path, prs):
    groups = {}
    for p in prs:
        groups.setdefault(p["repo"], []).append(p)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    head, sub = INTRO[path]
    body = "\n<br>\n".join(repo_group(r, ps) for r, ps in ordered)
    return f"""<details name="xp">
<summary><b>⛩ shrine of the {path}</b> - {SHRINE_TITLE[path]}</summary>
<a id="xp-shrine-{path}"></a>
<p align="center"><i>{sub}</i></p>
<p align="center"><b>{head}</b> · <b>{len(prs)} merged prs</b></p>
<p align="center">
{body}
<br>
<sub><a href="#user-content-xp-map">↩ walk another path</a></sub>
</p>
</details>"""

def scene(path, kanji, name, tagline):
    return f"""<details name="xp">
<summary><b>{kanji} the way of the {path}</b> - {tagline}</summary>
<a id="xp-{path}"></a>
<p align="center"><img src="assets/xp_{path}.gif" width="560"></p>
<p align="center">
<a href="#user-content-xp-shrine-{path}"><b>press on to the shrine →</b></a><br>
<sub><a href="assets/ronin-theme.mp3">♪ play the theme</a> &nbsp;·&nbsp; <a href="#user-content-xp-map">↩ return to the crossroads</a></sub>
</p>
</details>"""

def render_section(prs):
    by_path = {"mind": [], "blade": [], "chain": [], "scroll": []}
    for p in prs:
        by_path[classify(p["repo"], p["number"], p["title"])].append(p)
    total = len(prs)
    counts = {k: len(v) for k, v in by_path.items()}
    parts = [f"""## ~/play

<details name="xp" open>
<summary><b>༄ the crossroads</b> - a contribution quest</summary>
<a id="xp-map"></a>
<p align="center"><img src="assets/xp_banner.gif" width="720"></p>
<p align="center">
<sub>four paths, four kinds of work - every merged pull request lives here.<br>
<b>{total} merged prs</b> and counting; the quest renews itself with each new merge.</sub><br><br>
<a href="#user-content-xp-mind"><b>心 &nbsp;the way of the mind</b></a> &nbsp;·&nbsp;
<a href="#user-content-xp-blade"><b>刃 &nbsp;the way of the blade</b></a> &nbsp;·&nbsp;
<a href="#user-content-xp-chain"><b>鎖 &nbsp;the way of the chain</b></a> &nbsp;·&nbsp;
<a href="#user-content-xp-scroll"><b>巻 &nbsp;the way of the scroll</b></a><br>
<sub><a href="assets/ronin-theme.mp3">♪ play the theme</a> - original instrumental, no autoplay</sub>
</p>
</details>""",
        scene("mind", "心", "mind", "ai that shows its work"),
        scene("blade", "刃", "blade", "cutting vulnerabilities out"),
        scene("chain", "鎖", "chain", "a blockchain, built from scratch"),
        scene("scroll", "巻", "scroll", "the formstr suite, shipped"),
        shrine("mind", by_path["mind"]),
        shrine("blade", by_path["blade"]),
        shrine("chain", by_path["chain"]),
        shrine("scroll", by_path["scroll"]),
    ]
    return "\n\n".join(parts), counts

def main():
    readme = sys.argv[1] if len(sys.argv) > 1 else "README.md"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    prs = fetch_merged_prs(token)
    section, counts = render_section(prs)
    src = open(readme).read()
    if BEGIN not in src or END not in src:
        print("markers not found in", readme, file=sys.stderr)
        sys.exit(1)
    out = src.split(BEGIN)[0] + BEGIN + "\n\n" + section + "\n\n" + END + src.split(END)[1]
    if out != src:
        open(readme, "w").write(out)
        print("updated", readme)
    else:
        print("no change")
    print("counts:", json.dumps(counts), "total:", len(prs))

if __name__ == "__main__":
    main()
