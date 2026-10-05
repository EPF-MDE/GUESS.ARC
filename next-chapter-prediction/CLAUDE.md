# One Piece Next-Chapter Forecasting

## Project

This project studies whether machine learning can predict important events
in the next One Piece chapter from all information available up to the
current chapter.

The project uses One Piece only. It is a single continuous narrative.

## Main research question

Does an explicit narrative-state representation improve next-chapter
event prediction compared with text-only representations?

## Secondary questions

- How does context length affect prediction?
- Do explicit entities improve prediction?
- Do extracted events improve prediction?
- Does modeling unresolved plotlines improve prediction?
- Do temporal models outperform static models?
- Does better event prediction improve generated summaries?

## Critical rule: temporal causality

The project must never use future information.

For a target chapter t+1, every feature must be constructed exclusively
from chapters 1...t.

Never use:

- future chapters
- future summaries
- future entity states
- future relations
- future events
- future arc information
- annotations derived from future chapters

Random train/test splits are forbidden.

## Planned representations

- Raw chapter summaries
- Text embeddings
- Characters/entities
- Events
- Relations
- Narrative state
- Unresolved plotlines
- Temporal narrative graph

## Planned models

Baselines:
- Most frequent events
- Recent-event persistence

ML models:
- Embedding + MLP
- GRU
- LSTM
- Temporal Transformer

## Target

The first prediction task is multi-label next-event prediction.

Do not begin by directly generating the next chapter summary.

Pipeline:

chapters 1...t
→ narrative representation
→ event prediction for t+1
→ optional summary generation

## Evaluation

Primary metrics:

- Micro-F1
- Macro-F1
- Precision
- Recall
- Precision@K
- Recall@K

Additional metrics can be introduced only when justified.

## Engineering principles

- Small modules
- Typed Python
- Tests for important logic
- Configuration instead of hardcoded values
- Reproducible experiments
- Fixed random seeds
- Caching for expensive operations
- No unnecessary rewrites
- No giant scripts
- No fabricated experiment results

## Workflow

Before implementing a feature:

1. Understand the requirement.
2. Inspect the existing code.
3. Identify affected files.
4. Propose the smallest coherent implementation.
5. Implement.
6. Run tests.
7. Run a relevant smoke test.
8. Report what changed and remaining risks.

Never implement several unrelated tickets at once.

## Tickets

Tickets are tracked in GitHub Issues (#14–#72, mapping in ROADMAP.md §7).
The files in tickets/ are a frozen snapshot: do not edit them.
Ticket status, discussion and changes happen on the GitHub issue.
