document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const message = form.getAttribute("data-confirm") || "Confirmar esta ação?";
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

  document.querySelectorAll("[data-quick-create]").forEach((wrapper) => {
    const endpoint = wrapper.getAttribute("data-endpoint");
    const toggle = wrapper.querySelector("[data-quick-toggle]");
    const panel = wrapper.querySelector("[data-quick-panel]");
    const input = wrapper.querySelector("[data-quick-name]");
    const save = wrapper.querySelector("[data-quick-save]");
    const select = wrapper.querySelector("[data-quick-select]");
    const feedback = wrapper.querySelector("[data-quick-feedback]");

    if (!endpoint || !toggle || !panel || !input || !save || !select) {
      return;
    }

    toggle.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) {
        input.focus();
      }
    });

    save.addEventListener("click", async () => {
      const name = input.value.trim();
      if (name.length < 2) {
        if (feedback) {
          feedback.textContent = "Informe pelo menos 2 caracteres.";
        }
        input.focus();
        return;
      }

      const body = new FormData();
      body.append("name", name);
      save.disabled = true;
      if (feedback) {
        feedback.textContent = "Salvando...";
      }

      try {
        const response = await fetch(endpoint, {
          method: "POST",
          body,
          headers: { Accept: "application/json" },
        });
        const payload = await response.json();

        if (!response.ok) {
          throw new Error(payload.detail || "Não foi possível salvar.");
        }

        let option = Array.from(select.options).find((item) => item.value === String(payload.id));
        if (!option) {
          option = new Option(payload.name, payload.id);
          select.add(option);
        }
        option.selected = true;
        input.value = "";
        panel.hidden = true;
        if (feedback) {
          feedback.textContent = `${payload.name} adicionado.`;
        }
      } catch (error) {
        if (feedback) {
          feedback.textContent = error.message || "Não foi possível salvar.";
        }
      } finally {
        save.disabled = false;
      }
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        save.click();
      }
    });
  });
});
