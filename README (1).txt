GEOLOGICAL DISASTER YOUTUBE COLLECTION — VERSION 2
Python 3.10+; no official YouTube Data API or API key.

Install (Windows terminal, inside this directory):
    py -m pip install -U -r requirements.txt
For yt-dlp's JavaScript runtime warning, install Deno and reopen the terminal:
    winget install DenoLand.Deno
    deno --version
Deno is external to Python. The requirements install yt-dlp's default extras.

Pilot (up to five preliminarily selected videos per country; up to 15 candidates):
    py scraper.py --countries CA JP BR --limit 5 --candidates 15 --comment-sample 5
    py analyze.py --limit 5

Full collection (after validating the pilot and obtaining permission for automated access):
    py scraper.py --limit 10 --candidates 30 --comment-sample 5
    py analyze.py --limit 10
For a different disaster:
    py scraper.py --profile earthquake.json --limit 10 --candidates 30 --comment-sample 5
    py analyze.py --profile earthquake.json --limit 10
Also included: tsunami.json, flood.json, hurricane.json. All five profiles have
localized search phrases for the 51 configured languages in countries.json.
Edit search_terms for actual queries; translations and terms remain the base
words for classification. The hurricane profile includes regional cyclone terms.
The search phrases are best-effort, not native-speaker verified.

NEW COLLECTION BEHAVIOR
--limit is a target for preliminarily selected videos, not guaranteed confirmed
actual incidents. --candidates is the maximum number of search results examined
per country (defaults to 3 x limit, capped at 100). Results retain original ranks.
The program skips obvious music, game or political-landslide titles, defers likely
compilations and educational content for review, and checks detailed metadata
before fetching optional transcripts and comment samples. It stops selecting once
the target is reached or the candidate pool is exhausted. Unexamined candidates
are retained for auditing. The analyzer considers selected, excluded and deferred
candidates; manually approved deferred rows may lack engagement details.

OUTPUTS AND RESUMING
The default output folder is research_data/<keyword>_<limit>_v2. This intentionally
keeps older data and checkpoints separate. Do not copy old state.json or manifest.json
into the new folders: search terms, sample design and cache schema have changed.
Use --output for another experiment; rerun exactly the same settings to resume.
The selected countries may be expanded on later runs; all other collection settings
must match. If changing candidate count, comment count, profile, etc., use a new
folder. On a rate limit or access restriction, the program saves and stops. Do not
resume until access is permitted. No restriction-circumvention mechanisms.

raw_candidates.csv: all returned unique IDs per search, including exclusions,
  deferrals and unexamined results. candidate_status and candidate_reason explain
  screening. Metadata is not collected for every raw candidate.
results.csv: preliminarily selected videos and any currently processing video.
coverage.csv: requested, candidate_limit, returned, selected, excluded, deferred,
  unexamined, collection_finished, metadata_ok and search status by country.
parsed.csv: analyzed selected and screened-out/deferred rows, not unexamined rows.
kept.csv: provisionally relevant regional rows, including manual overrides.
kept_unique.csv: deduplicated accepted video IDs.
review.csv: uncertain videos and reasons (including deferred candidates).
decisions.csv: edit manual_decision (keep/review/toss), event_country, event_date,
  event_id, manual_notes. Save, close Excel and rerun analyze.py.
summary.csv: country-of-search counts and engagement for accepted rows, not event
  country or true event frequency. Use --strict for manually approved keeps only.
state.json: raw data/checkpoints; manifest.json: collection settings.
Close CSV files in Excel before running the programs.

To reanalyze the old pilot with new rules without making YouTube requests, copy its
CSV into a separate folder and use:
    py analyze.py --profile landslide.json --input path/to/old/results.csv
Outputs are written alongside that CSV; use a copy to preserve previous analyses.

LIMITATIONS
Search country is not event country. Event location/date/ID require independent
verification or manual assignment; channel country remains unpopulated. Search
terms and title rules may bias the sample toward more prominent disaster reports;
use a consistent protocol and keep the raw/coverage outputs. Search ranking is
YouTube's default, not a fixed date window. A fixed target cannot establish actual
regional event frequency. Global engagement is not local viewership or physical
impact. Transcript/comment access and counts vary; blanks are missing, not zero.
The classifier is heuristic and can miss or misclassify videos. Live collection
with the revised queries is not verified; test on three countries first. Automated
collection requires permission under YouTube's terms. Respect access restrictions.

Offline tests:
    py -m unittest -v test_offline
