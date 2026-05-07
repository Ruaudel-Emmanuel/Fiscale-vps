// Configuration API
const apiBase = "https://...";

// Références DOM
const linesContainer = document.getElementById("lines-container");
const addLineBtn = document.getElementById("add-line-btn");
const form = document.getElementById("invoice-form");
const statusBox = document.getElementById("status-box");

// Totaux
const subtotalDisplay = document.getElementById("subtotal-display");
const vatDisplay = document.getElementById("vat-display");
const totalDisplay = document.getElementById("total-display");

// Template de ligne
const lineTemplate = document.getElementById("line-template");

// -------- Outils --------

function formatMoney(value) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(Number(value || 0));
}

function showStatus(message, type = "info") {
  statusBox.textContent = message;
  statusBox.className = `status-box status-${type}`;
}

// -------- Gestion des lignes --------

function updateLineTotal(lineEl) {
  const qtyInput = lineEl.querySelector(".line-quantity-input");
  const unitInput = lineEl.querySelector(".line-unit-price-input");
  const totalEl = lineEl.querySelector(".line-total-display");

  const qty = Number(qtyInput.value || 0);
  const unit = Number(unitInput.value || 0);
  const total = qty * unit;

  totalEl.textContent = formatMoney(total);
}

function updateTotals() {
  const lines = getLinesData();

  const subtotal = lines.reduce(
    (sum, line) => sum + line.quantity * line.unitPrice,
    0
  );
  const vat = lines.reduce(
    (sum, line) => sum + line.quantity * line.unitPrice * (line.vatRate / 100),
    0
  );
  const total = subtotal + vat;

  subtotalDisplay.textContent = formatMoney(subtotal);
  vatDisplay.textContent = formatMoney(vat);
  totalDisplay.textContent = formatMoney(total);
}

function createLine() {
  const fragment = lineTemplate.content.cloneNode(true);
  const lineEl = fragment.querySelector(".line-item");

  const inputs = lineEl.querySelectorAll("input, select");
  const removeBtn = lineEl.querySelector(".remove-line-btn");

  inputs.forEach((input) => {
    input.addEventListener("input", () => {
      updateLineTotal(lineEl);
      updateTotals();
    });
  });

  removeBtn.addEventListener("click", () => {
    lineEl.remove();
    updateTotals();
  });

  // Calcul initial du total de la ligne
  updateLineTotal(lineEl);

  return fragment;
}

function addLine() {
  const line = createLine();
  linesContainer.appendChild(line);
  updateTotals();
}

function getLinesData() {
  const items = Array.from(document.querySelectorAll(".line-item"));
  return items.map((item) => ({
    description: item
      .querySelector(".line-description-input")
      .value.trim(),
    quantity: Number(
      item.querySelector(".line-quantity-input").value || 0
    ),
    unitPrice: Number(
      item.querySelector(".line-unit-price-input").value || 0
    ),
    vatRate: Number(
      item.querySelector(".line-vat-rate-input").value || 0
    ),
  }));
}

// -------- Construction du payload --------

function buildPayload() {
  const lines = getLinesData();

  if (lines.length === 0) {
    throw new Error("Ajoute au moins une ligne de facture.");
  }

  for (const line of lines) {
    if (!line.description) {
      throw new Error("Chaque ligne doit avoir une description.");
    }
    if (line.quantity <= 0) {
      throw new Error("La quantité doit être supérieure à 0.");
    }
    if (line.unitPrice < 0) {
      throw new Error("Le prix unitaire ne peut pas être négatif.");
    }
  }

  return {
    invoiceNumber: document
      .getElementById("invoiceNumber")
      .value.trim(),
    invoiceDate: document.getElementById("invoiceDate").value,
    serviceDate: document.getElementById("serviceDate").value,
    currency: "EUR",
    sellerName: document.getElementById("sellerName").value.trim(),
    sellerAddress: document
      .getElementById("sellerAddress")
      .value.trim(),
    sellerVat: document.getElementById("sellerVat").value.trim(),
    buyerName: document.getElementById("buyerName").value.trim(),
    buyerAddress: document
      .getElementById("buyerAddress")
      .value.trim(),
    buyerSiren: document.getElementById("buyerSiren").value.trim(),
    paymentTerms: document
      .getElementById("paymentTerms")
      .value.trim(),
    paymentMethod: document
      .getElementById("paymentMethod")
      .value.trim(),
    notes: document.getElementById("notes").value.trim(),
    lines,
  };
}

// -------- Appel API --------

async function generateInvoice(payload) {
  const response = await fetch(`${apiBase}/generate-facturx`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Erreur API (${response.status}) : ${errorText}`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "invoice-facturx.pdf";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// -------- Événements --------

addLineBtn.addEventListener("click", (event) => {
  event.preventDefault();
  addLine();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showStatus("", "info");

  try {
    const payload = buildPayload();
    showStatus("Génération de la facture en cours...", "info");

    await generateInvoice(payload);

    showStatus("Facture générée avec succès.", "success");
  } catch (error) {
    console.error(error);
    showStatus(error.message || "Erreur inattendue.", "error");
  }
});

// -------- Initialisation --------

addLine();
updateTotals();
showStatus("Remplis le formulaire puis génère ta facture.", "info");
