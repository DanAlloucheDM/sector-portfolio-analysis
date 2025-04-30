# Analyse et Optimisation de Portefeuille par Secteur

Ce projet vise à développer un système d'analyse et d'optimisation de portefeuille financier basé sur une approche sectorielle. Il utilise Python et plusieurs bibliothèques d'analyse de données financières pour collecter, traiter et analyser des données de marché.

## Contexte académique

Ce projet est développé dans le cadre du cours "Introduction à Python - Millésime 2025". Il s'agit d'une application pratique des concepts de programmation Python dans le domaine de la finance, notamment pour l'analyse et l'optimisation de portefeuilles d'investissement.

## Fonctionnalités implémentées

### Module de gestion des données de marché

Le cœur du projet est la classe `Market` qui permet de :

- Collecter automatiquement des données historiques depuis Yahoo Finance
- Organiser les instruments financiers par secteur (actions, ETFs, fonds mutuels)
- Gérer et nettoyer les données de marché
- Identifier et combler les données manquantes avec différentes stratégies
- Sauvegarder les données dans une structure hiérarchique

### Modularité et architecture

Le projet est structuré de manière modulaire :

- **src/data/market.py** : Classe principale pour la gestion des données de marché
- **src/data/log_utils.py** : Module utilitaire pour la gestion des logs

### Stratégies de traitement des données manquantes

Plusieurs stratégies sont implémentées pour traiter les données manquantes :

- Remplissage avec la valeur précédente
- Remplissage avec la valeur suivante
- Interpolation linéaire
- Moyenne des valeurs adjacentes

## Configuration requise

- Python 3.10+
- Dépendances listées dans `requirements.txt`

## Installation

1. Cloner le dépôt
   ```bash
   git clone https://github.com/votre-utilisateur/analyse-optimisation-portefeuille.git
   cd analyse-optimisation-portefeuille
   ```

2. Créer et activer un environnement virtuel
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Windows: venv\Scripts\activate
   ```

3. Installer les dépendances
   ```bash
   pip install -r requirements.txt
   ```

## Utilisation

Voici un exemple simple d'utilisation de la classe `Market` :

```python
from src.data.market import Market

# Initialiser le marché avec des paramètres personnalisés
market = Market(
    start_date='2022-01-01',
    end_date='2023-12-31',
    data_dir='data',
    limit=5  # Nombre d'instruments par secteur et type
)

# Accéder aux données d'un secteur
tech_data = market.get_sector_data('technology')

# Récupérer les données d'un ticker spécifique
aapl_data = market.get_ticker_data('AAPL')

# Compléter les données manquantes
market.fill_missing_dates(method='interpolate')

# Sauvegarder les données
market.save_market_data()
```

## Travaux futurs

- Analyse de corrélation entre les secteurs
- Optimisation de portefeuille basée sur la théorie moderne du portefeuille
- Visualisation interactive des données
- Backtesting de stratégies d'investissement
- Interface utilisateur pour faciliter l'analyse

## Licence

Ce projet est distribué sous licence MIT. Voir le fichier `LICENSE` pour plus d'informations.

## Contributions

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou à soumettre une pull request. 