/* DialSize.com — Client-side search, table sorting & scroll hints */
(function() {
  'use strict';

  /* ---- Search ---- */
  var searchData = null;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function(c) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
    });
  }

  function initSearch() {
    var input = document.getElementById('ds-search');
    var results = document.getElementById('ds-search-results');
    if (!input || !results) return;

    function runSearch() {
      var q = input.value.trim().toLowerCase();
      var terms = q.split(/\s+/);
      if (q.length < 2 || !searchData) {
        results.classList.remove('active');
        results.innerHTML = '';
        return;
      }

      var matches = [];
      for (var i = 0; i < searchData.length && matches.length < 12; i++) {
        var w = searchData[i];
        var hay = (w.brand + ' ' + w.collection + ' ' + w.name + ' ' + w.reference).toLowerCase();
        var allMatch = true;
        for (var t = 0; t < terms.length; t++) {
          if (hay.indexOf(terms[t]) === -1) { allMatch = false; break; }
        }
        if (allMatch) matches.push(w);
      }

      if (matches.length === 0) {
        results.innerHTML = '<div class="sr-empty">No matches found</div>';
        results.classList.add('active');
        return;
      }

      var html = '';
      for (var j = 0; j < matches.length; j++) {
        var m = matches[j];
        html += '<a href="' + escapeHtml(m.url) + '">';
        html += '<span>' + escapeHtml(m.title || (m.brand + ' ' + m.name)) + '</span>';
        html += '<span class="sr-ref">' + escapeHtml(m.reference) + '</span>';
        html += '</a>';
      }
      results.innerHTML = html;
      results.classList.add('active');
    }

    /* Preload the index; re-run any query typed (or passed via ?q=) before it arrived */
    fetch('/search-index.json')
      .then(function(r) { return r.json(); })
      .then(function(d) { searchData = d; runSearch(); })
      .catch(function() { searchData = []; });

    /* Support the SearchAction target: /?q=omega+planet */
    var params = new URLSearchParams(window.location.search);
    if (params.get('q')) {
      input.value = params.get('q');
    }

    input.addEventListener('input', runSearch);
    input.addEventListener('focus', runSearch);

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
      var headers = table.querySelectorAll('th');
      headers.forEach(function(th, colIdx) {
        if (!th.classList.contains('sortable')) return;
        th.setAttribute('tabindex', '0');
        th.setAttribute('aria-sort', 'none');
        th.addEventListener('click', function() {
          sortTable(table, colIdx, th);
        });
        th.addEventListener('keydown', function(e) {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            sortTable(table, colIdx, th);
          }
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
      h.setAttribute('aria-sort', 'none');
    });
    th.classList.add(asc ? 'asc' : 'desc');
    th.setAttribute('aria-sort', asc ? 'ascending' : 'descending');

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

  /* ---- Scroll hints on wide tables ---- */
  function initTableScroll() {
    document.querySelectorAll('.table-wrap').forEach(function(wrap) {
      var scroller = wrap.querySelector('.table-scroll');
      if (!scroller) return;
      function update() {
        var max = scroller.scrollWidth - scroller.clientWidth;
        wrap.classList.toggle('fade-left', scroller.scrollLeft > 2);
        wrap.classList.toggle('fade-right', scroller.scrollLeft < max - 2);
      }
      scroller.addEventListener('scroll', update, {passive: true});
      window.addEventListener('resize', update);
      update();
    });
  }

  /* ---- Init ---- */
  document.addEventListener('DOMContentLoaded', function() {
    initSearch();
    initSort();
    initTableScroll();
  });
})();
