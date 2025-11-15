#!/usr/bin/env python3
"""
PV247 PR fetcher/checkout (bez Selenium)

- Vyhľadá v organizácii PR s labelom a kľúčovým slovom v názve.
- Voliteľne filtruje len tvoju skupinu študentov.
- Vie preskočiť PR, ktoré už majú hodnotiaci komentár/review (Hodnotenie/Hodnoceni/Evaluation).
- Klonuje len PR, ktoré sa zmenili (podľa HEAD SHA) – cache v last_tested_sha.json.

Autor: ty + ChatGPT
"""

from __future__ import annotations

import os, sys, re, json, subprocess, argparse, textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any, Tuple

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------ CLI ------------------

class SmartFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass

def parse_args() -> argparse.Namespace:
    epilog = textwrap.dedent("""\
        Príklady:
          # Len od dátumu (updated >=), všetky úlohy:
          python3 step1_orchestrator.py -s 2025-09-01

          # Len konkrétna úloha (substring filter), najprv na sucho:
          python3 step1_orchestrator.py -s 2025-01-01 -c t-07-nextjs-basic- -n 60 --dry-run --debug

          # Potom naostro (klonovanie):
          python3 step1_orchestrator.py -s 2025-01-01 -c t-07-nextjs-basic- -n 60

          # Viac úloh naraz (regex, tasks 06–09):
          python3 step1_orchestrator.py -s 2025-01-01 -r '^t-0(6|7|8|9)-' -n 120

          # Vylúčiť solution/template repá:
          python3 step1_orchestrator.py -s 2025-01-01 -c t-07-nextjs-basic- -x '(solution|template)'

          # Použiť created:>= namiesto updated:>=
          python3 step1_orchestrator.py -s 2025-01-01 --created -c t-07-nextjs-basic-

          # Len tvoji študenti (zo súboru) + preskoč už hodnotené PR:
          python3 step1_orchestrator.py -s 2025-01-01 -c t-07-nextjs-basic- \\
            --students-file students.txt --student-match either \\
            --skip-if-evaluated --dry-run

        Poznámky:
          • Token sa číta z env premennej: GITHUB_TOKEN (povinné).
          • Ak CLI parameter neudáš, skript skúsi ENV fallbacky:
              since: PV247_SINCE/SINCE
              contains: PV247_REPO_CONTAINS
              regex: PV247_REPO_REGEX
              exclude: PV247_EXCLUDE_REGEX
              limit: PV247_LIMIT
              workers: PV247_WORKERS
              timeout: PV247_TIMEOUT
              org: PV247_ORG (default: FI-PV247)
              label: PV247_LABEL (default: Submitted)
              title: PV247_TITLE_CONTAINS (default: Feedback)
              clone-root: PV247_CLONE_ROOT (default: ./cloned_repos)
    """)
    p = argparse.ArgumentParser(
        description="PV247 PR fetcher/checkout bez Selenium: vyberie PR podľa filtrov a naklonuje len zmenené.",
        formatter_class=SmartFormatter,
        epilog=epilog
    )
    # základné filtre
    p.add_argument("-s", "--since", help="Filter na dátum (YYYY-MM-DD). Default z ENV PV247_SINCE/SINCE.")
    p.add_argument("--created", action="store_true",
                   help="Použi created:>= namiesto updated:>= vo vyhľadávaní.")
    p.add_argument("-c", "--contains", action="append",
                   help="Substring filter na názov repa (možno zadať viackrát).")
    p.add_argument("-r", "--regex", help="Regex filter na názov repa (include).")
    p.add_argument("-x", "--exclude", help="Regex na vylúčenie názvov rep.")

    # výkonnostné a technické
    p.add_argument("-n", "--limit", type=int, default=int(os.getenv("PV247_LIMIT", "0") or "0"),
                   help="Max počet PR na spracovanie (0 = bez limitu).")
    p.add_argument("-w", "--workers", type=int, default=int(os.getenv("PV247_WORKERS", "8") or "8"),
                   help="Počet paralelných workerov pre sťahovanie PR detailov.")
    p.add_argument("-t", "--timeout", type=float, default=float(os.getenv("PV247_TIMEOUT", "20")),
                   help="HTTP timeout v sekundách.")
    p.add_argument("-d", "--dry-run", action="store_true", help="Len vypíš, neklonuj.")
    p.add_argument("--debug", action="store_true", help="Vypíš query, počty, progres a vzorku názvov repo.")

    # GitHub kontext
    p.add_argument("--org", default=os.getenv("PV247_ORG", "FI-PV247"), help="GitHub organizácia.")
    p.add_argument("--label", default=os.getenv("PV247_LABEL", "Submitted"), help="Požadovaný label PR.")
    p.add_argument("--title-contains", default=os.getenv("PV247_TITLE_CONTAINS", "Feedback"),
                   help="Text, ktorý musí byť v názve PR.")
    p.add_argument("--clone-root", default=os.getenv("PV247_CLONE_ROOT", "./cloned_repos"),
                   help="Výstupný adresár pre klonovanie.")

    # študenti
    p.add_argument("--students-file", help="Cesta k súboru s GitHub loginmi (1 login/riadok; '@' sa ignoruje).")
    p.add_argument("--students", action="append",
                   help="Zoznam loginov priamo v CLI (comma-separated). Môžeš zadať viackrát.")
    p.add_argument("--student-match", choices=["author","repo","either"], default="either",
                   help="Ako párovať študenta: autor PR, suffix názvu repo (posledný segment), alebo stačí jedno z toho.")

    # preskočiť už hodnotené
    p.add_argument("--skip-if-evaluated", action="store_true",
                   help="Preskoč PR, ak už obsahuje hodnotiaci komentár/review.")
    p.add_argument("--eval-regex",
                   default=os.getenv("PV247_EVAL_REGEX", r"\b(hodnotenie|hodnoceni|evaluation)\b"),
                   help="Regex pre rozpoznanie hodnotiaceho komentára (case-insensitive).")

    p.add_argument("-V", "--version", action="version", version="step1_orchestrator 1.5.0")
    return p.parse_args()

# ------------------ Konfigurácia ------------------

@dataclass
class Config:
    since: str | None
    created: bool
    contains: List[str]
    regex: str | None
    exclude: str | None
    limit: int
    workers: int
    timeout: float
    dry_run: bool
    debug: bool
    org: str
    label: str
    title_contains: str
    clone_root: Path
    students: set[str]
    student_match: str  # 'author' | 'repo' | 'either'
    skip_if_evaluated: bool
    eval_re: re.Pattern

    cache_file: Path = Path("./last_tested_sha.json")
    github_api: str = "https://api.github.com"
    token: str = ""

def load_config(ns: argparse.Namespace) -> Config:
    def _normalize_login(token: str) -> str:
        return token.strip().lstrip("@").lower()

    since = ns.since or os.getenv("PV247_SINCE") or os.getenv("SINCE")
    contains = ns.contains[:] if ns.contains else []
    if not contains and os.getenv("PV247_REPO_CONTAINS"):
        contains = [os.getenv("PV247_REPO_CONTAINS")]

    # študenti zo súboru + inline
    students: set[str] = set()
    if ns.students_file:
        with open(ns.students_file, "r", encoding="utf-8") as f:
            for line in f:
                for t in re.split(r"[,\s]+", line.strip()):
                    if t:
                        students.add(_normalize_login(t))
    if ns.students:
        for chunk in ns.students:
            for t in re.split(r"[,\s]+", chunk.strip()):
                if t:
                    students.add(_normalize_login(t))

    token = os.getenv("GITHUB_TOKEN") or ""
    if not token:
        print("❌ Setni si GITHUB_TOKEN (export GITHUB_TOKEN=...)")
        sys.exit(1)
    os.environ.setdefault("GH_TOKEN", token)  # keby si neskôr použil `gh` CLI

    cfg = Config(
        since=since,
        created=ns.created,
        contains=contains,
        regex=ns.regex or os.getenv("PV247_REPO_REGEX"),
        exclude=ns.exclude or os.getenv("PV247_EXCLUDE_REGEX"),
        limit=ns.limit,
        workers=ns.workers,
        timeout=ns.timeout,
        dry_run=ns.dry_run or (os.getenv("PV247_DRYRUN", "0") == "1"),
        debug=ns.debug or (os.getenv("PV247_DEBUG", "0") == "1"),
        org=ns.org,
        label=ns.label,
        title_contains=ns.title_contains,
        clone_root=Path(ns.clone_root),
        students=students,
        student_match=ns.student_match,
        skip_if_evaluated=ns.skip_if_evaluated or (os.getenv("PV247_SKIP_IF_EVALUATED", "0") == "1"),
        eval_re=re.compile(ns.eval_regex, re.I),
        token=token
    )
    cfg.clone_root.mkdir(parents=True, exist_ok=True)
    return cfg

# ------------------ GitHub klient ------------------

def build_session(cfg: Config) -> requests.Session:
    """HTTP session s retries a tokenom."""
    s = requests.Session()
    s.headers.update({"Authorization": f"token {cfg.token}", "Accept": "application/vnd.github+json"})
    retry = Retry(total=5, backoff_factor=0.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET"]))
    adapter = HTTPAdapter(max_retries=retry, pool_connections=cfg.workers, pool_maxsize=cfg.workers)
    s.mount("https://", adapter)
    return s

def gh_get(session: requests.Session, url: str, timeout: float, **params) -> Any:
    r = session.get(url, params=params, timeout=timeout)
    if r.status_code >= 400:
        print(f"\n❌ GitHub API {r.status_code}: {r.url}\n{r.text}\n")
        r.raise_for_status()
    return r.json()

# ------------------ Vyhľadávanie a filtre ------------------

def repo_full_name(repo_api_url: str) -> str:
    """'https://api.github.com/repos/FI-PV247/x' -> 'FI-PV247/x'."""
    return "/".join(repo_api_url.rstrip("/").split("/")[-2:])

def build_search_query(cfg: Config) -> str:
    parts = [f"org:{cfg.org}", "is:pr", "is:open", f"label:{cfg.label}", "in:title", cfg.title_contains]
    if cfg.since and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cfg.since):
        parts.append(f"{'created' if cfg.created else 'updated'}:>={cfg.since}")
    return " ".join(parts)

def search_issues_all_pages(session: requests.Session, cfg: Config, q: str, per_page=100) -> List[Dict[str, Any]]:
    page = 1
    total_items: List[Dict[str, Any]] = []
    if cfg.debug:
        print(f"🔍 Query: {q}")
    while True:
        payload = gh_get(session, f"{cfg.github_api}/search/issues",
                         cfg.timeout, q=q, per_page=per_page, page=page,
                         sort="updated", order="desc")
        items = payload.get("items", [])
        if page == 1:
            total = payload.get("total_count", len(items))
            print(f"🔎 Search matched ≈ {total} PR (GitHub vráti max ~1000).")
        total_items.extend(items)
        if len(items) < per_page: break
        if cfg.limit and len(total_items) >= cfg.limit: break
        page += 1
    if cfg.limit:
        total_items = total_items[:cfg.limit]
    return total_items

def filter_students(items: List[Dict[str, Any]], cfg: Config) -> List[Dict[str, Any]]:
    """Filter podľa zoznamu študentov (autor PR, resp. suffix v názve repa)."""
    if not cfg.students:
        return items
    before = len(items)

    def repo_name(it) -> str:
        return repo_full_name(it["repository_url"]).split("/")[1]

    def ends_with_login(name: str) -> bool:
        lower = name.lower()
        # posledný segment za '-'
        suffix = lower.rsplit("-", 1)[-1]
        if suffix in cfg.students:
            return True
        return any(lower.endswith("-" + u) for u in cfg.students)

    kept = []
    for it in items:
        author = ((it.get("user") or {}).get("login") or "").lower()
        name = repo_name(it)
        by_author = author in cfg.students
        by_repo = ends_with_login(name)
        ok = (cfg.student_match == "author" and by_author) or \
             (cfg.student_match == "repo" and by_repo) or \
             (cfg.student_match == "either" and (by_author or by_repo))
        if ok:
            kept.append(it)

    print(f"👥 STUDENTS filter (match={cfg.student_match}) → zostáva: {len(kept)} PR (−{before - len(kept)})")
    return kept

def filter_contains_regex(items: List[Dict[str, Any]], cfg: Config) -> List[Dict[str, Any]]:
    """Substring + include-regex + exclude-regex filtre nad názvom repa."""
    def repo_name(it) -> str:
        return repo_full_name(it["repository_url"]).split("/")[1]

    if cfg.contains:
        before = len(items)
        lowers = [s.lower() for s in cfg.contains]
        items = [it for it in items if any(s in repo_name(it).lower() for s in lowers)]
        print(f"🔎 REPO_CONTAINS={cfg.contains} → zostáva: {len(items)} PR (−{before - len(items)})")

    if cfg.regex:
        before = len(items)
        rx = re.compile(cfg.regex, re.I)
        items = [it for it in items if rx.search(repo_name(it))]
        print(f"🧹 REPO_REGEX → zostáva: {len(items)} PR (−{before - len(items)})")

    if cfg.exclude:
        before = len(items)
        ex = re.compile(cfg.exclude, re.I)
        items = [it for it in items if not ex.search(repo_name(it))]
        print(f"🚫 EXCLUDE_REGEX vyradil: {before - len(items)} PR (zostáva {len(items)})")

    return items

# ---------- Detekcia "už hodnotené" ----------

def list_issue_comments(session: requests.Session, cfg: Config, repo_full: str, number: int) -> Iterable[Dict[str, Any]]:
    page = 1
    while True:
        chunk = gh_get(session, f"{cfg.github_api}/repos/{repo_full}/issues/{number}/comments",
                       cfg.timeout, per_page=100, page=page)
        if not isinstance(chunk, list): break
        for c in chunk: yield c
        if len(chunk) < 100: break
        page += 1

def list_pr_reviews(session: requests.Session, cfg: Config, repo_full: str, number: int) -> Iterable[Dict[str, Any]]:
    page = 1
    while True:
        chunk = gh_get(session, f"{cfg.github_api}/repos/{repo_full}/pulls/{number}/reviews",
                       cfg.timeout, per_page=100, page=page)
        if not isinstance(chunk, list): break
        for r in chunk: yield r
        if len(chunk) < 100: break
        page += 1

def pr_has_evaluation_marker(session: requests.Session, cfg: Config, repo_full: str, number: int) -> bool:
    # issue comments
    for c in list_issue_comments(session, cfg, repo_full, number):
        if cfg.eval_re.search(c.get("body") or ""): return True
    # review summary comments
    for r in list_pr_reviews(session, cfg, repo_full, number):
        if cfg.eval_re.search(r.get("body") or ""): return True
    return False

# ------------------ Fetch PR detaily + klonovanie ------------------

def fetch_pr_detail(session: requests.Session, cfg: Config, it: Dict[str, Any]) -> Dict[str, Any]:
    full = repo_full_name(it["repository_url"])
    number = it["number"]
    pr = gh_get(session, f"{cfg.github_api}/repos/{full}/pulls/{number}", cfg.timeout)
    return {
        "repo": full,
        "number": number,
        "url": it["html_url"],
        "head_sha": pr["head"]["sha"],
        "head_ref": pr["head"]["ref"],
        "ssh_url": pr["head"]["repo"]["ssh_url"] if pr["head"]["repo"] else None,
        "https_url": pr["head"]["repo"]["clone_url"] if pr["head"]["repo"] else None,
        "default_branch": pr["base"]["repo"]["default_branch"],
    }

def ensure_checkout(cfg: Config, pr: Dict[str, Any]) -> str:
    """Naklonuj repo (ak netreba, len fetch/checkout na PR vetvu)."""
    repo_name = pr["repo"].split("/")[1]
    dest = cfg.clone_root / repo_name
    ref = pr["head_ref"]

    def run(cmd: str, cwd: Path | None = None, ok: bool = True) -> int:
        print("→", cmd)
        try:
            subprocess.run(cmd, shell=True, check=True, cwd=cwd,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return 0
        except subprocess.CalledProcessError as e:
            if ok: return e.returncode
            raise

    if not dest.exists():
        if pr["ssh_url"]:
            run(f"git clone --no-tags --depth 1 {pr['ssh_url']} {dest}", ok=True)
        elif pr["https_url"]:
            https_with_token = pr["https_url"].replace("https://", f"https://{cfg.token}@")
            run(f"git clone --no-tags --depth 1 {https_with_token} {dest}", ok=True)
        else:
            raise RuntimeError("Repo zdroj pre head branch nie je dostupný (deleted fork?).")

    run(f"git fetch origin {ref} --depth 1", cwd=dest, ok=True)
    run(f"git checkout -B {ref} origin/{ref}", cwd=dest, ok=True)
    return str(dest)

# ------------------ Cache ------------------

def load_cache(path: Path) -> Dict[str, str]:
    if path.exists():
        try:
            return json.loads(path.read_text() or "{}")
        except Exception:
            return {}
    return {}

def save_cache(path: Path, data: Dict[str, str]) -> None:
    path.write_text(json.dumps(data, indent=2))

# ------------------ Hlavná logika ------------------

def main() -> None:
    ns = parse_args()
    cfg = load_config(ns)
    session = build_session(cfg)

    # Info
    if cfg.since and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cfg.since):
        print(f"⚠️  Ignorujem --since='{cfg.since}' – očakávam YYYY-MM-DD.")
    print(f"📅 Filter: {'created' if cfg.created else 'updated'} >= {cfg.since}" if cfg.since else "📅 Filter: bez dátumu")
    if cfg.contains:   print(f"🔎 REPO_CONTAINS: {cfg.contains}")
    if cfg.regex:      print(f"🔤 REPO_REGEX: {cfg.regex}")
    if cfg.exclude:    print(f"🚫 EXCLUDE_REGEX: {cfg.exclude}")
    if cfg.students:   print(f"👥 STUDENTS: {len(cfg.students)} používateľov (match={cfg.student_match})")
    if cfg.skip_if_evaluated: print(f"🧾 SKIP_IF_EVALUATED: on (regex={cfg.eval_re.pattern})")
    if cfg.limit:      print(f"⛏️  MAX_RESULTS: {cfg.limit}")
    if cfg.dry_run:    print("🧪 DRYRUN: zapnutý (nebudem klonovať)")
    if cfg.debug:      print("🐞 DEBUG: zapnutý (ukážem query a vzorku názvov repo)")
    print("")

    # 1) vyhľadanie PR
    q = build_search_query(cfg)
    items = search_issues_all_pages(session, cfg, q)

    # 2) filtre: študenti -> contains/regex/exclude
    items = filter_students(items, cfg)
    items = filter_contains_regex(items, cfg)
    if not items:
        print("ℹ️ Po filtroch nezostalo nič.")
        return

    # 3) voliteľne preskoč PR s hodnotením
    if cfg.skip_if_evaluated:
        before = len(items)
        kept: List[Dict[str, Any]] = []
        print(f"🔎 Kontrolujem hodnotiace komentáre (max workers={min(cfg.workers,6)})...")
        with ThreadPoolExecutor(max_workers=min(cfg.workers, 6)) as ex:
            futures = {}
            for it in items:
                full = repo_full_name(it["repository_url"])
                futures[ex.submit(pr_has_evaluation_marker, session, cfg, full, it["number"])] = it
            done = 0
            total = len(futures)
            for fut in as_completed(futures):
                done += 1
                try:
                    has_eval = fut.result()
                except Exception:
                    has_eval = False  # pri chybe radšej nepreskoč
                if not has_eval:
                    kept.append(futures[fut])
                if done % 10 == 0 or done == total:
                    print(f"  …eval-scan progress [{done}/{total}]")
        items = kept
        print(f"🧾 SKIP_IF_EVALUATED → zostáva: {len(items)} PR (−{before - len(items)})")
        if not items:
            print("ℹ️ Všetky zachytené PR už majú hodnotenie.")
            return

    # 4) Debug vzorka názvov rep
    if cfg.debug and items:
        names = sorted({repo_full_name(it["repository_url"]).split('/')[1] for it in items})
        print("\n🧭 SAMPLE repo names (first ~30 unique):")
        for n in names[:30]:
            print("  ·", n)
        print("")

    # 5) načítaj detaily PR paralelne (kvôli HEAD SHA, vetve, clone URL)
    out: List[Dict[str, Any]] = []
    print(f"⏬ Naťahujem detaily PR paralelne (workers={cfg.workers})...")
    with ThreadPoolExecutor(max_workers=cfg.workers) as ex:
        futures = {ex.submit(fetch_pr_detail, session, cfg, it): i for i, it in enumerate(items, 1)}
        total = len(futures)
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                out.append(fut.result())
            except Exception as e:
                print(f"⚠️  PR detail zlyhal: {e}")
            if done % 5 == 0 or done == total:
                print(f"  …progress [{done}/{total}]")

    if cfg.dry_run:
        print("\n===== ZOZNAM PR (dry-run) =====")
        for p in out:
            print(f"- {p['repo']} PR#{p['number']} {p['url']}")
        return

    # 6) klonovanie len pre nové/zmenené PR
    cache = load_cache(cfg.cache_file)
    changed, skipped = [], []
    for p in out:
        key = f"{p['repo']}#{p['number']}"
        if cache.get(key) == p["head_sha"]:
            skipped.append(p); continue
        dest = ensure_checkout(cfg, p)
        changed.append({**p, "path": dest})
        cache[key] = p["head_sha"]

    save_cache(cfg.cache_file, cache)

    # 7) report
    print("\n===== ZHRNUTIE =====")
    if changed:
        print("🔄 Aktualizované/nové PR:")
        for c in changed:
            print(f"  - {c['repo']} PR#{c['number']} ({c['head_ref']} @ {c['head_sha'][:7]}) → {c['path']}")
    else:
        print("✅ Nič sa nezmenilo od posledného behu (podľa commit SHA).")
    if skipped:
        print(f"\n⏭️ Preskočené (bez zmeny SHA): {len(skipped)}")

if __name__ == "__main__":
    main()
