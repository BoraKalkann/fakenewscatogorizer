# fakenewscatogorizer

Classifying misinformation in news articles — a team project for the Computer Engineering Design course.

## Idea
The user submits a news link. The app fetches the article, splits it into sentences, and checks each one in two ways:

- **Misleading language / propaganda techniques**, detected by our own trained model.
- **Factual errors**, checked by a research module that extracts claims and searches the web for evidence.

The results are combined into an article-level credibility score with a type label (satire, propaganda, hoax, reliable) and the reasoning behind it.

## Team
- Bora Kalkan (captain): model training, system architecture
- Tuğba Karaca: data preparation, feature extraction, evaluation
- İkbal Çanak: web frontend and backend, testing

## Status
Early stage. The project is English-only.
