(() => {
  'use strict';

  const cachePrefix = 'publication-metrics-v2:';
  const cacheLifetime = 6 * 60 * 60 * 1000;
  const staleAfter = 9 * 24 * 60 * 60 * 1000;
  const clockSkew = 5 * 60 * 1000;
  const requestTimeout = 10000;
  const format = new Intl.NumberFormat('en');
  const papers = [...document.querySelectorAll('.paper-metrics')];
  const expectedIds = [...new Set(papers.flatMap((paper) => paper.dataset.works.split(',')))];
  const scholarUrl = 'https://raw.githubusercontent.com/Chuan-10/Chuan-10.github.io/scholar-metrics/citation-counts.json';
  let scholarSnapshot;

  function isCount(value) {
    return Number.isSafeInteger(value) && value >= 0;
  }

  function readCache(key, componentCount) {
    try {
      const value = JSON.parse(localStorage.getItem(cachePrefix + key));
      if (!value || !isCount(value.count) || !Number.isFinite(value.updatedAt) ||
          !Number.isFinite(value.checkedAt) || value.updatedAt > Date.now() + clockSkew ||
          value.checkedAt > Date.now() || !Array.isArray(value.components) ||
          value.components.length !== componentCount || !value.components.every(isCount) ||
          value.components.reduce((total, count) => total + count, 0) !== value.count) {
        return null;
      }
      return value;
    } catch (_) {
      return null;
    }
  }

  function writeCache(key, value) {
    try {
      localStorage.setItem(cachePrefix + key, JSON.stringify(value));
    } catch (_) {
      // Counts still display when browser storage is unavailable.
    }
  }

  async function readJson(url) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), requestTimeout);
    try {
      const response = await fetch(url, { signal: controller.signal, credentials: 'omit' });
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      return await response.json();
    } finally {
      clearTimeout(timeout);
    }
  }

  function readScholarSnapshot() {
    if (!scholarSnapshot) {
      scholarSnapshot = Promise.allSettled([
        readJson(scholarUrl),
        readJson('citation-counts.json')
      ]).then((results) => {
        const snapshots = results.filter((result) => result.status === 'fulfilled')
          .map((result) => result.value)
          .filter((value) => value && value.source === 'Google Scholar' && value.citations &&
            Number.isFinite(Date.parse(value.updated_at)) && Date.parse(value.updated_at) <= Date.now() + clockSkew &&
            expectedIds.every((id) => isCount(value.citations[id])))
          .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
        if (!snapshots.length) throw new Error('No valid Google Scholar snapshot');
        return snapshots[0];
      });
    }
    return scholarSnapshot;
  }

  function render(element, value, source, labels, stale) {
    const formatted = format.format(value.count);
    const updated = new Date(value.updatedAt).toLocaleString('en', {
      year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
    });
    const breakdown = labels.length > 1
      ? ` (${labels.map((label, index) => `${label}: ${format.format(value.components[index])}`).join(' + ')})`
      : '';
    const note = stale ? '; temporarily showing cached data' : '';
    element.querySelector('[data-value]').textContent = formatted;
    element.dataset.stale = stale ? 'true' : 'false';
    element.title = `${source}${breakdown}; last updated ${updated}${note}`;
    if (source === 'GitHub stars') {
      element.setAttribute('aria-label', `${formatted} GitHub stars${stale ? ', cached' : ''}`);
    } else {
      element.setAttribute('aria-label', `${formatted} citations from Google Scholar${breakdown}${stale ? ', cached' : ''}`);
    }
  }

  function updateMetric(element, key, source, labels, fetchCounts) {
    const cached = readCache(key, labels.length);
    if (cached) render(element, cached, source, labels, Date.now() - cached.updatedAt > staleAfter);
    if (cached && Date.now() - cached.checkedAt < cacheLifetime) return;

    fetchCounts().then((result) => {
      const components = result.components;
      if (components.length !== labels.length || !components.every(isCount)) {
        throw new Error('Invalid metric data');
      }
      const count = components.reduce((total, value) => total + value, 0);
      if (!isCount(count) || !Number.isFinite(result.updatedAt) || result.updatedAt > Date.now() + clockSkew) {
        throw new Error('Invalid metric total or date');
      }
      const value = { count, components, updatedAt: result.updatedAt, checkedAt: Date.now() };
      writeCache(key, value);
      render(element, value, source, labels, Date.now() - value.updatedAt > staleAfter);
    }).catch(() => {
      if (cached) {
        render(element, cached, source, labels, true);
      } else {
        element.title = `${source} temporarily unavailable`;
      }
    });
  }

  papers.forEach((paper) => {
    const repo = paper.dataset.repo;
    const works = paper.dataset.works.split(',');
    const labels = paper.dataset.workLabels ? paper.dataset.workLabels.split(',') : works;
    const stars = paper.querySelector('[data-stars]');
    const citations = paper.querySelector('[data-citations]');

    updateMetric(stars, `github:${repo}`, 'GitHub stars', [repo], async () => {
      const result = await readJson(`https://api.github.com/repos/${repo}`);
      return { components: [result.stargazers_count], updatedAt: Date.now() };
    });

    updateMetric(citations, `scholar:${works.join(',')}`, 'Google Scholar citations', labels, async () => {
      const snapshot = await readScholarSnapshot();
      return { components: works.map((work) => snapshot.citations[work]), updatedAt: Date.parse(snapshot.updated_at) };
    });
  });
})();
