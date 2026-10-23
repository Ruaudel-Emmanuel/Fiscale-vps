# 🇫🇷 Factur-X Generator — Facturation électronique conforme EN 16931

> Générez des factures **PDF/A-3 avec XML embarqué** (norme Factur-X) en 3 clics.  
> **Frontend HTML + Backend Python** — zéro dépendance cloud, zéro abonnement.

---

## 🎯 Pourquoi ce projet existe

### Le problème
La **facturation électronique** devient obligatoire en France (loi 2026). Les TPE/PME doivent produire des factures au format **Factur-X** (PDF + XML dans un seul fichier PDF/A-3).  
Les solutions du marché sont soit :
- **chères** (abonnements SaaS),
- **complexes** (ERP surdimensionnés),
- **non conformes** (PDF simple + XML séparé = rejeté).

### La solution
Un générateur **100 % open source**, **local**, **conforme** :

| Avant (éditeur SaaS) | Après (Factur-X Generator) |
|---|---|
| 💶 20-50 €/mois d'abonnement | ☕ Gratuit, une installation |
| 🔒 Vos données fiscales chez un tiers | 🔐 Tout reste sur votre machine |
| ⏳ Formulaire lent, pas personnalisable | ⚡ Frontend HTML léger, modifiable |
| ❌ Pas de contrôle sur le format | ✅ Code ouvert, vous validez |

---

## ✨ Ce que ça fait (et ce que ça prouve)

| Compétence démontrée | Comment |
|---|---|
| **🐍 Python backend** | Génération PDF/A-3 + XML factur-x avec `reportlab` + `factur-x` |
| **🎨 Frontend HTML/JS** | Interface de saisie avec export JSON vers le backend |
| **📜 Conformité réglementaire** | Respect de la norme EN 16969 / Factur-X (profil minimum) |
| **🔧 Architecture réelle** | Séparation frontend/backend, pipeline de validation |
| **🧪 QA / validation** | Instructions veraPDF + validateur EN 16931 incluses |

---

## 🏗️ Architecture

```
facturx-generator-v3/
├── facturx-generator-v3.html   ← Frontend : saisir les données, exporter payload.json
├── facturx_builder.py          ← Backend : générer PDF visuel + XML + fusion PDF/A-3
└── output.pdf                  ← Facture Factur-X finale (prête à envoyer)
```

### Pipeline de génération

```
📝 HTML form → payload.json → 🐍 Python
                                 ├── 📄 PDF visuel (reportlab)
                                 ├── 📄 XML factur-x
                                 └── 📦 Fusion → PDF/A-3 final
```

---

## 🚀 Utilisation

```bash
# 1. Installer les dépendances
pip install factur-x reportlab

# 2. Ouvrir le formulaire HTML

# 3. Remplir → exporter payload.json

# 4. Générer la facture conforme
python facturx_builder.py payload.json output.pdf
```

### Validation recommandée

```bash
# Conformité PDF/A-3
verapdf output.pdf

# Conformité EN 16931 (validateur Factur-X en ligne)
```

---

## 🔒 Sécurité & Privacy

- **Aucune donnée ne quitte votre machine** — tout est local
- **Aucun compte, aucun abonnement** — pas de cloud, pas de SaaS
- Le code est ouvert : vous contrôlez exactement ce qu'il fait

---

## 📋 Prérequis

- Python 3.9+
- `pip install factur-x reportlab`
- (Optionnel) veraPDF pour validation PDF/A

---

## 👤 À propos

Développé par [Emmanuel Ruaudel](https://github.com/Ruaudel-Emmanuel) — freelance automation & Python.  
Ce projet montre une maîtrise de :
- Python backend (génération PDF, XML, conformité réglementaire)
- Frontend HTML/JS (formulaire, export JSON)
- Architecture logicielle (séparation des concerns, pipeline)
- Connaissances métier (norme Factur-X, EN 16931)
