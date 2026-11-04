The source code to [Jin-Chuan Shi's public academic website](https://chuan-10.github.io/).

A weekly local Codex automation runs `python3 scripts/publish_metrics.py`.
It updates GitHub star counts directly in the homepage and publishes citation
counts from the Google Scholar profile to the `scholar-metrics` branch. The
website displays stars without browser requests to GitHub and reads citations
from the data branch, falling back to the last published snapshot. LEGaussians
shows the sum of its CVPR and TPAMI records.

The updates run independently. If one source is unavailable, its previous
counts are retained and the automation reports the failure. The local machine
and Codex must be available, and the GitHub CLI (`gh`) must be signed in, for
the scheduled task to run. Only the homepage star numbers and citation data
are published; local untracked files are not included.

The GitHub workflow can also be run manually with an optional `SERPAPI_API_KEY`
repository secret. The key is only used by that workflow and is never included
in the website or published data.
