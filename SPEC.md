# Map of Baby Food Science — Product Specification

**Project:** mapo_baby_food  
**Repository:** tomhirsch3000/mapo_baby_food  
**Status:** Local development scaffold complete  
**Last updated:** 2026-05-06

---

## 1. Project Brief

### Concept
A visual, interactive map of scientific evidence about baby food and infant nutrition. The goal is to give parents and researchers a way to explore what the science actually says — organised by food type, baby age, or recommendation — rather than reading individual papers.

The project is inspired by two existing projects by the same author:
- **mapo-2.0** — an interactive map of physics research papers
- **mapo-food** — an earlier baby food prototype with food photographs and radial clusters

This project takes the visual metaphor and layout engine from mapo-2.0 and the food-centric content and image approach from mapo-food, combining them into a purpose-built baby food evidence map.

### Core Value Proposition
Parents want to know: *Is it safe to give my baby peanuts at 6 months? What does the evidence say?* This tool lets them see the weight of scientific consensus at a glance — strength of evidence, number of studies, conflicting findings — rather than relying on a single article or health website.

---

## 2. Questions Asked and Answered

**Q: Does OpenAlex cover medical and nutrition research, or is it just physics?**  
A: OpenAlex covers all academic fields including medicine, nutrition, paediatrics, and immunology. It is suitable as the primary paper source for this project.

**Q: Do you want actual 3D rendering (Three.js) or the 3D space aesthetic?**  
A: The 3D space/galaxy metaphor is what matters — the visual feel of stars and constellations. The actual rendering is 2D SVG using D3, which is how mapo-2.0 works under the hood despite the name "arxiv-3d".

**Q: Should the app pull concept/field data from OpenAlex for the layout, or use a custom structure?**  
A: Custom structure. The baby food domain is narrow enough that hand-curated topic clusters (peanut allergy, complementary feeding, gut microbiome, etc.) are better than OpenAlex's general concept taxonomy.

**Q: Will you need an AI synthesis layer?**  
A: Yes. A local Ollama LLM (Mistral) will be used to generate recommendation summaries, classify evidence strength, and extract structured metadata from paper abstracts. Python code from mapo-2.0's `process_ai_metadata.py` will be adapted.

**Q: What image source should be used for food photographs?**  
A: loremflickr.com as a placeholder for development (same approach as mapo-food). Replace with curated images before production launch.

**Q: What is the deployment target?**  
A: Vercel for the frontend. Local development first, Vercel later. The Flask backend will be deployed separately (Railway or Render) when ready.

**Q: Do you have a preference for image sources?**  
A: No preference. Proceed with loremflickr.

---

## 3. Visual Design

### Aesthetic
- Galaxy / cosmos metaphor: white light-mode background with radial gradients simulating a star field
- Nodes rendered as circles with glow effects; larger nodes = more citations
- Edges as faint lines connecting related papers
- Premium light-mode theme (not dark mode)
- Typography: Inter (Google Fonts)
- Colour palette: indigo/violet accent (`#6366f1`, `#8b5cf6`), slate text (`#1e293b`, `#334155`)

### Layout Modes
Two toggle options in the control panel:

| Mode | Description |
|------|-------------|
| **Central** | Force-directed radial layout; nodes cluster around their group centre |
| **Timeline** | Papers arranged left-to-right by publication year in horizontal lanes |

### Grouping Modes (replaces mapo's Field/Author/Institution)

| Mode | Groups papers by |
|------|-----------------|
| **Food Type** | The specific food studied (peanuts, dairy, vegetables, etc.) |
| **Baby Age** | The target age range in the study (0–6 months, 6–12 months, etc.) |
| **Recommendation** | The primary research field/recommendation category |

---

## 4. Navigation Hierarchy

The app has four view levels:

```
UNIVERSE VIEW
  └─ 12 galaxy nodes, one per nutrition topic cluster
  └─ Click a galaxy → GALAXY VIEW

GALAXY VIEW
  └─ Topic subdivided into food-type / age / recommendation groups
  └─ Click a group → FIELD VIEW

FIELD VIEW
  └─ Individual paper nodes for that group
  └─ Click a paper → shows details in footer panel
  └─ Double-click → DETAIL VIEW (loads citation network)

DETAIL VIEW
  └─ The selected paper + all papers it cites / is cited by
  └─ Fetched live from the Flask API

SEARCH (parallel view)
  └─ Entered from the search bar in any view
  └─ Shows core results + foundation/impact papers
  └─ Fetched live from the Flask API
```

### Galaxy Nodes (UNIVERSE level)
Each node represents one nutrition topic cluster:

| ID | Name | Icon Category |
|----|------|--------------|
| peanut_allergy | Peanut Allergy | peanuts |
| egg_allergy | Egg Allergy | eggs |
| cow_milk_allergy | Cow Milk Allergy | cow-milk |
| complementary_feeding | Complementary Feeding | solid-food |
| breastfeeding | Breastfeeding | breast-milk |
| infant_formula | Infant Formula | formula |
| iron_deficiency | Iron Deficiency | iron |
| vitamin_d | Vitamin D | vitamin-d |
| omega3_dha | Omega-3 / DHA | omega3 |
| gut_microbiome | Gut Microbiome | probiotics |
| baby_led_weaning | Baby-Led Weaning | solid-food |
| vegetable_introduction | Vegetable Introduction | vegetables |

### Research Field Categories (used in FIELD/RECOMMENDATION grouping)
- Allergen Introduction
- Feeding Milestones
- Nutrients & Supplements
- Food Safety
- Gut Health
- Growth & Development
- Breastfeeding & Formula

---

## 5. Paper Node Data Model

Each paper node carries these fields, populated by OpenAlex import and AI enrichment:

| Field | Source | Description |
|-------|--------|-------------|
| `paperId` | OpenAlex | Unique paper ID (e.g. `W1234567890`) |
| `title` | OpenAlex | Paper title |
| `abstract` | OpenAlex | Reconstructed from inverted index |
| `year` | OpenAlex | Publication year |
| `cited_by_count` | OpenAlex | Citation count (used for node size) |
| `all_author_names` | OpenAlex | Semicolon-separated author list |
| `all_institution_names` | OpenAlex | Semicolon-separated institution list |
| `paper_nature` | Derived | `clinical_trial` / `experimental` / `meta_analysis` / `review` |
| `study_type` | Derived | More granular type (cohort, RCT, etc.) |
| `food_type` | Import config | Food category slug (e.g. `peanuts`, `cow-milk`) |
| `age_group` | Import config | Target age range string |
| `AI_primary_field` | Ollama | One of the 7 research field categories |
| `AI_summary` | Ollama | 2–3 sentence plain-English summary for parents |
| `recommendation_summary` | Ollama | One sentence: what this means for parents |
| `evidence_strength` | Ollama | `strong` / `moderate` / `limited` / `mixed` |
| `likelihood_score` | Ollama | 0–100, probability the finding is real/replicable |
| `seriousness_score` | Ollama | 0–10, importance of the outcome for baby health |
| `participant_count` | Ollama | Extracted from abstract if mentioned |

### Evidence Strength Colour Coding (footer panel badges)
| Strength | Colour |
|----------|--------|
| strong | green `#10b981` |
| moderate | indigo `#6366f1` |
| limited | amber `#f59e0b` |
| mixed | slate `#94a3b8` |

---

## 6. Technology Stack

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 19 |
| Graph rendering | D3 v7 (SVG, 2D force-directed) |
| Build tool | Vite 6 |
| Styling | Plain CSS (Galaxy.css, Toggle.css) |
| Font | Inter via Google Fonts |
| Food images | loremflickr.com (placeholder) |

### Backend
| Component | Technology |
|-----------|-----------|
| API server | Flask 3 + flask-cors, port 5001 |
| Database | SQLite, one file per topic (`data/papers_*.db`) |
| Paper source | OpenAlex REST API (no key required) |
| AI enrichment | Ollama (local), model: Mistral |
| Ollama client | openai Python SDK pointed at `localhost:11434/v1` |

### Data Pipeline (run locally, output committed or served statically)
1. `backend/import_openalex.py` — fetches papers from OpenAlex into SQLite
2. `backend/process_ai.py` — enriches papers with Ollama AI metadata
3. `backend/build_data.py` — generates `universe.json` and per-topic `nodes.json` / `edges.json` into `frontend/public/`
4. `backend/notebooks/import_baby_food.ipynb` — Jupyter notebook orchestrating all three steps

---

## 7. File Structure

```
mapo_baby_food/
├── .gitignore
├── data/                          # SQLite databases (git-ignored)
│   └── .gitkeep
├── backend/
│   ├── server.py                  # Flask API
│   ├── import_openalex.py         # Paper fetcher
│   ├── process_ai.py              # AI enrichment
│   ├── build_data.py              # JSON builder
│   ├── requirements.txt
│   └── notebooks/
│       └── import_baby_food.ipynb
└── frontend/
    ├── index.html                 # Vite entry point
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── App.jsx
        ├── App.css
        ├── index.jsx
        ├── index.css
        ├── components/
        │   ├── Graph.jsx          # D3 SVG renderer
        │   ├── ControlPanel.jsx
        │   ├── FooterPanel.jsx
        │   └── SearchBar.jsx
        ├── modules/
        │   └── LayoutEngine.js    # Force layout algorithms
        ├── hooks/
        │   └── useGraphData.js    # Data fetching & processing
        ├── config/
        │   └── categoryIcons.js   # Food image URL map
        ├── utils/
        │   └── d3-helpers.js
        └── styles/
            ├── Galaxy.css
            └── Toggle.css
```

---

## 8. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Health check; lists available databases |
| GET | `/api/search?query=&min_citations=&max_papers=` | Full-text search; returns core + foundation + impact paper nodes |
| GET | `/api/paper/<id>/details?min_citations=&max_papers=` | Citation network for a single paper |

---

## 9. Running Locally

### Frontend
```cmd
cd frontend
npm install
npm start
# Opens at http://localhost:3000
```

### Backend (optional for static universe view)
```cmd
cd backend
pip install -r requirements.txt
python server.py
# Runs at http://localhost:5001
```

### Populating Data
```cmd
cd backend
python import_openalex.py --topic peanut_allergy --max 100
python process_ai.py --db ../data/papers_peanut_allergy.db
python build_data.py
```
Requires Ollama running locally: `ollama serve && ollama pull mistral`

---

## 10. Deployment Plan

### Frontend → Vercel
- Root directory: `frontend`
- Build command: `vite build` (auto-detected)
- Output directory: `dist`
- Environment variable: `VITE_API_URL=<backend-url>` (once backend is deployed)

### Backend → TBD (Railway or Render)
- The SQLite databases need to be bundled or mounted as a volume
- Alternative: pre-build all JSON files and serve them as static assets from Vercel (no backend needed for read-only browsing)

---

## 11. Known Limitations / Next Steps

- No real paper data yet — all 12 galaxy nodes are empty placeholders
- Food images are loremflickr placeholders (random photos, not curated)
- AI enrichment requires a local Ollama install with Mistral
- Backend not yet deployed; search and detail view require local Flask server
- No authentication or user accounts (read-only public map)
- Mobile layout partially supported (single-column footer, hidden hover panel)
