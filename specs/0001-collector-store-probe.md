---
id: 0001
title: Polite collector, append-only raw store on the HF Dataset, and the bot-block probe Action
status: in-progress
created: 2026-09-27
---

## Problem

Every later stage needs the raw HTML of every in-scope FDA drug warning letter, with provenance: parsing, labelling, classification, search and trends. It also needs to be able to re-collect weekly without duplicating or silently changing anything. Today nothing is collected. Facts found on 2026-09-27 while writing this spec shape the design:

1. **The live fda.gov listing starts in January 2021.** The DataTables JSON endpoint behind the listing page returns 3,701 rows (500 per request). The oldest was posted 01/15/2021. Older letter pages are still served, but nothing on fda.gov lists them. **Decision:** the corpus window is the live listing. FY2019–FY2020 are dropped, and FY2021 is partial (its oldest in-scope letter was issued 2021-01-22). `docs/vision.md` and the roadmap are amended in task 1.
2. **Drug CGMP letters are not all issued by CDER.** Of the 674 listing rows whose subject is a drug CGMP, API, compounding or finished-pharmaceutical letter, 190 were issued by ORA pharmaceutical-quality divisions. Examples include "Division of Pharmaceutical Quality Operations I–IV" and "Office of Pharmaceutical Quality Operations, Division II", and ~10 came from CVM, CBER or CFSAN. **Decision:** scope is decided by the **subject line** using the letter-type rule table, not by issuing office. The office is recorded as metadata.
3. **fda.gov `robots.txt` sets `Crawl-Delay: 30` for `*`.** The collector keeps a 30 s minimum interval. Filtering the listing by subject *before* fetching keeps the backfill to 674 letters.
4. **The listing contains duplicate rows.** `lone-pine-farm-654161-06262023` appears twice, identical. Pagination checks must tolerate identical duplicates.

Spot check of 8 in-scope `CGMP/Finished Pharmaceuticals` rows, each fetched and read on 2026-09-27. All 8 are domestic (US address on the letter page), all 8 are kept by the rule table below, and every page's Issuing Office equals the listing's:

| Firm | Issued | Issuing office |
|---|---|---|
| Diamond Chemical Co., Inc. | 2024-09-06 | Division of Pharmaceutical Quality Operations I |
| Clean Solutions LLC | 2024-09-06 | Division of Pharmaceutical Quality Operations I |
| Little Moon Essentials, LLC | 2024-09-17 | Division of Pharmaceutical Quality Operations II |
| Wittman Pharma, Inc. | 2024-08-06 | Division of Pharmaceutical Quality Operations II |
| kdc/one Chatsworth, Inc. | 2026-09-08 | Center for Drug Evaluation and Research (CDER) |
| Empower Clinic Services, LLC dba Empower Pharmacy | 2026-09-18 | Center for Drug Evaluation and Research (CDER) |
| Bausch & Lomb Inc. | 2026-09-04 | Center for Drug Evaluation and Research (CDER) |
| Happy Farm Botanicals, Inc. | 2026-09-01 | Center for Drug Evaluation and Research (CDER) |

The first four would have been lost under the earlier CDER-office filter.

fda.gov sits behind bot protection that may block GitHub runner IPs. The collection design assumes a weekly Action (Day 5), so a manually dispatched probe Action checks this on Day 1. That leaves time to fall back to PC-only collection.

This spec covers roadmap Day 1 slices 1, 2 and 6, plus the scope amendments these decisions require.

## Goals

- `regintel collect` reads the full live listing and keeps rows whose subject maps to a letter type. It fetches only those letter pages, politely: 30 s minimum interval, bounded retries, and it stops on blocking. The HTML is stored in `alasdo/regintel-data` under `raw/`, with one append-only manifest line per stored letter version.
- A rerun with no upstream change adds 0 manifest lines and fetches 0 letter pages.
- Nothing already in `raw/` is ever overwritten or deleted. The store enforces this in code, not just by convention.
- The first backfill can be interrupted at any point and resumed without losing fetched pages or refetching stored ones.
- A `workflow_dispatch` probe Action fetches the listing endpoint and one current drug CGMP letter page from a GitHub runner. It logs HTTP status, byte count, sha256 and a looks-like-a-letter check, and commits `probe/<run_id>.json` to the Dataset with `HF_TOKEN`.
- `docs/vision.md`, `specs/ROADMAP.md` and `docs/decisions/0001-architecture.md` are amended to the new window, the subject-based scope and the extended Dataset layout.
- Everything is tested offline with recorded fixtures.

## Non-goals

- Letters not on the live listing (anything posted before 2021-01-15). This is dropped by decision and stated as a limitation.
- Parsing letter content. The one exception is the `looks_like_letter` sanity check. Canonical text, metadata and observations are slices 3–4.
- Changing the letter-type taxonomy. The rule table implements the vision's four types. Subjects it does not match are out of scope and not fetched.
- Fetching response-letter or close-out-letter pages. Only their URLs and dates from the listing are recorded.
- FDA Data Dashboard ingest (Day 5).
- The weekly scheduled collect workflow (Day 5). This spec ships only the manual probe workflow.
- Running the full backfill to completion. That is the Day 1 roadmap demo, not an acceptance check here, because it takes about 6 h of wall-clock time.

## Design

### Data flow

```
fda.gov listing (DataTables JSON, 8 × 500-row pages, 30 s apart)
        ↓ parse + validate (fail loudly on drift), dedupe identical rows
ListingRow[3,701]  ─────────────────────────────→ raw/listing/<ts>-<sha8>.jsonl.gz
        ↓ letter_type(subject) is not None          (full snapshot, only when changed)
ListingRow[674]  (in scope)
        ↓ plan: ids not in manifest/skipped, plus ids whose posted_date changed
        │       since the previous snapshot; newest posted first
PoliteClient.get  (30 s interval, retry 429/5xx, 403 → stop)
        ↓ looks_like_letter, else not stored (3 in a row → stop)
data/cache/pending/<letter_id>/<sha256>.html + record.json   (survives a crash)
        ↓ every --batch-size letters and at the end
guarded_commit(additions, parent_revision)   (append-only guard)
        ↓
HF Dataset  raw/letters/<letter_id>/<sha256>.html
            raw/manifest.jsonl     (one line per stored letter version)
            raw/skipped.jsonl      (in-scope rows whose page returned 404)
            raw/listing/…          (snapshots)
            probe/<run_id>.json    (probe Action only)
```

### Scope: the letter-type rule table

`src/regintel/letter_type.py` is the **single source** of letter-type rules. The collector uses it now to decide what to fetch, and `parse` (slice 4) will import the same function to set `letter_type`. Rules are ordered and the first match wins. All regexes are case-insensitive. Subjects are HTML-unescaped, with tags stripped and whitespace collapsed.

| Order | Result | Rule |
|---|---|---|
| 0 | `None` (out of scope) | Excludes: `Medical Device\|QSR\|Biologic\|Blood\|HCT/P\|Tobacco\|Food\|Feed\|Dietary\|Seafood\|Juice\|Infant\|Water` |
| 1 | `compounding` | `Compound\|Outsourcing\|503[AB]` |
| 2 | `api` | `CGMP.*(Active Pharmaceutical Ingredient\|\bAPI\b)` |
| 3 | `cgmp_finished` | `CGMP.*(Finished (Pharmaceutical\|Drug)\|\bOTC\b\|\bDrugs?\b\|Drug Products\|PET)` |
| 4 | `unapproved_misbranded` | `Finished Pharmaceutical.*(Unapproved\|Misbrand)` |
| – | `None` | no match |

`RULES_VERSION` is an integer constant, and `rules_sha256()` hashes the rule table's source. Both are recorded on every manifest line and in `CollectSummary`. When the rules change, newly matching rows are fetched on the next run. Rows that stop matching stay stored, because nothing is deleted.

Applied to the 2026-09-27 listing, the table keeps 674 rows. By issue fiscal year:

| FY (issue date) | cgmp_finished | api | compounding | unapproved_misbranded | total |
|---|---|---|---|---|---|
| 2021 (from 2021-01-22) | 26 | 4 | 13 | 36 | 79 |
| 2022 | 53 | 9 | 8 | 27 | 97 |
| 2023 | 75 | 6 | 11 | 14 | 106 |
| 2024 | 109 | 4 | 4 | 31 | 148 |
| 2025 | 90 | 14 | 12 | 1 | 117 |
| 2026 | 101 | 16 | 10 | 0 | 127 |

Deliberately **out of scope** under this table. Counts are CDER-issued rows unless noted:
- `Unapproved New Drugs/Misbranded` without "Finished Pharmaceutical": 106 rows
- telehealth and internet sales: ~140 rows
- COVID-19 products: ~47 rows
- `Nonprescription/OTC`: 38 rows
- clinical investigator, BIMO and GLP letters
- `CGMP/QSR/Drug/Medical Devices`: 2 rows, any office

Kept although not CDER-issued: 5 CVM (animal-drug CGMP), 4 CBER, 1 ORA food division and 3 CFSAN rows. Their `issuing_office` is recorded, so `parse` or analysis can separate them later.

**`tests/fixtures/collect/subjects_2026-09-27.csv`** lists every distinct subject in the listing with its count and expected `letter_type`. It is the golden table for the rules and is reviewed in the PR.

### Identity

- **`letter_id`** is the last path segment of the letter URL, for example `kdcone-chatsworth-inc-733205-09082026`. The MARCS-CMS number is *not* used, because a letter and its close-out share it.
- **URL normalisation.** Use `https://www.fda.gov` plus the path, with no query, fragment or trailing slash. Case is kept.

### Refetch rule (the "cache")

An in-scope row is fetched when either of these holds:

- its `letter_id` has no manifest line and no `skipped.jsonl` line
- its `posted_date` differs from the same id's `posted_date` in the **latest listing snapshot**, which means FDA reposted it

A refetch whose sha256 matches an existing manifest line for that id adds nothing. A different sha256 adds a new file and a new line, and the old file stays. Comparing against the snapshot rather than the manifest keeps a same-sha refetch from triggering again every week.

A listing snapshot is written only when its canonical content changes **and every repost in the plan got a definitive answer** (a letter page, stored or unchanged, or a 404). Unfetched *new* letters need no such gate, because they stay unknown and are planned again next run. For ids missing from the latest snapshot (for example mid-backfill), the refetch rule compares against the `posted_date` on the newest manifest line for that id. Canonical content means the deduplicated rows sorted by `letter_id`, serialised as JSONL with sorted keys, and gzipped with `mtime=0`. The latest snapshot therefore records close-out changes without refetching letters. Snapshots hold **all** listing rows, in scope or not, so every scope decision can be recomputed and audited.

`data/cache/pending/<store key>/` holds fetched but unpushed pages. The key is a hash of the destination store's identity, so a `--no-push` dry run's pages can never reach the Hub dataset. On start, pending records are pushed first with their original `retrieved_at`. After a successful commit, the pushed entries are deleted. `data/` is gitignored, and `data/raw/**` is guard-protected, which is why the cache lives in `data/cache/`.

### Volume and duration estimates (from the 2026-09-27 listing)

| Run | Requests | Wall-clock at 30 s |
|---|---|---|
| First backfill | 8 listing pages + 674 letters = 682 | ≈ 5 h 41 min, plus retries. Runs on the owner's PC, resumable. |
| Weekly increment | 8 listing pages + ~2–3 new in-scope letters (674 letters over ~296 weeks ≈ 2.3/week) | ≈ 5–6 min |
| Probe | 1 listing page (`length=10`) + 1 letter | ≈ 30 s |

At 50 letters per batch, the backfill makes ≈ 14 commits.

### Interfaces

```python
# src/regintel/config.py
@dataclass(frozen=True)
class Settings:
    dataset_repo: str = "alasdo/regintel-data"  # env REGINTEL_DATASET
    hf_token: str | None = None  # env HF_TOKEN; never logged
    cache_dir: Path = Path("data/cache")  # env REGINTEL_CACHE_DIR
    user_agent: str = "regintel/<version> (+https://github.com/alasdo/regintel)"

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings": ...


# src/regintel/letter_type.py
LetterType = Literal["cgmp_finished", "api", "compounding", "unapproved_misbranded"]
RULES_VERSION: int = 1


def letter_type(subject: str) -> LetterType | None: ...  # pure; None = out of scope
def rules_sha256() -> str: ...


# src/regintel/collect/http.py
@dataclass(frozen=True)
class FetchPolicy:
    min_interval_s: float = 30.0  # between request *starts*, retries included
    max_attempts: int = 4
    backoff_base_s: float = 30.0  # 30, 60, 120; no jitter (deterministic)
    retry_after_cap_s: float = 300.0
    timeout_s: float = 60.0


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    body: bytes
    retrieved_at: datetime  # UTC, tz-aware
    attempts: int


class BlockedError(RuntimeError): ...  # 403 (client), or 3 consecutive unexpected pages (run)


class FetchFailed(RuntimeError): ...  # retries exhausted


class PoliteClient:
    def __init__(
        self,
        policy: FetchPolicy,
        user_agent: str,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = ...,
    ) -> None: ...
    def get(self, url: str, params: Mapping[str, str | int] | None = None) -> FetchResult: ...
```

Retry and stop policy:
- **Retried** (up to `max_attempts`, honouring `Retry-After` up to the cap): 429, 500, 502, 503, 504, timeouts and connection errors.
- **403**: raises `BlockedError` at once, with no retry. The run pushes what it has and exits with code 2.
- **404**: returned to the caller, which records it in `skipped.jsonl` with reason `http_404`.
- **Unexpected pages**: the *run* checks each 200 with `looks_like_letter`. A failing page is logged, counted and not stored. It is also not recorded as skipped, so it is retried next run. After 3 in a row the run raises `BlockedError`, since a challenge page is the likely cause.

```python
# src/regintel/collect/listing.py
LISTING_URL = "https://www.fda.gov/datatables/views/ajax"
# fixed params: view_name=warning_letter_solr_index, view_display_id=warning_letter_solr_block,
#               start, length=500, draw=1


@dataclass(frozen=True)
class ListingRow:
    letter_id: str
    url: str
    posted_date: date
    issue_date: date | None
    company: str  # html-unescaped, tags stripped, whitespace collapsed
    issuing_office: str  # may be "" (2 in-scope rows have no office)
    subject: str
    response_letter_url: str | None
    closeout_url: str | None
    closeout_date: date | None


class ListingSchemaError(ValueError): ...


def parse_listing_page(payload: object) -> tuple[int, list[ListingRow]]: ...  # pure
def dedupe_rows(rows: Sequence[ListingRow]) -> tuple[list[ListingRow], int]: ...  # pure
def fetch_listing(client: PoliteClient, page_size: int = 500) -> list[ListingRow]: ...
```

`parse_listing_page` raises `ListingSchemaError` on any of these:
- the payload is not a dict with an int `recordsTotal` and a list `data`
- a row does not have exactly 8 cells
- no `href` in the company cell
- a date that is not `MM/DD/YYYY` (it uses the displayed text, not the `datetime` attribute, which carries a timezone artefact)
- an empty subject

An empty issuing office is allowed, because it occurs in real in-scope rows.

`fetch_listing` pages until `start >= recordsTotal`. It then applies these checks:
- `recordsTotal` did not change between pages
- the **row count** equals `recordsTotal`
- after `dedupe_rows`, no `letter_id` appears twice with *different* fields. Identical duplicates are dropped and counted.

A pass is trusted when it passes these checks and either has no duplicates or has the same letter ids as the pass before it, since a row shifting across a page boundary looks exactly like FDA's genuine duplicate rows while hiding a missing row. It makes up to 3 passes, then raises. Separately, it raises `ListingSchemaError` if the listing has 0 rows or 0 in-scope rows: an empty result means drift or a block, not "nothing new".

```python
# src/regintel/collect/page.py
def looks_like_letter(html: bytes) -> bool: ...  # has "<title>… | FDA" and an "Issuing Office:" dt


# src/regintel/collect/manifest.py   (pydantic v2 models; extra="forbid")
class ManifestLine(BaseModel):
    schema_version: Literal[1]
    letter_id: str
    url: str
    retrieved_at: datetime  # UTC
    sha256: str  # hex of raw body bytes
    bytes: int
    http_status: int
    path: str  # raw/letters/<letter_id>/<sha256>.html
    # ListingRow minus letter_id/url, as seen at fetch time
    listing: ListingFields
    letter_type: LetterType  # from the subject, at fetch time
    rules_version: int
    rules_sha256: str
    run_id: str  # <UTC timestamp>-<8 hex>
    collector_version: str


class SkipLine(BaseModel):
    schema_version: Literal[1]
    letter_id: str
    url: str
    retrieved_at: datetime
    reason: Literal["http_404"]
    run_id: str


def parse_manifest(text: str) -> list[ManifestLine]: ...  # raises on bad line / dup (id, sha)
def serialise(lines: Sequence[BaseModel]) -> str: ...  # JSONL, sorted keys, trailing \n


# src/regintel/store/base.py
class Store(Protocol):
    def head_revision(self) -> str: ...
    def read_bytes(self, path: str, revision: str) -> bytes | None: ...
    def exists(self, path: str, revision: str) -> bool: ...
    def commit(self, additions: Mapping[str, bytes], message: str, parent_revision: str) -> str: ...


class AppendOnlyViolation(RuntimeError): ...


class ConcurrentWriteError(RuntimeError): ...


def guarded_commit(
    store: Store, additions: Mapping[str, bytes], message: str, parent_revision: str
) -> str: ...
```

`guarded_commit` is the only write path, and it enforces two rules:
- **Appendable files** (`raw/manifest.jsonl`, `raw/skipped.jsonl`): the new bytes must start with the existing bytes at `parent_revision`.
- **Everything else under `raw/`, and `probe/`**: the path must not exist yet. The exception is identical bytes, which are dropped from the commit as a no-op.

It allows no deletions and no writes outside `raw/` and `probe/`.

```python
# src/regintel/store/hub.py
# HubStore(Store): huggingface_hub.HfApi; create_commit(parent_commit=...);
#   a conflict raises ConcurrentWriteError
class HubStore:
    def __init__(self, repo_id: str, token: str | None, api: HfApi | None = None) -> None: ...


def init_dataset(api: HfApi, repo_id: str) -> bool: ...  # create public repo if missing


# src/regintel/store/local.py
# LocalStore(Store): directory + revision counter file; used by tests and `collect --no-push`


# src/regintel/collect/run.py
@dataclass(frozen=True)
class CollectSummary:
    run_id: str
    rules_version: int
    listing_rows: int
    duplicate_rows_dropped: int
    in_scope_rows: int
    in_scope_by_type: dict[str, int]
    planned: int
    fetched: int
    new_manifest_lines: int
    unchanged_refetches: int
    skipped: dict[str, int]
    unexpected_pages: int
    commits: int
    blocked: bool
    dataset_revision_before: str
    dataset_revision_after: str


def plan_fetches(
    in_scope: Sequence[ListingRow],
    manifest: Sequence[ManifestLine],
    skipped: Sequence[SkipLine],
    previous_snapshot: Sequence[ListingRow] | None,
) -> list[ListingRow]: ...  # pure; newest posted_date first, ties by letter_id


def collect(
    settings: Settings,
    client: PoliteClient,
    store: Store,
    *,
    max_fetches: int | None,
    batch_size: int = 50,
) -> CollectSummary: ...


# src/regintel/probe.py
def probe(client: PoliteClient, url: str) -> ProbeRecord: ...


#   ProbeRecord: run_id, github_run_id, runner (env), listing{status, bytes, sha256, records_total},
#   letter{url, final_url, status, bytes, sha256, looks_like_letter, attempts, elapsed_s},
#   blocked, retrieved_at
```

### CLI (`src/regintel/cli.py`, argparse, `[project.scripts] regintel = "regintel.cli:main"`)

| Command | Does | Exit |
|---|---|---|
| `regintel store init` | Creates `alasdo/regintel-data` as a **public** dataset if missing (idempotent). | 0 |
| `regintel collect [--max-fetches N] [--batch-size 50] [--min-interval 30] [--no-push]` | Runs as described above and prints `CollectSummary` as JSON on stdout. `--no-push` uses `LocalStore(data/cache/local-dataset)`. `--min-interval` below 30 is refused (robots.txt). | 0 ok; 2 blocked; 3 concurrent write; 1 other |
| `regintel probe [--url URL] [--push]` | Fetches the listing with `length=10`, then the letter 30 s later, and prints the `ProbeRecord` JSON. `--push` commits `probe/<run_id>.json`. | 0 letter ok; 2 blocked or not a letter |

The logs use `logging` and never print the token. `HfApi` gets the token only through its constructor.

### Probe workflow (`.github/workflows/probe.yml`)

- `on: workflow_dispatch` only, with an input `url`. The default is the current drug CGMP letter to kdc/one Chatsworth, Inc. (`CGMP/Finished Pharmaceuticals/Adulterated`, CDER, issued 2026-09-08): `https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/kdcone-chatsworth-inc-733205-09082026`.
- `permissions: contents: read`. `env: HF_TOKEN: ${{ secrets.HF_TOKEN }}` only on the probe step.
- Steps: `actions/checkout` and `astral-sh/setup-uv`, both pinned by commit SHA; then `uv sync --extra collect --no-dev --frozen`; then `uv run regintel probe --url "$PROBE_URL" --push`, with `PROBE_URL: ${{ inputs.url }}` passed through `env`, not interpolated into the shell. The step always uploads the JSON as a workflow artifact, even on failure.

### Dependencies and tooling

- `[project.optional-dependencies] collect = ["httpx", "huggingface_hub", "pydantic>=2"]`
- dev group: add `respx` and `pyyaml` (for the workflow test)
- `make setup` becomes `uv sync --all-extras`
- `[tool.ruff]` gets `extend-exclude = ["specs"]`. Ruff formats Python code blocks in Markdown, and spec sketches are not meant to be lint-clean code.

Not used: BeautifulSoup/lxml, since the listing cells are tiny, uniform fragments handled with `html.parser`, and full HTML parsing belongs to slice 3. Also not used: requests-cache, since the manifest *is* the cache, and HTTP-level caching would hide refetches from provenance.

### Document amendments (task 1)

- **`docs/vision.md`**
  - *Corpus:* "every CDER warning letter to drug manufacturers from FY2019 onward" becomes "every drug warning letter on FDA's live warning-letter listing (posted from January 2021), selected by subject line (drug CGMP finished dose, API, compounding, and finished-pharmaceutical unapproved/misbranding letters), whichever FDA office issued it".
  - *Data-source table:* same change.
  - *Opening paragraph:* the example "since 2019" becomes "since 2021".
  - *Limitations:* add "Window: FY2019–FY2020 letters are not on FDA's live listing and are not collected, so trends start in FY2021. FY2021 is partial (letters issued from 22 January 2021). Year-over-year comparisons involving FY2021 are marked partial." Also add "Scope is set by subject line; letters whose subject omits drug-manufacturing terms (for example pure 'Unapproved New Drugs/Misbranded', telehealth and COVID-19 letters) are out of scope."
- **`specs/ROADMAP.md`**
  - *Day 1 demo:* "FY2019→ CDER listing" becomes "live-listing (2021→) drug letters". "a 2019 letter and a 2025 letter" becomes "a 2021 letter and a 2025 letter".
  - *Exit criteria:* "at least one per FY 2019–2026" becomes "FY 2021–2026".
  - *Slices:* slice 4 notes that the letter-type rules already exist (`regintel.letter_type`, from this spec).
- **`docs/decisions/0001-architecture.md`**
  - *Dataset layout:* adds `raw/listing/<ts>-<sha8>.jsonl.gz`, `raw/skipped.jsonl` and `probe/<run_id>.json`.
  - *"Where things run" table:* notes that the collector filters by the subject rule table before fetching.
  - *Parse fixture years:* become FY 2021–2026.
  - *Metadata:* `letter_type` comes from `regintel.letter_type`, shared with the collector.

### Key decisions and rejected alternatives

- **Listing via the DataTables JSON endpoint.** The XLSX export was rejected because it has no letter URLs and caps at 1,000 rows. Scraping the rendered HTML table was rejected because it paginates client-side.
- **Window equals the live listing.** A Wayback-derived seed list for FY2019–2020 was rejected by the owner: its coverage cannot be verified, and it adds a second discovery path.
- **Scope by subject line, before fetching.** Filtering by CDER office was rejected, because it drops 190 ORA-issued drug CGMP letters (spot check above). Fetching everything and filtering after was rejected: about 5× the requests at 30 s each.
- **One rule table shared by collector and parser.** Scope and letter type cannot drift apart. Its version and hash are on every manifest line.
- **Honour `Crawl-Delay: 30`.** This costs about 6 h of backfill, which is resumable and runs on the PC.
- **Listing snapshots in addition to listing fields on manifest lines.** They capture later close-outs without refetching letters, and they keep every scope decision auditable.
- **Optimistic concurrency (`parent_commit`) instead of locks.** A concurrent writer fails loudly with exit code 3 and no retry.

## Acceptance checks

Automated. All of these run under `make check`, offline, with fixtures in `tests/fixtures/collect/`. The fixtures are real responses captured once and trimmed. `respx` refuses unmocked requests.

- [ ] `tests/test_letter_type.py::test_rules_match_golden_subjects`: every row of `subjects_2026-09-27.csv` gives its expected `letter_type`, and the kept total is 674.
- [ ] `tests/test_letter_type.py::test_spot_check_rows_in_scope`: the 8 spot-check subjects and offices above are all in scope, and the 4 ORA-issued ones are included.
- [ ] `tests/test_letter_type.py::test_exclusions_win`: `CGMP/QSR/Drug/Medical Devices/Adulterated` and `CGMP/Dietary Supplement/Adulterated` give `None`, and `Unapproved New Drug/Compounding/Misbranding` gives `compounding`.
- [ ] `tests/test_letter_type.py::test_rules_sha_pinned`: `rules_sha256()` equals the value committed in the test, so changing a rule forces a visible test update and a `RULES_VERSION` bump.
- [ ] `tests/collect/test_listing.py::test_parse_listing_page_golden`: `listing_page.json` (real, trimmed to ~15 rows) gives `listing_page.expected.json`. The fixture includes the `(CDER)`, `| CDER` and ORA office variants, an empty office, a close-out cell, `<br />` in a subject, `&amp;`/`&#039;` in a company, and the identical Lone Pine Farm duplicate.
- [ ] `tests/collect/test_listing.py::test_schema_drift_fails`: each of 7 cells, a missing href, a bad date, an empty subject and a missing `recordsTotal` raises `ListingSchemaError`.
- [ ] `tests/collect/test_listing.py::test_fetch_listing_paginates`, `::test_fetch_listing_detects_shift_then_recovers`, `::test_recordstotal_change_persisting_raises`, `::test_fetch_listing_raises_when_shift_persists`, `::test_shift_disguised_as_duplicate_is_refetched`: pages are joined in order, and shifts are detected and re-read, raising after 3 inconsistent passes.
- [ ] `tests/collect/test_listing.py::test_identical_duplicates_dropped_conflicting_raise`
- [ ] `tests/collect/test_listing.py::test_empty_listing_fails`: 0 rows, or 0 in-scope rows, raise `ListingSchemaError`.
- [ ] `tests/collect/test_http.py::test_min_interval_between_request_starts`: with a fake clock and sleep, 3 GETs, including a retried one, are ≥ 30 s apart.
- [ ] `tests/collect/test_http.py::test_retries_then_succeeds` (503, 503, 200 → attempts 3, backoff 30, 60), `::test_honours_retry_after_capped`, `::test_gives_up_after_max_attempts` (`FetchFailed`), `::test_403_raises_blocked_without_retry` (exactly 1 request).
- [ ] `tests/collect/test_page.py::test_looks_like_letter`: a real letter fixture gives True. An Akamai-style "Access Denied" body and an empty body give False.
- [ ] `tests/store/test_guard.py::test_manifest_must_be_prefix_extension`: rewriting an earlier manifest line raises `AppendOnlyViolation`, and nothing is committed.
- [ ] `tests/store/test_guard.py::test_existing_raw_path_not_overwritten`: different bytes raise. Identical bytes are a no-op. Paths outside `raw/` and `probe/` raise.
- [ ] `tests/store/test_hub.py::test_parent_commit_conflict_raises_concurrent_write` (fake `HfApi`), `::test_init_dataset_idempotent_public` (creates with `private=False` once; the second call returns False).
- [ ] `tests/collect/test_run.py::test_first_run_fetches_only_in_scope`: a mocked listing with 3 in-scope rows (one ORA-issued) and 2 out-of-scope rows (one CDER telehealth, one device) gives 3 HTML files, 3 manifest lines and 1 snapshot. The out-of-scope URLs are never requested (respx call count 0), and `in_scope_by_type` is correct.
- [ ] `tests/collect/test_run.py::test_second_run_is_noop`: the same mocks rerun give `new_manifest_lines == 0`, 0 letter requests, 0 new commits, and a byte-identical dataset.
- [ ] `tests/collect/test_run.py::test_repost_same_sha_adds_nothing` and `::test_repost_new_sha_appends`: after a changed `posted_date`, the refetch appends a new file and line only when the sha differs, the old file is unchanged, and a third run does not refetch.
- [ ] `tests/collect/test_run.py::test_404_recorded_and_not_retried`
- [ ] `tests/collect/test_run.py::test_crash_resume_pushes_pending_with_original_timestamp`: a store that fails on the 2nd batch commit leaves pending entries. The next run pushes them with the original `retrieved_at` and does not refetch them.
- [ ] `tests/collect/test_run.py::test_blocked_mid_run_pushes_progress_and_exits_2`: the CLI exit code is 2, and letters fetched before the 403 are committed. `::test_three_unexpected_pages_blocks` covers the other stop condition.
- [ ] `tests/collect/test_run.py::test_manifest_invariants` (property check over every run test's output):
  - `(letter_id, sha256)` is unique
  - every `path` exists
  - the sha256 of each stored file equals its line's `sha256`
  - `retrieved_at` is tz-aware UTC
  - `letter_type` equals `letter_type(listing.subject)`
  - `parse_manifest` round-trips
- [ ] `tests/collect/test_run.py::test_plan_order_deterministic`: `plan_fetches` on shuffled inputs gives an identical ordered plan.
- [ ] `tests/test_probe.py::test_probe_ok_record`, `::test_probe_blocked_exits_2_and_still_pushes`, and `::test_probe_record_never_contains_token` (with `HF_TOKEN=hf_test_sentinel`, the serialised record and captured logs do not contain the sentinel).
- [ ] `tests/test_workflows.py::test_probe_workflow_shape`: parsing `probe.yml` shows the only trigger is `workflow_dispatch` and `permissions == {"contents": "read"}`. `HF_TOKEN` comes from `secrets.HF_TOKEN` and appears only in the probe step's `env`. Every `uses:` is pinned to a 40-hex SHA, `inputs.url` is never interpolated in a `run:` string, and the default URL has a subject in scope.
- [ ] `tests/test_cli.py::test_min_interval_below_30_refused`: exit code 1 and nothing is fetched.
- [ ] `make check` passes (ruff, mypy strict, pytest), with `specs/` excluded from ruff.

Manual. These are observable once, need network and credentials, and are not automatable offline:

- [ ] M1: `uv run regintel store init` prints `created` and a second run prints `exists`. `https://huggingface.co/datasets/alasdo/regintel-data` is public.
- [ ] M2: dispatch **Probe fda.gov** from the Actions tab. The log shows the listing and letter status, bytes, sha256 and `looks_like_letter`, and `probe/<run_id>.json` appears on the Dataset. The outcome (blocked or not) is recorded in the PR description. If blocked, a short fallback note is added under `docs/decisions/` before Day 5, as the roadmap requires.
- [ ] M3: `uv run regintel collect --max-fetches 5` pushes 5 letters (`new_manifest_lines: 5`, `in_scope_rows` ≈ 674 or more). A second run with `--max-fetches 0` prints `new_manifest_lines: 0` and `fetched: 0`.

## Implementation notes (deviations from the sketches above)

These are recorded here so the spec stays the contract. All came out of implementation or the independent review.

- **Store protocol additions:** `identity` (keys the pending cache per destination) and `list_paths(prefix, revision)` (finds the latest snapshot).
- **Return values and client:**
  - `fetch_listing` returns `(rows, duplicates_dropped)`.
  - `PoliteClient` gains `now()` and an optional `on_request` hook. It waits in an httpx request hook, so redirect hops are spaced too. A redirect loop raises `FetchFailed`.
  - `FetchResult` gains `elapsed_s`, the time fda.gov took, excluding our own wait.
- **Summary and probe records:**
  - `CollectSummary` gains `failed` and `out_of_scope_drug_like`. Only *newly seen* out-of-scope CGMP/Pharm subjects are logged.
  - `ProbeRecord` adds `ok`, `runner_os`, `runner_name` and `error`.
- **Rules hash:** `rules_sha256()` hashes the rule content (patterns, order, flags, `NORMALISER_VERSION`), not module source. `PET` is word-bounded. `RULES_VERSION` stays 1 because no data had been published under the earlier hash.
- **Hub errors:**
  - `HubStore.read_bytes` treats only a real 404 (`RemoteEntryNotFoundError`) as "absent". Outages propagate, so the append-only guard can never see a missing manifest.
  - A failed commit is a `ConcurrentWriteError` whenever the head has moved, whatever the status code.
- **Probe:** `regintel probe --push` exits 3 (concurrent write) or 1 (Hub/OS error) after printing the record. The workflow disables persisted checkout credentials and pins the uv version.

## Task breakdown

1. **Scaffold and document amendments.**
   - Add the `collect` extra, the dev deps, the `regintel` script entry and `extend-exclude = ["specs"]` to `pyproject.toml`. Set `setup` in `Makefile` to `--all-extras`. Add `HF_TOKEN` and `REGINTEL_DATASET` to `.env.example`.
   - Write `src/regintel/config.py` and a `src/regintel/cli.py` skeleton.
   - Apply the amendments to `docs/vision.md`, `specs/ROADMAP.md` and `docs/decisions/0001-architecture.md`, as listed above.

   *Files:* `pyproject.toml`, `uv.lock`, `Makefile`, `.env.example`, `src/regintel/{config,cli}.py`, `tests/test_config.py`, `docs/vision.md`, `specs/ROADMAP.md`, `docs/decisions/0001-architecture.md`
2. **Letter-type rule table.** Build the golden subjects fixture from the captured listing. *Files:* `src/regintel/letter_type.py`, `tests/test_letter_type.py`, `tests/fixtures/collect/subjects_2026-09-27.csv`
3. **Polite HTTP client and page check.** *Files:* `src/regintel/collect/{__init__,http,page}.py`, `tests/collect/test_http.py`, `tests/collect/test_page.py`, `tests/fixtures/collect/{letter_cgmp.html,access_denied.html}`
4. **Listing parser, dedupe and pagination.** Capture and trim real fixtures. *Files:* `src/regintel/collect/listing.py`, `tests/collect/test_listing.py`, `tests/fixtures/collect/listing_page*.json`
5. **Store and append-only guard.** Local and hub implementations, plus `store init`. *Files:* `src/regintel/store/{__init__,base,local,hub}.py`, `tests/store/test_guard.py`, `tests/store/test_hub.py`
6. **Manifest models and the collect run.** Covers the plan, pending cache, batching, snapshots, skip lines, the summary and the CLI `collect`. *Files:* `src/regintel/collect/{manifest,run}.py`, `src/regintel/cli.py`, `tests/collect/test_run.py`, `tests/test_cli.py`
7. **Probe command and workflow.** *Files:* `src/regintel/probe.py`, `src/regintel/cli.py`, `.github/workflows/probe.yml`, `tests/test_probe.py`, `tests/test_workflows.py`
8. **Live checks M1–M3.** The owner runs `store init` and dispatches the probe. Record the outcomes in the PR, and add a fallback note in `docs/decisions/` if blocked. *Files:* none, or `docs/decisions/0002-collection-fallback.md` if blocked.

## Risks and open questions

**Open, needing owner confirmation before approval:**
1. **Unapproved/misbranding letters are kept only when the subject says "Finished Pharmaceutical".** That gives 109 rows. The 106 CDER `Unapproved New Drugs/Misbranded` letters without it, plus the telehealth and COVID letters, are out. The vision's sample wants "a few unapproved/misbranding letters", and FY2025–2026 have only 1 such row, so the sample stratum for this type is thin in recent years.
2. **`Nonprescription/OTC` (38 CDER rows) is out of scope.** These are OTC monograph letters, some to manufacturers (for example Macau-Union Pharmaceutical Limited). Should they be in?

**Risks:**
- **Thin strata for sampling (slice 5).** API has 4 letters in FY2021 and 4 in FY2024, and unapproved/misbranding has 1 in FY2025 and 0 in FY2026. The FY × type stratification needs a rule for small cells (for example merge FY pairs or take all). That rule belongs to the slice 5 spec, but the numbers are known now.
- **The subject line is FDA free text.** New phrasings can appear, for example `CGMP/Finished Pharmaceutical` without the s, or `CGMP/Drugs/Adulterated/OTC`. The golden subjects table catches regressions but not new phrasings. *Mitigation:* `CollectSummary` also reports the count of out-of-scope rows whose subject contains `CGMP` or `Pharm`, and a new such subject appears in the weekly log for review.
- **The listing endpoint is undocumented** (Drupal Views AJAX) and may change without notice. *Mitigation:* schema-drift errors abort before any write, and the probe exercises the endpoint.
- **Bot protection.** Runner IPs may be blocked (the probe answers this), and so could the PC during a ~6 h backfill. *Mitigation:* stop on the first 403 or after 3 unexpected pages, then resume later. There is no evasion: the User-Agent stays honest and no headless browser is used.
- **Raw-HTML sha256 includes page chrome** (for example "Content current as of"). Hashes are therefore per page version. Reposts will almost always produce a new version, and text-level dedup belongs to parse.
- **The public Dataset means every push is immediately public.** Records hold only public URLs, hashes and runner metadata, and `test_probe_record_never_contains_token` covers the token.
- **Lost FY2019–FY2020.** Trends start in FY2021 (partial). This is stated in the vision's limitations and cannot be recovered without a second discovery path, which the owner rejected.
