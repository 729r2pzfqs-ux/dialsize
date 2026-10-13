/* DialSize.com — Client-side search & table sorting */
(function() {
  'use strict';

  /* ---- Search ---- */
  var searchData = null;

  function initSearch() {
    var input = document.getElementById('ds-search');
    var results = document.getElementById('ds-search-results');
    if (!input || !results) return;

    input.addEventListener('focus', function() {
      if (!searchData) {
        fetch('/search-index.json')
          .then(function(r) { return r.json(); })
          .then(function(d) { searchData = d; })
          .catch(function() { searchData = []; });
      }
    });

    input.addEventListener('input', function() {
      var q = this.value.trim().toLowerCase();
      if (q.length < 2 || !searchData) {
        results.classList.remove('active');
        results.innerHTML = '';
        return;
      }

      var matches = [];
      for (var i = 0; i < searchData.length && matches.length < 12; i++) {
        var w = searchData[i];
        var hay = (w.brand + ' ' + w.collection + ' ' + w.name + ' ' + w.reference).toLowerCase();
        if (hay.indexOf(q) !== -1) matches.push(w);
      }

      if (matches.length === 0) {
        results.innerHTML = '<div style="padding:.75rem 1rem;color:#888;font-size:.85rem;">No matches found</div>';
        results.classList.add('active');
        return;
      }

      var html = '';
      for (var j = 0; j < matches.length; j++) {
        var m = matches[j];
        html += '<a href="' + m.url + '">';
        html += '<span>' + m.brand + ' ' + m.name + '</span>';
        html += '<span class="sr-ref">' + m.reference + '</span>';
        html += '</a>';
      }
      results.innerHTML = html;
      results.classList.add('active');
    });

    document.addEventListener('click', function(e) {
      if (!input.contains(e.target) && !results.contains(e.target)) {
        results.classList.remove('active');
      }
    });

    input.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') {
        results.classList.remove('active');
        input.blur();
      }
    });
  }

  /* ---- Table sorting ---- */
  function initSort() {
    var tables = document.querySelectorAll('.specs-table');
    tables.forEach(function(table) {
      var headers = table.querySelectorAll('th.sortable');
      headers.forEach(function(th, colIdx) {
        th.addEventListener('click', function() {
          sortTable(table, colIdx, th);
        });
      });
    });
  }

  function sortTable(table, col, th) {
    var tbody = table.querySelector('tbody') || table;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    if (rows.length < 2) return;

    var asc = !th.classList.contains('asc');
    table.querySelectorAll('th.sortable').forEach(function(h) {
      h.classList.remove('asc', 'desc');
    });
    th.classList.add(asc ? 'asc' : 'desc');

    rows.sort(function(a, b) {
      var aVal = getCellValue(a, col);
      var bVal = getCellValue(b, col);
      var aNum = parseFloat(aVal);
      var bNum = parseFloat(bVal);
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return asc ? aNum - bNum : bNum - aNum;
      }
      return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });

    rows.forEach(function(row) { tbody.appendChild(row); });
  }

  function getCellValue(row, col) {
    var cell = row.querySelectorAll('td')[col];
    return cell ? cell.textContent.trim() : '';
  }

  /* ---- Cookie consent ---- */
  function initCookieConsent() {
    var banner = document.getElementById('cookie-banner');
    if (!banner) return;
    if (localStorage.getItem('ds_cookie_consent')) return;
    banner.classList.add('show');

    var acceptBtn = document.getElementById('cookie-accept');
    var rejectBtn = document.getElementById('cookie-reject');

    if (acceptBtn) {
      acceptBtn.addEventListener('click', function() {
        localStorage.setItem('ds_cookie_consent', 'accepted');
        banner.classList.remove('show');
        loadAnalytics();
      });
    }
    if (rejectBtn) {
      rejectBtn.addEventListener('click', function() {
        localStorage.setItem('ds_cookie_consent', 'rejected');
        banner.classList.remove('show');
      });
    }
  }

  function loadAnalytics() {
    /* GA4 loads via gtag in the page head with consent mode */
    if (typeof gtag === 'function') {
      gtag('consent', 'update', {
        'analytics_storage': 'granted',
        'ad_storage': 'granted',
        'ad_user_data': 'granted',
        'ad_personalization': 'granted'
      });
    }
  }

  /* ---- Init ---- */
  document.addEventListener('DOMContentLoaded', function() {
    initSearch();
    initSort();
    initCookieConsent();

    /* If consent was previously accepted, enable analytics */
    if (localStorage.getItem('ds_cookie_consent') === 'accepted') {
      loadAnalytics();
    }
  });
})();
