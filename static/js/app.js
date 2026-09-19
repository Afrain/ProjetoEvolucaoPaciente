document.addEventListener("DOMContentLoaded", () => {
  const formatCpfCnpj = (value) => {
    const digits = value.replace(/\D/g, "").slice(0, 14);
    if (digits.length <= 11) {
      return digits
        .replace(/^(\d{3})(\d)/, "$1.$2")
        .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
        .replace(/\.(\d{3})(\d)/, ".$1-$2");
    }
    return digits
      .replace(/^(\d{2})(\d)/, "$1.$2")
      .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1/$2")
      .replace(/(\/\d{4})(\d)/, "$1-$2");
  };

  document.querySelectorAll("[data-cpf-cnpj-mask]").forEach((input) => {
    const applyMask = () => {
      input.value = formatCpfCnpj(input.value);
    };
    applyMask();
    input.addEventListener("input", applyMask);
  });

  document.querySelectorAll("[data-payment-form]").forEach((form) => {
    const condition = form.querySelector("[data-payment-condition]");
    const installmentFields = form.querySelectorAll("[data-installment-field]");
    const countInput = form.querySelector("[data-installment-count]");
    const schedule = form.querySelector("[data-installment-schedule]");
    const dateList = form.querySelector("[data-installment-date-list]");
    const datesJson = form.querySelector("[data-installment-dates-json]");
    if (!condition || !installmentFields.length) {
      return;
    }

    let installmentDates = [];
    if (schedule) {
      try {
        installmentDates = JSON.parse(schedule.getAttribute("data-existing-due-dates") || "[]");
      } catch (_) {
        installmentDates = [];
      }
    }

    const addMonthsKeepingDay = (isoDate, months) => {
      const parts = isoDate.split("-").map(Number);
      if (parts.length !== 3 || parts.some(Number.isNaN)) {
        return "";
      }
      const absoluteMonth = parts[1] - 1 + months;
      const year = parts[0] + Math.floor(absoluteMonth / 12);
      const month = ((absoluteMonth % 12) + 12) % 12;
      const lastDay = new Date(year, month + 1, 0).getDate();
      const day = Math.min(parts[2], lastDay);
      return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    };

    const syncDatesJson = () => {
      if (datesJson) {
        datesJson.value = JSON.stringify(installmentDates);
      }
    };

    const renderInstallmentDates = (regenerateFromFirst = false) => {
      if (!countInput || !dateList) {
        return;
      }
      const count = Number.parseInt(countInput.value, 10);
      if (!Number.isInteger(count) || count < 2 || count > 60) {
        installmentDates = [];
        dateList.innerHTML = '<p class="muted">Informe a quantidade de parcelas para definir os vencimentos.</p>';
        syncDatesJson();
        return;
      }

      if (regenerateFromFirst && installmentDates[0]) {
        installmentDates = Array.from({ length: count }, (_, index) => addMonthsKeepingDay(installmentDates[0], index));
      } else {
        installmentDates = installmentDates.slice(0, count);
        while (installmentDates.length < count) {
          const nextIndex = installmentDates.length;
          installmentDates.push(installmentDates[0] ? addMonthsKeepingDay(installmentDates[0], nextIndex) : "");
        }
      }

      dateList.innerHTML = "";
      installmentDates.forEach((value, index) => {
        const label = document.createElement("label");
        label.textContent = `${index + 1}ª parcela`;
        const input = document.createElement("input");
        input.type = "date";
        input.value = value || "";
        input.disabled = condition.disabled;
        input.addEventListener("change", () => {
          installmentDates[index] = input.value;
          if (index === 0 && input.value) {
            renderInstallmentDates(true);
          } else {
            syncDatesJson();
          }
        });
        label.appendChild(input);
        dateList.appendChild(label);
      });
      syncDatesJson();
    };

    const syncInstallments = () => {
      const isInstallment = condition.value === "Parcelado";
      installmentFields.forEach((field) => {
        field.hidden = !isInstallment;
        const input = field.querySelector("input");
        if (input) {
          input.disabled = !isInstallment || condition.disabled;
        }
      });
      if (datesJson) {
        datesJson.disabled = !isInstallment || condition.disabled;
      }
      if (isInstallment) {
        renderInstallmentDates(false);
      }
    };
    syncInstallments();
    condition.addEventListener("change", syncInstallments);
    if (countInput) {
      countInput.addEventListener("input", () => renderInstallmentDates(false));
    }
  });

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

  document.querySelectorAll("[data-episode-details]").forEach((details) => {
    const label = details.querySelector("[data-episode-toggle-label]");
    if (!label) {
      return;
    }
    const syncLabel = () => {
      label.textContent = details.open ? "Diminuir detalhes" : "Visualizar detalhes";
    };
    syncLabel();
    details.addEventListener("toggle", syncLabel);
  });
});
