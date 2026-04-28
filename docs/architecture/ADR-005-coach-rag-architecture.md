# ADR 005 — Architecture du Coach RAG data-aware

**Statut :** Accepté
**Date :** 2026-04
**Auteur :** Colin

## Contexte

Le projet ParisMove AI dispose d'un pipeline d'ingestion temps-réel collectant
des données sur les transports, la qualité de l'air et la météo. La feature
"coach" doit permettre à un utilisateur final de poser des questions en
langage naturel sur ces données.

Plusieurs architectures de RAG (Retrieval-Augmented Generation) étaient
possibles :

1. **RAG documentaire classique** : indexer des documents textuels dans une
   base vectorielle, retrouver les chunks pertinents par similarité, puis
   demander au LLM de répondre à partir de ces chunks.

2. **RAG data-aware** : le LLM oriente vers des "tools" (fonctions Python)
   qui interrogent la base de données structurée et retournent des résultats
   factuels que le LLM intègre dans sa réponse.

## Décision

Adopter la **stratégie 2 (RAG data-aware)** avec une orchestration en 3 étapes :

1. **Intent classification** (LLM léger 8B) → détermine la nature de la question
2. **Tool selection & execution** → exécute les fonctions appropriées sur la BDD
3. **Response generation** (LLM 70B) → reformule en réponse naturelle

## Justifications

### Pourquoi pas le RAG classique ?

Notre donnée n'est pas du texte mais des **mesures structurées avec sémantique
spatiale et temporelle**. Indexer dans un vectorstore aurait nécessité :
- Convertir chaque ligne SQL en phrase (verbose, lossy)
- Re-embedder à chaque ingestion (coûteux)
- Et le LLM aurait peu de contexte sur la fraîcheur des données

Le pattern data-aware évite tout ça : la donnée reste en SQL, on tire la
réponse à la demande.

### Pourquoi 2 LLMs (8B et 70B) ?

L'intent classification est une tâche simple (catégoriser parmi 8 classes).
Un modèle 8B le fait à 95%+ précision et **5-10x plus vite** que le 70B.
On réserve le 70B pour la génération finale qui demande de la nuance.

C'est le pattern "**model cascading**" utilisé en production chez les grandes
boîtes : utiliser le plus petit modèle qui suffit pour chaque tâche.

### Garde-fous anti-hallucination

Trois niveaux :

1. **Architecture forcing-tools** : le LLM ne peut pas générer de chiffre qui
   n'est pas dans le contexte fourni par les tools.

2. **Système de sources** : chaque chiffre est accompagné de sa source
   (Airparif, AQICN, Open-Meteo, PRIM IDFM) et de l'âge de la mesure.
   Le LLM doit citer ces sources.

3. **Mode warning explicite** : quand le LLM répond sans données (questions
   hors-sujet ou données absentes), il doit préfixer par "⚠️ Pas de données
   temps-réel...".

### Pourquoi Groq ?

- **Rapidité** : Groq génère ~600 tokens/sec, contre ~30 tokens/sec sur d'autres
  providers. UX très fluide en mode chat.
- **Gratuit** : quotas généreux pour le tier gratuit.
- **API compatible OpenAI** : si on doit migrer un jour, c'est trivial.
- **Modèles ouverts** : LLaMA 3.3 70B est open-weights, on peut self-host
  si besoin pour des questions de souveraineté.

### Pourquoi pas de FastAPI/Streamlit pour cette PR ?

L'objectif est de livrer le cœur du système en une PR digeste. Une CLI
permet de :
- Tester rapidement
- Démontrer en soutenance (terminal = cinématographique)
- Servir de base à n'importe quelle UI future (FastAPI, Streamlit) sans
  rien refactorer du module orchestrator.

## Conséquences

### Positives
- Découplage propre : `intent.py`, `tools.py`, `orchestrator.py` sont
  testables indépendamment.
- Facile à étendre : ajouter une catégorie d'intent + un tool, et le coach
  comprend une nouvelle classe de questions.
- Multilingue gratuit (FR/EN) grâce aux capacités natives du LLM.
- Anti-hallucination robuste grâce aux 3 niveaux de garde-fous.

### Négatives
- Latence cumulée : 2 appels LLM par question (intent puis génération).
  Avec Groq, ça reste sous la seconde, mais avec un autre provider il
  faudrait paralléliser ou sauter l'intent classifier sur les questions
  courtes.
- Coût des tokens pour le contexte : si les tools retournent beaucoup de
  texte, on consomme plus. Acceptable au volume actuel (4 stations, 10
  points météo).
- Dépendance à la qualité du prompt système. À surveiller en cas de mise
  à jour du modèle Groq.

## Alternatives rejetées

### Function calling natif (OpenAI / Anthropic)

L'API "function calling" structurée existe chez OpenAI et Anthropic mais
**n'est pas encore stable côté Groq** au moment de cette décision. Notre
approche manuelle (intent → tool → LLM) est équivalente fonctionnellement
et portable sur n'importe quel LLM.

### LangChain / LlamaIndex

Frameworks puissants mais sur-dimensionnés pour notre besoin. On a 6 tools
et un intent classifier ; un orchestrateur de 200 lignes Python est plus
clair que 5 dépendances et 50 lignes de magic config.

### Embedding des données structurées

Convertir chaque mesure en texte ("La station Paris 18 a un AQI de 52 le
28/04 à 10h") puis les embedder dans Chroma. Inefficace : nos données
changent toutes les 30 minutes, il faudrait re-embedder constamment, et la
similarité vectorielle est moins précise qu'un filtre SQL `WHERE station =
'paris-18' ORDER BY measured_at DESC LIMIT 1`.
