# Scott Sun — Academic Homepage & Research Telemetry

[![ORCID](https://img.shields.io/badge/ORCID-0009--0002--1095--6228-green?logo=orcid&logoColor=white)](https://orcid.org/0009-0002-1095-6228)
[![Google Scholar](https://img.shields.io/badge/Google_Scholar-Scott_Sun-blue?logo=google-scholar&logoColor=white)](https://scholar.google.com/citations?user=bmVEc3wAAAAJ)
[![OSF Hub](https://img.shields.io/badge/OSF_Hub-10.17605%2FOSF.IO%2FCAQXH-blue?logo=open-science-framework&logoColor=white)](https://doi.org/10.17605/OSF.IO/CAQXH)
[![Zenodo Community](https://img.shields.io/badge/Zenodo-ifg--htsie-navy?logo=zenodo&logoColor=white)](https://zenodo.org/communities/ifg-htsie/records)
[![Schema Version](https://img.shields.io/badge/Schema-v3.0_Aligned-brightgreen)](#-repository-architecture--data-flow)
[![Metadata Audit](https://img.shields.io/badge/Scholarly_Audit-Passing-success)](#-data-pipeline--telemetry-lifecycle)

> **Independent Researcher**  
> *Information Theory · Complex Systems · Emergent Geometry · Additive Combinatorics · Foundations of Physics*

This repository source-controls the personal academic portal for Scott Sun ([scottsun.com](https://www.scottsun.com/)), hosting formal preprints, computational audit suites, open-science datasets, and an automated research telemetry engine.

---

## 🔬 Research Focus & Theoretical Frameworks

My research explores how structural information, pre-geometric constraints, computation, and collective dynamics generate higher-level mathematical and physical emergence:

* **Structural Information Evolution (HTSIE)**: Higher-order information dynamics, structural constraints, and non-equilibrium state evolution.
* **Emergent Geometry & Causality**: Pre-geometric spacetime descriptions, Lorentzian quotients, light-cone algebra, and null pin holonomy.
* **Spectral-Dimension Flow & Irreversible Time**: Scale-dependent geometric flow, fractal horizon defects, and the arrow of time.
* **Additive Combinatorics & Computational Audits**: Exhaustive verification, modular radar algorithms, gap geometry, and Cantor-Pascal diagnostics for mathematical representation problems (e.g., Sun's Binomial Representation Program).
* **Mechanistic Interpretability in AI**: Mapping mathematical indices (DFFI, EDI) to Sparse Autoencoders (SAE) and scaling law limits in Large Language Models.

---

## 🛠️ Repository Architecture & Data Flow

This repository is built as an automated, self-auditing academic data node. It decouples research metadata, live telemetry, and automated CI/CD validation from the frontend rendering engine.

```text
[scottsun.com/](https://scottsun.com/)
├── .github/
│   └── workflows/
│       ├── auto_update_attention.yml  # 🤖 Auto-sync: Scheduled API fetch & attention.json backwrite
│       └── scholarly_audit.yml        # 🛡️ CI Guard: PR & commit metadata validation (Crossref/OpenAlex)
├── data/
│   ├── attention.json                 # 📊 Telemetry Store: Single Source of Truth (Schema v3.0)
│   └── publications.json              # 📜 Research Assets: Standardized publication metadata
├── scripts/
│   ├── scholarly_audit.py             # 🔍 Audit Engine: Crossref/OpenAlex DOI & title consistency check
│   └── fetch_telemetry.py             # ⚡ Telemetry Fetcher: Aggregates GitHub, Zenodo & Scholar metrics
└── index.html                         # 💻 Frontend Engine: Data-driven static dashboard
