"""Calculate language usage across all your GitHub repos and draw it as an SVG card.

Runs inside GitHub Actions and writes assets/languages.svg, which the README displays.
Uses the GitHub API directly, so there is no third-party image server to go down.
"""
import html
import json
import os
import urllib.error
import urllib.request

USER = os.environ.get("GH_USER", "Harshpanday101")
TOKEN = os.environ.get("GH_TOKEN", "")
INCLUDE_FORKS = os.environ.get("INCLUDE_FORKS", "false").lower() == "true"
EXCLUDE = {x.strip().lower() for x in os.environ.get("EXCLUDE_LANGS", "").split(",") if x.strip()}
TOP_N = int(os.environ.get("TOP_N", "8"))
OUT = os.environ.get("OUT_FILE", "assets/languages.svg")

COLORS = {
    "Python": "#3572A5", "C++": "#f34b7d", "C": "#8a8a8a", "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6", "Java": "#b07219", "HTML": "#e34c26", "CSS": "#8a63d2",
    "Shell": "#89e051", "Makefile": "#6aa84f", "CMake": "#DA3434", "Go": "#00ADD8",
    "Rust": "#dea584", "Kotlin": "#A97BFF", "MATLAB": "#e16737", "Cuda": "#6fae5b",
    "Arduino": "#bd79d1", "Verilog": "#b2b7f8", "SQL": "#e38c00", "PHP": "#8892bf",
    "Dart": "#00B4AB", "Swift": "#F05138", "Ruby": "#cc342d", "Batchfile": "#C1F12E",
    "Assembly": "#9c6b3c", "Dockerfile": "#4c7f92", "Jupyter Notebook": "#DA5B0B",
    "Lua": "#4a4aff", "Dart": "#00B4AB",
}
FALLBACK = ["#7aa2f7", "#bb9af7", "#7dcfff", "#e0af68", "#9ece6a", "#f7768e", "#ff9e64", "#73daca"]


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


def color_for(lang, i):
    return COLORS.get(lang, FALLBACK[i % len(FALLBACK)])


def render_svg(total, repo_count):
    W, PAD = 700, 32
    BG, BORDER, TITLE, TEXT, MUTED, TRACK = "#1a1b27", "#2f334d", "#7aa2f7", "#c0caf5", "#787c99", "#2a2e45"
    font = "font-family=\"'Segoe UI',Ubuntu,'Helvetica Neue',Arial,sans-serif\""

    if not total:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="120" viewBox="0 0 {W} 120">'
                f'<rect width="{W}" height="120" rx="14" fill="{BG}" stroke="{BORDER}"/>'
                f'<text x="{W/2}" y="65" text-anchor="middle" fill="{TEXT}" {font} font-size="16">No language data yet</text></svg>')

    s = sum(total.values())
    ranked = sorted(total.items(), key=lambda x: -x[1])[:TOP_N]
    shown = sum(v for _, v in ranked)
    rows = [(lang, size * 100 / s, color_for(lang, i)) for i, (lang, size) in enumerate(ranked)]
    other = (s - shown) * 100 / s

    bar_x, bar_w, bar_y, bar_h = PAD, W - 2 * PAD, 78, 16
    per_col = (len(rows) + 1) // 2
    list_y = bar_y + bar_h + 34
    row_h = 46
    H = list_y + per_col * row_h + 38

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Languages used">',
           f'<defs><clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="8"/></clipPath></defs>',
           f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="{BG}" stroke="{BORDER}"/>',
           f'<text x="{PAD}" y="42" fill="{TITLE}" {font} font-size="22" font-weight="700">Languages I Use</text>',
           f'<text x="{PAD}" y="60" fill="{MUTED}" {font} font-size="12">Across {repo_count} GitHub repositories</text>',
           f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="8" fill="{TRACK}"/>',
           '<g clip-path="url(#bar)">']

    x = bar_x
    total_shown_pct = sum(p for _, p, _ in rows) + other
    for lang, pct, col in rows:
        w = bar_w * pct / total_shown_pct
        out.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w + 0.5:.2f}" height="{bar_h}" fill="{col}"/>')
        x += w
    out.append('</g>')

    col_w = (W - 2 * PAD) / 2
    for i, (lang, pct, col) in enumerate(rows):
        c, r = divmod(i, per_col)
        cx = PAD + c * col_w + (18 if c else 0)
        cy = list_y + r * row_h
        inner_w = col_w - 36
        name = html.escape(lang)
        out.append(f'<circle cx="{cx + 6}" cy="{cy - 5}" r="6" fill="{col}"/>')
        out.append(f'<text x="{cx + 20}" y="{cy}" fill="{TEXT}" {font} font-size="15" font-weight="600">{name}</text>')
        out.append(f'<text x="{cx + inner_w}" y="{cy}" text-anchor="end" fill="{MUTED}" {font} font-size="14">{pct:.1f}%</text>')
        out.append(f'<rect x="{cx}" y="{cy + 10}" width="{inner_w}" height="6" rx="3" fill="{TRACK}"/>')
        out.append(f'<rect x="{cx}" y="{cy + 10}" width="{max(inner_w * pct / 100, 4):.2f}" height="6" rx="3" fill="{col}"/>')

    out.append(f'<text x="{W/2}" y="{H - 14}" text-anchor="middle" fill="{MUTED}" {font} font-size="11">Auto-updated every 12 hours</text>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    repos = list_repos()
    svg = render_svg(totals(repos), len(repos))
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if svg != old:
        open(OUT, "w", encoding="utf-8").write(svg)
        print("SVG updated")
    else:
        print("No changes")


if __name__ == "__main__":
    main()
