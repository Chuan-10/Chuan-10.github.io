The source code to [Jin-Chuan Shi's public academic website](https://chuan-10.github.io/).

Publication stars are fetched from GitHub, and citation counts come from the
Google Scholar author profile. A weekly local Codex automation runs
`python3 scripts/publish_scholar.py` and updates only the `scholar-metrics`
branch. The website reads that branch directly and falls back to the last
published snapshot. LEGaussians shows the sum of its CVPR and TPAMI records.
If Google Scholar blocks a request, the previous snapshot is retained and
older data is marked as cached. The local machine and Codex must be available
for the scheduled task to run.

The GitHub workflow can also be run manually with an optional `SERPAPI_API_KEY`
repository secret. The key is only used by that workflow and is never included
in the website or published data.
