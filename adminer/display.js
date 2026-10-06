(() => {
  function initialize() {
    const header = document.querySelector('thead a[href$="order=Data_free"]');
    if (!header) return;
    const table = header.closest("table");
    const column = header.closest("th").cellIndex;

    for (const row of table.rows) {
      let position = 0;
      for (const cell of row.cells) {
        const span = cell.colSpan;
        if (position <= column && column < position + span) {
          if (span > 1) cell.colSpan = span - 1;
          else cell.style.display = "none";
          break;
        }
        position += span;
      }
    }

    const units = ["bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"];
    const numbers = new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 2,
    });
    function formatSizes() {
      const cells = table.querySelectorAll(
        '[id^="Data_length-"], [id^="Index_length-"], #sum-Data_length, #sum-Index_length',
      );
      for (const cell of cells) {
        const raw = cell.textContent.trim();
        if (!/^\d[\d,.\s]*$/.test(raw)) continue;
        const bytes = BigInt(raw.replace(/[,.\s]/g, ""));
        let size = Number(bytes);
        let unit = 0;
        while (size >= 1024 && unit < units.length - 1) {
          size /= 1024;
          unit++;
        }
        cell.title = `${bytes.toLocaleString("en-US")} bytes`;
        cell.textContent = `${numbers.format(size)} ${units[unit]}`;
      }
    }

    formatSizes();
    // Adminer fills table statistics asynchronously after the initial page load.
    new MutationObserver(formatSizes).observe(table, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
