<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/banner-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/banner.svg" />
    <img width="100%" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/banner.svg" alt="Chirudeva Reddy, AI engineer working on applied machine learning and evaluation" />
  </picture>
</p>

<p align="center">
  <a href="https://www.linkedin.com/in/chirudeva-reddy/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-linkedin-dark.svg" />
      <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-linkedin.svg" />
      <img src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-linkedin.svg" alt="Connect with Chirudeva Reddy on LinkedIn" />
    </picture>
  </a>
  <a href="mailto:chirudevareddy03@gmail.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-email-dark.svg" />
      <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-email.svg" />
      <img src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-email.svg" alt="Email Chirudeva Reddy" />
    </picture>
  </a>
  <a href="https://www.instagram.com/chiru.reddyy/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-instagram-dark.svg" />
      <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-instagram.svg" />
      <img src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/social-instagram.svg" alt="Follow Chirudeva Reddy on Instagram" />
    </picture>
  </a>
</p>

## About me

I got here the long way round. I was pointed at the rigorous, prestigious academic path early, and at the start it did not interest me one bit.

That changed about a year ago, once I noticed the work I actually finished was always work on a problem that was bothering me personally. That is still the whole argument: if I can solve a problem for myself, why not optimise the process and solve it for everyone else too. Most of what is below started exactly that way.

Learning all of this in the middle of the AI era taught me the other half. In a world full of frontier models you can certainly build cool things by outsourcing the intelligence, and it is tempting. *Forcing* myself to take the extra mile and learn the thing while I build it is what makes the process exponentially better.

Right now I am working through ML fundamentals, RAG evaluation, computer vision, and what it takes to run AI in production. I am looking for an AI engineering role.

## Featured work

### [ClaimLens](https://github.com/Chirudeva-Reddy/ClaimLens) &nbsp;·&nbsp; [live demo](https://chirudeva-reddy.github.io/ClaimLens/)

**Two-stage vehicle damage segmentation with rule-based repair costing, and a total-loss call it is willing to refuse.**

Two fine-tuned YOLOv8n-seg checkpoints run in sequence, a parts detector over 21 body panels and a damage detector over 6 collision types, and Shapely polygon intersection maps each damage mask onto the panel underneath it. Pricing is deliberately not learned: it comes from a crawled UAE collision-parts catalogue, so a wrong number is traceable to a row rather than to a weight. The loss ratio is checked against the CBUAE Unified Motor Policy 50% threshold, with US and UK presets alongside it.

The part I care about most is the abstention path. When damage reaches a load-bearing unibody zone, the photo fails a blur and resolution gate, or confidence drops below the floor, the pipeline returns `INSUFFICIENT_EVIDENCE_INSPECTION_REQUIRED` instead of a price.

<sub>Parts model 82.0% Box mAP@50, damage model 64.6% Box mAP@50, both from the committed checkpoint metrics. 18 pytest modules.</sub>

`YOLOv8n-seg` `Ultralytics` `Shapely` `TF-IDF retrieval` `FastAPI` `Gradio`

---

### [body2fit](https://github.com/Chirudeva-Reddy/body2health)

**Waist, hip and chest girths from two orthogonal phone photos, with a 3D geometry gate that can mark a run unreportable.**

YOLOv11m and SAM 2.1 segment the silhouettes and standardise them onto a fixed canvas. Twin ResNet-18 branches encode the front and side views into a shared 512-D space aligned by symmetric InfoNCE, and the fused vector feeds multi-task regression heads. The health indices are derived arithmetically from the predicted girths rather than predicted directly, so they cannot disagree with the measurements they came from.

An opt-in SMPL-X fit (`--smplx_fit`) closes the loop: it fits a mesh with Neural Localizer Fields, renders it back to the camera view, and marks the run unreportable when render-back IoU and contour chamfer disagree with the silhouette actually observed.

<sub>Waist MAE 2.40 cm dual-view and 1.97 cm with height, on a subject-disjoint BodyM split. Dual-view cuts single-front-view waist error by 74%. Paper listed as under submission to IJCAI 2026.</sub>

`SAM 2.1` `YOLOv11m` `Siamese ResNet-18` `InfoNCE` `SMPL-X` `PyTorch` `Three.js`

---

### [Pre-generation hallucination detection](https://github.com/Chirudeva-Reddy/NLP-Proj) &nbsp;·&nbsp; [live demo](https://chirudeva-reddy.github.io/NLP-Proj/)

**Reading hallucination risk out of a 1.5B model's hidden states instead of out of its output text.**

The same RAG prompt runs twice through Qwen2.5-1.5B, once with retrieved evidence and once with empty context, and four signals come off the residual stream: cosine drift between consecutive answer positions, Mahalanobis distance and PCA residual against a faithful-token manifold fit on the train split, and logit-lens KL between the two passes. They fuse by robust z-score with medians, IQRs and weights frozen from train and validation, so nothing is tuned on the test set. Bidirectional activation patching is there to check the signals are causal rather than merely correlated.

<sub>AUROC 0.6511 on the RAGTruth held-out test (bootstrap CI 0.6307–0.6614) against 0.6106 for the attention-entropy baseline, so the intervals still overlap. The frozen composite transfers to HaluEval-QA within 0.006 AUROC. Cosine drift peaks two tokens before hallucination onset (p = 2.9e-5). University project, four authors.</sub>

`Qwen2.5-1.5B` `Forward hooks` `Logit lens` `Activation patching` `RAGTruth` `HaluEval`

---

### [Road accident severity prediction](https://github.com/Chirudeva-Reddy/Road-Accident-Severity-Prediction)

**Severity classification and crash-hotspot mapping over Chicago traffic crash records.**

LightGBM, XGBoost, ExtraTrees and two logistic-regression baselines are compared under five-fold stratified cross-validation. LightGBM and XGBoost land 0.0003 macro F1 apart, well inside the cross-validation standard deviation, which is the sort of margin worth naming rather than declaring a winner over; LightGBM is the one saved and evaluated on the held-out set. SHAP and LIME explain what it keys on.

The geospatial half spatially joins crash points onto Chicago's 77 community areas and runs DBSCAN with a Haversine metric per area instead of over every point at once, which is the decision that keeps the clustering tractable at all.

<sub>Macro F1 0.806 and balanced accuracy 0.799 on the held-out test set. 98 cluster centroids and a 15-page report committed. Four-person academic project.</sub>

`LightGBM` `XGBoost` `SHAP` `LIME` `DBSCAN` `GeoPandas` `Plotly Dash`

---

### [duet](https://github.com/Chirudeva-Reddy/duet)

**Asks Claude Code and Codex the same question independently, then reports where they disagree.**

One bash script. No API keys, no config file, no daemon: it drives the CLIs you are already signed into. Both panelists run read-only and neither sees the other, then a third pass leads with the disagreements rather than blending them into a consensus answer that hides them.

`--selftest` tests the guarantee instead of the flag name. Each agent gets a scratch directory and is told to write a canary file by any means it can find, and anything that lands on disk is reported as a breach, so a renamed or weakened sandbox flag fails loudly instead of silently.

`Bash` `Claude Code CLI` `Codex CLI` `Read-only sandboxing`

---

### [Salon ERP](https://github.com/Chirudeva-Reddy/odoo-salon-erp)

**An installable Odoo 19 module. No ML in it, here for the data model and the tests.**

A booking state machine whose transitions are guarded methods rather than a free-form status field, and an append-only loyalty ledger whose `write()` and `unlink()` raise on any non-empty recordset, so a customer balance is the signed sum of a trail nobody can edit. Double-booking is blocked by a half-open interval constraint run with `sudo`, so the per-stylist record rule cannot hide a genuine conflict from the check. CI installs the module into a clean `odoo:19.0` container with demo data and runs the suite on every push.

`Odoo 19` `PostgreSQL 16` `Odoo ORM record rules` `Docker Compose` `GitHub Actions`

## Tools I use

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/stack-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/stack.svg" />
  <img width="100%" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/stack.svg" alt="Python, PyTorch, TensorFlow, scikit-learn, CUDA, MLflow, NumPy, Pandas, Streamlit, Plotly, Django, Node.js, PostgreSQL, MongoDB, AWS, Azure, Firebase and Vercel" />
</picture>

## GitHub activity

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/activity-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/activity.svg" />
  <img width="100%" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/activity.svg" alt="Contribution totals, streaks and top languages for Chirudeva Reddy" />
</picture>

<!-- The green contribution snake. Uncomment this block to show it alongside
     the ocean one below; both are still generated by .github/workflows/snake.yml.
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/github-snake-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/github-snake.svg" />
  <img alt="Chirudeva Reddy's GitHub contribution snake" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/github-snake.svg" />
</picture>
-->

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/ocean-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/ocean.svg" />
    <img width="100%" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/ocean.svg" alt="Ocean-themed animation of the GitHub contribution snake eating a year of commit squares" />
  </picture>
</p>

Everything on this page is generated by [.github/workflows/snake.yml](.github/workflows/snake.yml) and committed to the `output` branch: the snake by [Platane/snk](https://github.com/Platane/snk), the rest by [tools/build_assets.py](tools/build_assets.py). No third-party image service is contacted when you load this page.

</details>

## Training Graph

Weekly minutes from my Hevy log over the last 16 weeks. The flat stubs are weeks I did not train.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/training-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/training.svg" />
  <img width="100%" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/training.svg" alt="Weekly training minutes over the last 16 weeks, with session count, week streak and average session length" />
</picture>

## Let's build something useful

I am open to AI engineering roles and to collaborating on applied ML and trustworthy AI. If you have a hard, practical problem, send it over.

**[Email me](mailto:chirudevareddy03@gmail.com)** or **[connect with me on LinkedIn](https://www.linkedin.com/in/chirudeva-reddy/)**.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/footer-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/footer.svg" />
    <img width="100%" src="https://raw.githubusercontent.com/Chirudeva-Reddy/Chirudeva-Reddy/output/footer.svg" alt="Open to AI engineering roles. Hard, practical problems welcome. chirudevareddy03@gmail.com" />
  </picture>
</p>

<sub>Every image on this page is generated by [.github/workflows/snake.yml](.github/workflows/snake.yml) and committed to the `output` branch: the snake by [Platane/snk](https://github.com/Platane/snk), the rest by [tools/build_assets.py](tools/build_assets.py), with brand glyphs vendored from [Simple Icons](https://simpleicons.org). No third-party image service is contacted when you load this page.</sub>
