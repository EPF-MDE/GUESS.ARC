# Embedding Gold alongside the Taxonomy Gold, forecast in embedding space

Going from Silver Files to the Taxonomy Gold is costly, slow and still in progress (`data/taxonomy/` is empty; Konrad's old-schema tags cover only 766 chapters and none after 1100). Rather than block chapter-event prediction on it, we add a second Gold Representation: the Embedding Gold, one Chapter Embedding per chapter, built from the Long Summary prose only (never the structured header, so the cast can't leak in). It is cheap, covers all 1,193 chapters today, and needs no taxonomy work. The price is interpretability — a vector isn't human-readable — which we pay back by decoding Predicted Embeddings to the Characters listed in the Silver File header and by showing the nearest real past chapters.

The prediction task on this layer forecasts chapter n+1's Chapter Embedding from chapters up to n, as a residual on chapter n (so the persistence baseline is the zero prediction), and is judged both in embedding space (centered cosine, retrieval rank) and, once decoded, by micro F1 on Characters against the existing 53% persistence baseline. This branch evaluates the embedding route on its own terms; a head-to-head comparison with the Taxonomy Gold is explicitly out of scope.

## Considered Options

- **Wait for the Taxonomy Gold** — rejected: blocks all modelling on extraction work whose timeline we don't control.
- **Train on Konrad's 766 old-schema chapters** — rejected: patchy after chapter 500, no labels on the test range (1101–1193), and a schema being replaced.
- **Use embeddings only as extra input features to a tag predictor** (the feasibility study's original step 3) — rejected for this branch: still requires tags as targets.

## Consequences

- The Embedding Gold is stored as one matrix per embedding configuration (model, chunking rule, silver revisions) with a manifest, not one file per chapter as in ADR 0006: the per-chapter reviewability argument doesn't apply to vectors, and mixing configurations must be impossible.
- Stored vectors are the raw model output; dimensionality reduction (PCA) is fitted per experiment on training chapters only and belongs to the model, not the gold layer.
