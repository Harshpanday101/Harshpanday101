"""Calculate language usage across all your GitHub repos and write it into README.md.

Runs inside GitHub Actions. Uses the GitHub API directly, so there is no
third-party image server that can go down or hit rate limits.
"""
import json
import os
import re
import urllib.error
import urllib.request

USER = os.environ.get("GH_USER", "Harshpanday101")
TOKEN = os.environ.get("GH_TOKEN", "")
INCLUDE_FORKS = os.environ.get("INCLUDE_FORKS", "false").lower() == "true"
EXCLUDE = {x.strip().lower() for x in os.environ.get("EXCLUDE_LANGS", "").split(",") if x.strip()}
TOP_N = 8
START, END = "<!--LANGS_START-->", "<!--LANGS_END-->"


def api(url):
    headers = {"User-Agent": "lang-stats", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def fetch_pages(url_template):
    items, page = [], 1
    while True:
        chunk = api(url_template.format(page=page))
        if not chunk:
            break
        items += chunk
        page += 1
    return items


def list_repos():
    repos = None
    if TOKEN:
        # A personal token can list private repos too. The built-in GITHUB_TOKEN
        # is not allowed to call this endpoint, so fall back to public repos.
        try:
            repos = fetch_pages("https://api.github.com/user/repos?per_page=100&page={page}&affiliation=owner")
        except urllib.error.HTTPError as e:
            print(f"Could not list private repos ({e.code}); using public repos only")
    if repos is None:
        repos = fetch_pages(f"https://api.github.com/users/{USER}/repos?per_page=100&page={{page}}&type=owner")
    return [r for r in repos if r["owner"]["login"].lower() == USER.lower()
            and (INCLUDE_FORKS or not r["fork"])]


def totals(repos):
    total = {}
    for r in repos:
        for lang, size in api(r["languages_url"]).items():
            if lang.lower() not in EXCLUDE:
                total[lang] = total.get(lang, 0) + size
    return total


def render(total, repo_count):
    if not total:
        return "_No language data found yet._"
    s = sum(total.values())
    ranked = sorted(total.items(), key=lambda x: -x[1])[:TOP_N]
    lines = ["| Language | Share | |", "|:--|--:|:--|"]
    for lang, size in ranked:
        pct = size * 100 / s
        bar = "█" * round(pct / 5) or "▏"
        lines.append(f"| **{lang}** | {pct:.1f}% | `{bar}` |")
    lines.append("")
    lines.append(f"<sub>Calculated from {repo_count} repositories · auto-updated every 12 hours</sub>")
    return "\n".join(lines)


def main():
    repos = list_repos()
    block = render(totals(repos), len(repos))
    text = open("README.md", encoding="utf-8").read()
    new = re.sub(f"{START}.*?{END}", f"{START}\n{block}\n{END}", text, flags=re.S)
    if new != text:
        open("README.md", "w", encoding="utf-8").write(new)
        print("README updated")
    else:
        print("No changes")


if __name__ == "__main__":
    main()
