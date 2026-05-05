# Fiscale Factur-X v2 — test et rebuild

## Prérequis

- Docker et Docker Compose installés
- Projet cloné localement
- Fichier de test disponible : `payload-test.json`

---

## Redémarrage propre

Depuis le dossier du projet :

```bash
docker compose down
docker compose build
docker compose up -d
```

Vérifier que le conteneur tourne :

```bash
docker compose ps
```

---

## Vérification santé API

Tester l’endpoint de santé :

```bash
curl -v http://localhost:8100/health
```

Résultat attendu :
- code HTTP `200 OK`
- réponse JSON avec un statut `ok`

---

## Génération d’un PDF Factur-X

Lancer un test complet avec le payload d’exemple :

```bash
curl -v -X POST "http://localhost:8100/generate-facturx" \
  -H "Content-Type: application/json" \
  --data-binary @payload-test.json \
  --output facture-test-facturx.pdf
```

Vérifier le fichier généré :

```bash
ls -lh facture-test-facturx.pdf
file facture-test-facturx.pdf
```

Résultat attendu :
- fichier présent
- type : `PDF document`

---

## Logs utiles

Afficher les logs du service :

```bash
docker compose logs --tail=120 facturx-api
```

En cas de succès, on doit voir des lignes proches de :

```text
factur-x XML file successfully validated against XSD
factur-x.xml file added to PDF document
factur-x PDF generated
POST /generate-facturx HTTP/1.1" 200 OK
```

---

## Test rapide en une ligne

```bash
curl -sf http://localhost:8100/health && \
curl -s -X POST "http://localhost:8100/generate-facturx" \
  -H "Content-Type: application/json" \
  --data-binary @payload-test.json \
  --output facture-test-facturx.pdf && \
file facture-test-facturx.pdf
```

---

## Dépannage rapide

### 1. Le conteneur ne démarre pas

```bash
docker compose ps
docker compose logs --tail=120 facturx-api
```

### 2. L’endpoint `/health` ne répond pas

```bash
until curl -sf http://localhost:8100/health; do
  sleep 1
done
```

### 3. Le fichier de sortie reste invalide

Vérifier le fichier généré :

```bash
ls -lh facture-test-facturx.pdf
file facture-test-facturx.pdf
```

Si `curl` n’arrive pas à écrire le fichier, supprimer l’ancien :

```bash
rm -f facture-test-facturx.pdf
```

Puis relancer le test.

### 4. Vérifier la génération Python dans le conteneur

Copier le payload dans le conteneur :

```bash
docker cp payload-test.json facturx-api:/tmp/payload-test.json
```

Tester directement le service Python :

```bash
docker exec -it facturx-api /bin/sh -lc 'python - << "PY"
import json
from pathlib import Path
from app.services.facturx_service import generate_facturx_pdf

payload = json.loads(Path("/tmp/payload-test.json").read_text(encoding="utf-8"))
pdf_bytes, filename = generate_facturx_pdf(payload)
print(type(pdf_bytes), len(pdf_bytes), filename)
PY'
```

Résultat attendu :
- type `bytes`
- taille > 0
- nom de fichier `invoice-facturx.pdf`

---

## Commandes utiles

Redémarrer seulement le service :

```bash
docker compose restart facturx-api
```

Reconstruire sans cache :

```bash
docker compose build --no-cache
docker compose up -d
```

Entrer dans le conteneur :

```bash
docker exec -it facturx-api /bin/sh
```

---

## État attendu quand tout fonctionne

- `docker compose ps` → conteneur `Up`
- `curl /health` → `200 OK`
- `curl POST /generate-facturx` → `200 OK`
- `file facture-test-facturx.pdf` → `PDF document`
- logs → validation XSD + génération PDF réussies