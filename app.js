const API_BASE_URL = "https://...";

const form = document.getElementById("invoice-form");
const linesContainer = document.getElementById("lines-container");
const addLineBtn = document.getElementById("add-line-btn");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status-box");

const subtotalDisplay = document.getElementById("subtotal-display");
const vatDisplay = document.getElementById("vat-display");
const totalDisplay = document.getElementById("total-display");

function formatEuro(value) {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR"
  }).format(Number(value || 0));
}

function toNumber(value) {
  const num = parseFloat(value);
  return Number.isFinite(num) ? num : 0;
}

function createLine(defaults = {}) {
  const tpl = document.getElementById("line-template");
  const node = tpl.content.firstElementChild.cloneNode(true);

  const descriptionInput = node.querySelector(".line-description-input");
  const quantityInput = node.querySelector(".line-quantity-input");
  const unitPriceInput = node.querySelector(".line-unit-price-input");
  const vatRateInput = node.querySelector(".line-vat-rate-input");
  const totalBox = node.querySelector(".line-total-display");
  const removeBtn = node.querySelector(".remove-line-btn");

  descriptionInput.value = defaults.description || "";
  quantityInput.value = defaults.quantity ?? 1;
  unitPriceInput.value = defaults.unitPrice ?? 350;
  vatRateInput.value = defaults.vatRate ?? 20;

  function updateLineTotal() {
    const quantity = toNumber(quantityInput.value);
    const unitPrice = toNumber(unitPriceInput.value);
    const lineTotal = quantity * unitPrice;
    totalBox.textContent = formatEuro(lineTotal);
    updateSummary();
  }

  quantityInput.addEventListener("input", updateLineTotal);
  unitPriceInput.addEventListener("input", updateLineTotal);
  vatRateInput.addEventListener("change", updateSummary);

  removeBtn.addEventListener("click", () => {
    node.remove();
    updateSummary();
  });

  updateLineTotal();
  linesContainer.appendChild(node);
}

function getLinesData() {
  const lineNodes = [...linesContainer.querySelectorAll(".line-item")];

  return lineNodes.map((lineNode) => ({
    description: lineNode.querySelector(".line-description-input").value.trim(),
    quantity: toNumber(lineNode.querySelector(".line-quantity-input").value),
    unitPrice: toNumber(lineNode.querySelector(".line-unit-price-input").value),
    vatRate: toNumber(lineNode.querySelector(".line-vat-rate-input").value)
  }));
}

function updateSummary() {
  const lines = getLinesData();

  const subtotal = lines.reduce((sum, line) => {
    return sum + line.quantity * line.unitPrice;
  }, 0);

  const vat = lines.reduce((sum, line) => {
    return sum + (line.quantity * line.unitPrice * line.vatRate / 100);
  }, 0);

  const total = subtotal + vat;

  subtotalDisplay.textContent = formatEuro(subtotal);
  vatDisplay.textContent = formatEuro(vat);
  totalDisplay.textContent = formatEuro(total);
}

function setStatus(type, message) {
  statusBox.className = "status-box";
  if (type) statusBox.classList.add(type);
  statusBox.textContent = message || "";
}

function getFilenameFromDisposition(disposition) {
  if (!disposition) return "facture-facturx.pdf";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match?.[1] || "facture-facturx.pdf";
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

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
    invoiceNumber: document.getElementById("invoiceNumber").value.trim(),
    invoiceDate: document.getElementById("invoiceDate").value,
    serviceDate: document.getElementById("serviceDate").value,
    currency: "EUR",
    sellerName: document.getElementById("sellerName").value.trim(),
    sellerAddress: document.getElementById("sellerAddress").value.trim(),
    sellerVat: document.getElementById("sellerVat").value.trim(),
    buyerName: document.getElementById("buyerName").value.trim(),
    buyerAddress: document.getElementById("buyerAddress").value.trim(),
    buyerSiren: document.getElementById("buyerSiren").value.trim(),
    paymentTerms: document.getElementById("paymentTerms").value.trim(),
    paymentMethod: document.getElementById("paymentMethod").value.trim(),
    notes: document.getElementById("notes").value.trim(),
    lines
  };
}

async function submitInvoice(event) {
  event.preventDefault();

  try {
    const payload = buildPayload();

    submitBtn.disabled = true;
    setStatus("loading", "Génération de la facture en cours...");

    const response = await fetch(`${API_BASE_URL}/generate-facturx`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/pdf"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      let errorMessage = "Erreur lors de la génération de la facture.";
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorMessage;
      } catch (_) {}
      throw new Error(errorMessage);
    }

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition");
    const filename = getFilenameFromDisposition(disposition);

    downloadBlob(blob, filename);
    setStatus("success", "Facture générée avec succès. Le téléchargement a démarré.");
  } catch (error) {
    setStatus("error", error.message || "Une erreur inconnue est survenue.");
  } finally {
    submitBtn.disabled = false;
  }
}

addLineBtn.addEventListener("click", () => {
  createLine({
    description: "",
    quantity: 1,
    unitPrice: 350,
    vatRate: 20
  });
});

form.addEventListener("submit", submitInvoice);

createLine({
  description: "Prestation de développement Python",
  quantity: 1,
  unitPrice: 350,
  vatRate: 20
});

const today = new Date().toISOString().slice(0, 10);
document.getElementById("invoiceDate").value = today;
document.getElementById("serviceDate").value = today;
document.getElementById("sellerName").value = "Rennesdev";
