The source code to [Jin-Chuan Shi's public academic website](https://chuan-10.github.io/).

Publication stars are fetched from GitHub, and citation counts come from the
Google Scholar author profile. A GitHub Actions workflow refreshes the citation
snapshot weekly and stores it on the `scholar-metrics` branch; the website reads
that branch directly and falls back to the last published snapshot. LEGaussians
shows the sum of its CVPR and TPAMI records. If Google Scholar blocks a request,
the previous snapshot is retained and older data is marked as cached.

If direct requests from GitHub Actions are blocked, an optional `SERPAPI_API_KEY`
repository secret enables the Google Scholar Author API instead. The key is only
used by the workflow and is never included in the website or published data.
