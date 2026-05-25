# ADR-005 — Architecture du Coach RAG data-aware

## Statut
Accepté — avril 2026

## Contexte
Le projet collecte des données temps-réel sur les transports, la qualité
de l'air et la météo. La feature "coach" doit permettre de poser des
questions en langage naturel sur ces données structurées, sans halluciner
de chiffres inventés.

## Décision
**RAG data-aware** avec orchestration en 3 étapes :

1. **Intent classification** (LLaMA 3.1 8B via Groq) → catégorise la question
2. **Tool execution** → appelle les fonctions Python qui interrogent la BDD
3. **Response generation** (LLaMA 3.3 70B via Groq) → formule la réponse

Anti-hallucination en 3 niveaux : (1) le LLM ne peut répondre qu'avec les
données retournées par les tools, (2) chaque chiffre doit citer sa source
et son âge, (3) réponse préfixée `⚠️` si aucune donnée disponible.

## Conséquences
- ✅ Données restent en SQL — pas de re-embedding à chaque ingestion
- ✅ Multilingue FR/EN natif grâce aux capacités du LLM
- ✅ Facilement extensible : ajouter un tool = nouvelle classe de questions
- ⚠️ 2 appels LLM par question (latence ~1s avec Groq, acceptable)
- ⚠️ Dépendance à la qualité du prompt système — à surveiller en cas
  de mise à jour du modèle
