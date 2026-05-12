document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const message = form.getAttribute("data-confirm") || "Confirmar esta acao?";
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  const search = document.querySelector("[data-patient-search]");
  const cards = document.querySelectorAll("[data-patient-card]");
  if (search && cards.length) {
    search.addEventListener("input", () => {
      const term = search.value.trim().toLowerCase();
      cards.forEach((card) => {
        const text = (card.getAttribute("data-search-text") || "").toLowerCase();
        card.hidden = term.length > 0 && !text.includes(term);
      });
    });
  }
});
