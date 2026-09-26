# Scott Sun — Academic Homepage & Research Telemetry Node

[![ORCID](https://img.shields.io/badge/ORCID-0009--0002--1095--6228-green?logo=orcid&logoColor=white)](https://orcid.org/0009-0002-1095-6228)
[![Google Scholar](https://img.shields.io/badge/Google_Scholar-Scott_Sun-blue?logo=google-scholar&logoColor=white)](https://scholar.google.com/citations?user=bmVEc3wAAAAJ)
[![OEIS Sequence](https://img.shields.io/badge/OEIS-A306477-brightgreen?logo=database&logoColor=white)](https://oeis.org/A306477)
[![OEIS CiteSl](https://img.shields.io/badge/OEIS_Wiki-CiteSl_Indexed-gold)](https://oeis.org/wiki/CiteSl)
[![OSF Hub](https://img.shields.io/badge/OSF_Hub-10.17605%2FOSF.IO%2FCAQXH-blue?logo=open-science-framework&logoColor=white)](https://doi.org/10.17605/OSF.IO/CAQXH)
[![Zenodo Master DOI](https://img.shields.io/badge/Zenodo-10.5281%2Fzenodo.21544303-navy?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.21544303)
[![Schema Version](https://img.shields.io/badge/Schema-v3.0_Aligned-brightgreen)](#-repository-architecture--data-flow)
[![Metadata Audit](https://img.shields.io/badge/Scholarly_Audit-Passing-success)](#-data-pipeline--telemetry-lifecycle)

> **Independent Researcher**  
> *Information Theory · Complex Systems · Emergent Geometry · Additive Combinatorics · Foundations of Physics*

This repository source-controls the personal academic data node for Scott Sun ([scottsun.com](https://www.scottsun.com/)), hosting formal preprints, computational audit suites, open-science datasets, and an automated research telemetry engine.

---

## 🏛️ Official OEIS Indexing & Academic Citations

Research outputs on Sun's (2,4,6,8) Binomial Representation Program (OEIS A306477) are officially indexed and cited in the **[OEIS Wiki Citation Repository (CiteSl)](https://oeis.org/wiki/CiteSl)** under three primary works:

1. **Candidate Discovery & Diagnostics (V23.4)**:  
   *Scott Sun*, *A Computational Audit of a Candidate Counterexample to Sun's (2,4,6,8) Conjecture: Exhaustive Verification and Cantor-Pascal Diagnostics*, ResearchGate / OSF (2026). [`doi:10.17605/OSF.IO/CAQXH`](https://doi.org/10.17605/OSF.IO/CAQXH)
2. **Local Modular Constraints & Surjectivity**:  
   *Scott Sun*, *Additive Representations by Mixed-Degree Binomial Coefficient Sequences: A Computational Investigation of Sun's (2,4,6,8) Conjecture*, ResearchGate (2026). [`ResearchGate Publication`](https://www.researchgate.net/publication/383501142_Additive_Representations_by_Mixed-Degree_Binomial_Coefficient_Sequences)
3. **Triangular Witness Trajectories & Bounds (V40.3)**:  
   *Scott Sun*, *Triangular Witness Trajectories and Gap-Cascade Bounds for the (2,4,6,8) Binomial Representation Problem*, Zenodo (2026). [`doi:10.5281/zenodo.21544303`](https://doi.org/10.5281/zenodo.21544303)

---

## 🔬 Research Focus & Theoretical Frameworks

My research explores how structural information, pre-geometric constraints, computation, and collective dynamics generate higher-level mathematical and physical emergence:

* **Structural Information Evolution (HTSIE)**: Higher-order information dynamics, structural constraints, and non-equilibrium state evolution.
* **Emergent Geometry & Causality**: Pre-geometric spacetime descriptions, Lorentzian quotients, light-cone algebra, and null pin holonomy.
* **Spectral-Dimension Flow & Irreversible Time**: Scale-dependent geometric flow, fractal horizon defects, and the arrow of time.
* **Additive Combinatorics & Computational Audits**: Exhaustive verification, modular radar algorithms, gap geometry, Lean 4 formalization, and Cantor-Pascal diagnostics for mathematical representation problems (e.g., Sun's Binomial Representation Program, OEIS A306477).
* **Mechanistic Interpretability in AI**: Mapping mathematical indices (DFFI, EDI) to Sparse Autoencoders (SAE) and scaling law limits in Large Language Models.

---

## 🛠️ Repository Architecture & Data Flow

This repository is built as an automated, self-auditing academic data node. It decouples research metadata, live telemetry, and automated CI/CD validation.

```text
[scottsun.com/](https://scottsun.com/)
├── .github/
│   └── workflows/
│       ├── auto_update.yml         # 🤖 Scheduled Telemetry Sync (Runs daily at 18:00 UTC)
│       └── scholarly_audit.yml     # 🛡️ CI/CD Guard (PR & Push DOI / CFF Validation)
├── data/
│   └── attention.json              # 📊 Telemetry Store: Metrics & Aggregate Attention (Schema v3.0)
├── scholarly/
│   └── publications.json           # 📜 Static Publication Metadata, DOIs & OEIS Links (Schema v2.0)
├── scripts/
│   ├── scholarly_audit.py          # 🔍 Audit Engine: Crossref & OpenAlex API Consistency Inspector
│   └── update_attention.py         # 🔄 Telemetry Engine: Zenodo & GitHub Traffic Aggregator
├── .nojekyll                       # 🚀 Bypass Jekyll Build for Direct GitHub Pages Static Serving
├── CITATION.cff                    # 🏷️ Citation Metadata File (CFF v1.2.0)
├── index.html                      # 🌐 Academic Data Node Homepage (V40.3 & OEIS Aligned)
├── requirements.txt                # 📦 Python Runtime Dependencies
└── README.md                       # 📖 Documentation Node
