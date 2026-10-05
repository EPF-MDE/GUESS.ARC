"""Next Chapter Prediction.

À partir des résumés des chapitres 1..n d'un livre, prédire ce qui est
susceptible de se produire au chapitre n+1.

Le paquet est organisé en étages indépendants, chacun utilisable seul :

``ncp.data``            chargement d'un dataset de résumés, format-agnostique
``ncp.forecasting``     découpage de l'historique en exemples (fenêtre glissante)
``ncp.annotations``     extraction d'entités / événements / relations
``ncp.representations`` transformation d'un exemple en features (les 5 approches comparées)
``ncp.models``          prédicteurs (baselines d'abord, neuronal ensuite)
``ncp.evaluation``      métriques et rapports
``ncp.experiments``     orchestration bout-en-bout, pilotée par configuration
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
