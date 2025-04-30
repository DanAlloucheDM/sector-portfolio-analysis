"""
Module de gestion des données de marché.

Ce module fournit une classe principale Market qui permet de collecter, 
gérer et accéder aux données de marché par secteur en utilisant yfinance.
"""

# ===== IMPORTS STANDARDS =====
import os
import sys
import contextlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ===== IMPORTS TIERS =====
import pandas as pd
import numpy as np
import yfinance as yf

# ===== IMPORTS LOCAUX =====
from src.data.log_utils import disable_logs, restore_logs

# ===== DÉFINITION DE LA CLASSE MARKET =====

class Market:
    """
    Classe pour collecter, gérer et accéder aux données de marché par secteur.
    
    Cette classe permet de collecter automatiquement des données historiques pour 
    différents instruments financiers (actions, ETFs, fonds mutuels) regroupés par 
    secteurs à l'aide de yfinance.
    """
    
    # ===== INITIALISATION =====
    
    def __init__(self, start_date: str = '2010-01-01', end_date: str = '2024-12-31', 
                 data_dir: str = 'data', verbose: bool = True, limit: int = 3, 
                 save: bool = True, rounding: bool = True):
        """
        Initialise le collecteur de données de marché.
        
        Args:
            start_date (str): Date de début au format 'YYYY-MM-DD'
            end_date (str): Date de fin au format 'YYYY-MM-DD'
            data_dir (str): Répertoire pour sauvegarder les données
            verbose (bool): Afficher les messages de progression
            limit (int): Nombre maximum d'instruments à collecter par secteur et type
            save (bool): Sauvegarder automatiquement les données collectées
            rounding (bool): Arrondir les valeurs de prix au centième près
        """
        # Paramètres principaux
        self.start_date = start_date
        self.end_date = end_date
        self.data_dir = data_dir
        self.verbose = verbose
        self.limit = limit
        self.save = save
        self.rounding = rounding
        
        # Liste des secteurs selon Yahoo Finance
        self.sectors = [
            'technology', 'financial-services', 'healthcare', 'consumer-cyclical',
            'industrials', 'consumer-defensive', 'energy', 'basic-materials',
            'communication-services', 'real-estate', 'utilities'
        ]
        
        # Création du répertoire de données si nécessaire
        if self.save and not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # DataFrame pour stocker les informations des tickers
        self.tickers_info = pd.DataFrame(columns=['Ticker', 'StartDate', 'EndDate', 'MissingDates', 'Sector', 'Type'])
        
        # Initialiser le marché
        self.market = pd.DataFrame()
        self.instruments = {}
        self.inactive_days = pd.DatetimeIndex([])
        
        # Collecter les données
        self._collect_data(limit)
        
        # Identifier les jours inactifs
        self._identify_inactive_days(verbose=self.verbose)
        
        # Générer les informations détaillées des tickers
        self._generate_tickers_info(verbose=self.verbose)
    
    # ===== COLLECTE DE DONNÉES =====
    
    def _collect_data(self, limit: int):
        """
        Collecte les données et construit le DataFrame consolidé self.market.
        
        Args:
            limit (int): Nombre maximum d'instruments à collecter par secteur et type
        """
        if self.verbose:
            print("Initialisation de la collecte de données...")
        
        # Initialisation des structures
        self.instruments = {}
        all_dfs = []
        valid_tickers = {}
        problem_tickers = {}
        total_instruments = 0
        total_available = 0
        
        # Désactiver les logs de yfinance en utilisant la fonction du module log_utils
        original_log_levels = disable_logs()
        
        try:
            # Collecter les données pour chaque secteur
            for sector in self.sectors:
                if self.verbose:
                    print(f"\nTraitement du secteur: {sector}")
                
                # Initialiser les instruments pour ce secteur
                self.instruments[sector] = {'stocks': [], 'etfs': [], 'mutual_funds': []}
                valid_tickers[sector] = {'stocks': [], 'etfs': [], 'mutual_funds': []}
                problem_tickers[sector] = {'stocks': [], 'etfs': [], 'mutual_funds': []}
                
                # Récupérer tous les instruments disponibles
                sector_data = yf.Sector(sector)
                stocks = sector_data.top_companies.index.tolist()
                etfs = list(sector_data.top_etfs.keys())
                mutual_funds = list(sector_data.top_mutual_funds.keys())
                
                total_available += len(stocks) + len(etfs) + len(mutual_funds)
                
                if self.verbose:
                    print(f"Tickers disponibles: Actions: {len(stocks)}, ETFs: {len(etfs)}, Fonds mutuels: {len(mutual_funds)}")
                
                # Télécharger les données pour chaque type d'instrument
                for instrument_type, all_tickers in [('stocks', stocks), ('etfs', etfs), ('mutual_funds', mutual_funds)]:
                    if not all_tickers:
                        continue
                    
                    if self.verbose:
                        print(f"  Traitement des {instrument_type}...")
                    
                    # Compteur de tickers valides
                    valid_count = 0
                    
                    # Parcourir les tickers jusqu'à atteindre la limite ou épuiser tous les tickers
                    for ticker in all_tickers:
                        # Si on a déjà atteint la limite de tickers valides, on arrête
                        if valid_count >= limit:
                            break
                            
                        try:
                            # Télécharger les données avec suppression des messages d'erreur
                            with open(os.devnull, 'w') as fnull, contextlib.redirect_stderr(fnull), contextlib.redirect_stdout(fnull):
                                data = yf.download(
                                    tickers=ticker,
                                    start=self.start_date,
                                    end=self.end_date,
                                    auto_adjust=True,
                                    progress=False,
                                    rounding=self.rounding,
                                    actions=False,
                                    multi_level_index=False
                                )
                            
                            if not data.empty:
                                # Préparer les données
                                data.index.name = 'Date'
                                if hasattr(data.columns, 'name'):
                                    data.columns.name = None
                                
                                # Ajouter les métadonnées
                                ticker_df = data.copy()
                                ticker_df['Ticker'] = ticker
                                ticker_df['Sector'] = sector
                                ticker_df['Type'] = instrument_type
                                
                                # Ajouter au DataFrame résultant
                                all_dfs.append(ticker_df)
                                valid_tickers[sector][instrument_type].append(ticker)
                                self.instruments[sector][instrument_type].append(ticker)
                                valid_count += 1
                                total_instruments += 1
                                
                                if self.verbose:
                                    print(f"    Données téléchargées pour {ticker}: {data.shape[0]} entrées ({valid_count}/{limit})")
                            else:
                                problem_tickers[sector][instrument_type].append(ticker)
                                if self.verbose:
                                    print(f"    Aucune donnée disponible pour {ticker} - exclu du marché")
                        except Exception as e:
                            problem_tickers[sector][instrument_type].append(ticker)
                            if self.verbose:
                                print(f"    Erreur lors du téléchargement des données pour {ticker}: {str(e)} - exclu du marché")
                    
                    # Informer si on n'a pas pu atteindre la limite
                    if valid_count < limit and self.verbose:
                        print(f"     Attention: Seulement {valid_count}/{limit} {instrument_type} valides trouvés pour {sector}")
            
            # Récapitulatif des problèmes
            if self.verbose and sum(len(problems) for sector_problems in problem_tickers.values() 
                               for problems in sector_problems.values()) > 0:
                print("\nRécapitulatif des tickers exclus en raison de problèmes:")
                for sector, sector_problems in problem_tickers.items():
                    for instrument_type, problems in sector_problems.items():
                        if problems:
                            print(f"  {sector} - {instrument_type}: {', '.join(problems)}")
            
            # Construire le DataFrame consolidé
            if not all_dfs:
                if self.verbose:
                    print("Aucune donnée collectée.")
                self.market = pd.DataFrame()
                return
            
            # Consolider les données
            self.market = pd.concat(all_dfs, axis=0)
            
            # Réorganiser les colonnes
            cols = self.market.columns.tolist()
            meta_cols = ['Ticker', 'Sector', 'Type']
            data_cols = [c for c in cols if c not in meta_cols]
            self.market = self.market[meta_cols + data_cols]
            
            # Créer un index multi-niveaux (Date, Ticker)
            self.market.reset_index(inplace=True)
            self.market.set_index(['Date', 'Ticker'], inplace=True)
            
            # Nettoyer les données
            self._clean_market_data(verbose=self.verbose)
            
            # Sauvegarder les données
            if self.save and not self.market.empty:
                self.save_market_data(verbose=self.verbose)
            
            # Afficher le récapitulatif
            if self.verbose:
                print(f"\nCollecte des données terminée:")
                print(f"  {total_instruments} tickers sur {total_available} disponibles ont été intégrés")
                print(f"  {self.market.shape[0]} lignes de données au total")
        
        finally:
            # Restaurer les logs en utilisant la fonction du module log_utils
            restore_logs(original_log_levels)
    
    def _clean_market_data(self, verbose=None):
        """
        Nettoie le DataFrame consolidé en gérant les doublons et la cohérence des prix.

        Args:
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if self.market.empty:
            return
        
        if verbose:
            print("Nettoyage des données du marché...")
            print(f"Dimensions avant nettoyage: {self.market.shape}")
        
        # Copie des données pour éviter la modification en place
        market_df = self.market.copy()
        
        # 1. Gestion des doublons sur (Date, Ticker)
        if market_df.index.duplicated().any():
            if verbose:
                print(f"Doublons détectés sur (Date, Ticker): {market_df.index.duplicated().sum()} doublons. Résolution...")
            
            # Colonnes numériques et non numériques
            numeric_cols = market_df.select_dtypes(include=['number']).columns.tolist()
            non_numeric_cols = [col for col in market_df.columns if col not in numeric_cols]
            result_dfs = []
            
            if numeric_cols:
                numeric_df = market_df[numeric_cols].groupby(level=['Date', 'Ticker']).mean()
                result_dfs.append(numeric_df)
            
            if non_numeric_cols:
                non_numeric_df = market_df[non_numeric_cols].groupby(level=['Date', 'Ticker']).first()
                result_dfs.append(non_numeric_df)
            
            if len(result_dfs) > 1:
                market_df = pd.concat(result_dfs, axis=1)
            else:
                market_df = result_dfs[0]
            
            if verbose:
                print(f"Résolution des doublons terminée. Nouvelle taille: {market_df.shape}")
        
        # 2. Vérification de la cohérence des prix
        price_columns = ['Close', 'Open', 'High', 'Low']
        if all(col in market_df.columns for col in price_columns):
            # Permutation des valeurs si Low > High
            low_high_mask = market_df['Low'] > market_df['High']
            if low_high_mask.any():
                temp_low = market_df.loc[low_high_mask, 'Low'].copy()
                market_df.loc[low_high_mask, 'Low'] = market_df.loc[low_high_mask, 'High']
                market_df.loc[low_high_mask, 'High'] = temp_low
            
            # Permutation si Open > High
            open_high_mask = market_df['Open'] > market_df['High']
            if open_high_mask.any():
                market_df.loc[open_high_mask, 'Open'], market_df.loc[open_high_mask, 'High'] = \
                    market_df.loc[open_high_mask, 'High'].copy(), market_df.loc[open_high_mask, 'Open'].copy()
            
            # Permutation si Close > High
            close_high_mask = market_df['Close'] > market_df['High']
            if close_high_mask.any():
                market_df.loc[close_high_mask, 'Close'], market_df.loc[close_high_mask, 'High'] = \
                    market_df.loc[close_high_mask, 'High'].copy(), market_df.loc[close_high_mask, 'Close'].copy()
            
            # Permutation si Open < Low
            open_low_mask = market_df['Open'] < market_df['Low']
            if open_low_mask.any():
                market_df.loc[open_low_mask, 'Open'], market_df.loc[open_low_mask, 'Low'] = \
                    market_df.loc[open_low_mask, 'Low'].copy(), market_df.loc[open_low_mask, 'Open'].copy()
        
        # Mettre à jour le DataFrame consolidé
        self.market = market_df
        
        if verbose:
            print(f"Dimensions après nettoyage: {self.market.shape}")

    
    def _identify_inactive_days(self, verbose=None):
        """
        Identifie les jours pour lesquels aucune donnée n'est disponible.
        Ces jours sont stockés dans self.inactive_days.
        
        Args:
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if self.market.empty:
            self.inactive_days = pd.DatetimeIndex([])
            return
        
        # Période complète
        full_period = pd.date_range(start=self.start_date, end=self.end_date)
        
        # Dates disponibles
        available_dates = pd.DatetimeIndex(self.market.index.get_level_values('Date').unique())
        
        # Jours inactifs = jours sans données
        self.inactive_days = full_period.difference(available_dates)
        
        if verbose and not self.inactive_days.empty:
            inactive_count = len(self.inactive_days)
            total_days = len(full_period)
            inactive_percent = (inactive_count / total_days) * 100
            print(f"\nJours inactifs identifiés: {inactive_count} sur {total_days} jours ({inactive_percent:.1f}%).")
            if inactive_count > 0 and inactive_count <= 20:
                print(f"Jours inactifs: {', '.join(d.strftime('%Y-%m-%d') for d in self.inactive_days)}")

    
    # ===== UTILITAIRES =====
    
    # ===== ACCÈS AUX DONNÉES =====
    
    def get_sector_data(self, sector, start_date=None, end_date=None, verbose=None):
        """
        Récupère les données pour un secteur spécifique.
        
        Args:
            sector (str): Nom du secteur
            start_date (str, optional): Date de début au format 'YYYY-MM-DD'
            end_date (str, optional): Date de fin au format 'YYYY-MM-DD'
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            pd.DataFrame: Données du secteur
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if self.market.empty:
            if verbose:
                print("Aucune donnée disponible dans le marché.")
            return pd.DataFrame()
        
        # Ajuster les dates aux limites de la période disponible
        start = pd.to_datetime(start_date) if start_date is not None else pd.to_datetime(self.start_date)
        end = pd.to_datetime(end_date) if end_date is not None else pd.to_datetime(self.end_date)
        
        # Vérifier que les dates sont dans les limites
        if start < pd.to_datetime(self.start_date):
            if verbose:
                print(f"Date de début ajustée à {self.start_date}")
            start = pd.to_datetime(self.start_date)
            
        if end > pd.to_datetime(self.end_date):
            if verbose:
                print(f"Date de fin ajustée à {self.end_date}")
            end = pd.to_datetime(self.end_date)
        
        # Filtrer par secteur
        sector_data = self.market[self.market['Sector'] == sector].copy()
        
        if sector_data.empty:
            if verbose:
                print(f"Aucune donnée disponible pour le secteur '{sector}'.")
            return pd.DataFrame()
        
        # Filtrer par date
        sector_data = sector_data[
            (sector_data.index.get_level_values('Date') >= start) & 
            (sector_data.index.get_level_values('Date') <= end)
        ]
        
        if sector_data.empty and verbose:
            print(f"Aucune donnée disponible pour le secteur '{sector}' dans la période spécifiée.")
        
        # Supprimer la colonne 'Sector' qui est redondante
        if 'Sector' in sector_data.columns:
            sector_data = sector_data.drop(columns=['Sector'])
            
        return sector_data
   
    def get_ticker_data(self, ticker, start_date=None, end_date=None, verbose=None):
        """
        Récupère les données pour un ticker spécifique.
        
        Args:
            ticker (str): Symbole du ticker
            start_date (str, optional): Date de début au format 'YYYY-MM-DD'
            end_date (str, optional): Date de fin au format 'YYYY-MM-DD'
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            pd.DataFrame: Données du ticker avec l'index 'Date' uniquement
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if self.market.empty:
            if verbose:
                print("Aucune donnée disponible dans le marché.")
            return pd.DataFrame()
        
        # Ajuster les dates aux limites de la période disponible
        start = pd.to_datetime(start_date) if start_date is not None else pd.to_datetime(self.start_date)
        end = pd.to_datetime(end_date) if end_date is not None else pd.to_datetime(self.end_date)
        
        # Vérifier que les dates sont dans les limites
        if start < pd.to_datetime(self.start_date):
            if verbose:
                print(f"Date de début ajustée à {self.start_date}")
            start = pd.to_datetime(self.start_date)
            
        if end > pd.to_datetime(self.end_date):
            if verbose:
                print(f"Date de fin ajustée à {self.end_date}")
            end = pd.to_datetime(self.end_date)
        
        # Filtrer par ticker
        ticker_mask = self.market.index.get_level_values('Ticker') == ticker
        ticker_data = self.market.loc[ticker_mask].copy()
        
        if ticker_data.empty:
            if verbose:
                print(f"Aucune donnée disponible pour le ticker '{ticker}'.")
            return pd.DataFrame()
        
        # Filtrer par date
        ticker_data = ticker_data[
            (ticker_data.index.get_level_values('Date') >= start) & 
            (ticker_data.index.get_level_values('Date') <= end)
        ]
        
        if ticker_data.empty and verbose:
            print(f"Aucune donnée disponible pour le ticker '{ticker}' dans la période spécifiée.")
        
        # Supprimer les colonnes 'Sector' et 'Type' qui sont redondantes
        columns_to_drop = []
        if 'Sector' in ticker_data.columns:
            columns_to_drop.append('Sector')
        if 'Type' in ticker_data.columns:
            columns_to_drop.append('Type')
        
        if columns_to_drop:
            ticker_data = ticker_data.drop(columns=columns_to_drop)
        
        # Supprimer l'index 'Ticker' pour ne garder que l'index 'Date'
        ticker_data = ticker_data.droplevel('Ticker')
            
        return ticker_data

    
    def get_tickers_by_sector(self, sector):
        """
        Récupère la liste des tickers pour un secteur spécifique.
        
        Args:
            sector (str): Nom du secteur
            
        Returns:
            dict: Dictionnaire des tickers par type d'instrument
        """
        if sector not in self.instruments:
            return {}
            
        return self.instruments[sector]
    
    # ===== INFORMATIONS SUR LES TICKERS =====
    
    def _generate_tickers_info(self, verbose=None):
        """
        Génère un DataFrame contenant des informations détaillées sur chaque ticker:
        - Ticker
        - Date de début des données
        - Date de fin des données
        - Liste des dates manquantes (excluant les jours inactifs)
        - Secteur
        - Type d'instrument
        
        Args:
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose

        # Créer une liste pour stocker les informations
        tickers_data = []
        
        # Obtenir tous les tickers uniques
        unique_tickers = self.market.index.get_level_values('Ticker').unique()
        
        # Période complète
        full_period = pd.date_range(start=self.start_date, end=self.end_date)
        
        # Pour chaque ticker, calculer les informations
        for ticker in unique_tickers:
            # Obtenir les données du ticker
            ticker_mask = self.market.index.get_level_values('Ticker') == ticker
            ticker_data = self.market.loc[ticker_mask]
            
            # Obtenir les métadonnées
            sector = ticker_data['Sector'].iloc[0] if not ticker_data.empty else None
            instr_type = ticker_data['Type'].iloc[0] if not ticker_data.empty else None
            
            # Obtenir les dates disponibles
            available_dates = pd.DatetimeIndex(ticker_data.index.get_level_values('Date'))
            
            # Déterminer les dates de début et de fin
            start_date = available_dates.min() if not available_dates.empty else None
            end_date = available_dates.max() if not available_dates.empty else None
            
            # Calculer les dates manquantes (dans la période entre start_date et end_date)
            if start_date is not None and end_date is not None:
                ticker_period = pd.date_range(start=start_date, end=end_date)
                
                # Exclure les jours inactifs de la période du ticker
                active_period = ticker_period.difference(self.inactive_days)
                
                # Maintenant, calculer les dates manquantes comme les dates actives qui ne sont pas disponibles
                missing_dates = active_period.difference(available_dates).tolist()
            else:
                missing_dates = []
            
            # Ajouter aux données
            tickers_data.append({
                'Ticker': ticker,
                'StartDate': start_date,
                'EndDate': end_date,
                'MissingDates': missing_dates,
                'Sector': sector,
                'Type': instr_type
            })
        
        # Créer le DataFrame des informations
        self.tickers_info = pd.DataFrame(tickers_data)
        
        if verbose:
            # Afficher des statistiques sur les dates manquantes
            missing_counts = self.tickers_info['MissingDates'].apply(len)
            if missing_counts.sum() > 0:
                print(f"Total des dates manquantes (hors jours inactifs): {missing_counts.sum()}")
                print(f"Nombre de tickers avec des dates manquantes: {(missing_counts > 0).sum()}/{len(unique_tickers)}")

    
    def get_ticker_info(self, ticker=None, sector=None, instr_type=None, verbose=None):
        """
        Récupère les informations détaillées pour un ou plusieurs tickers en fonction des filtres.
        
        Args:
            ticker (str, optional): Filtrer par ticker spécifique
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            pd.DataFrame: Informations filtrées des tickers avec l'index défini sur 'Ticker'
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if self.tickers_info.empty:
            if verbose:
                print("Aucune information sur les tickers n'est disponible.")
            return pd.DataFrame()
        
        # Appliquer les filtres
        result = self.tickers_info
        
        if ticker is not None:
            result = result[result['Ticker'] == ticker]
            
        if sector is not None:
            result = result[result['Sector'] == sector]
            
        if instr_type is not None:
            result = result[result['Type'] == instr_type]
        
        # Définir l'index sur la colonne 'Ticker'
        result = result.set_index('Ticker')
        
        return result
    
    def get_tickers_with_missing_dates(self, sector=None, instr_type=None, min_missing=1, sort_by='count', verbose=None):
        """
        Récupère les tickers qui ont des dates manquantes.
        
        Args:
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            min_missing (int, optional): Nombre minimum de dates manquantes pour inclure un ticker
            sort_by (str, optional): Critère de tri - 'count' (nombre de dates manquantes), 'ticker' ou 'percentage'
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            pd.DataFrame: DataFrame des tickers avec des dates manquantes et des informations supplémentaires
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if self.tickers_info.empty:
            if verbose:
                print("Aucune information sur les tickers n'est disponible.")
            return pd.DataFrame()
        
        # Obtenir les informations filtrées des tickers
        tickers_info = self.get_ticker_info(sector=sector, instr_type=instr_type, verbose=False)
        
        # Calculer le nombre de dates manquantes pour chaque ticker
        missing_counts = tickers_info['MissingDates'].apply(len)
        
        # Filtrer pour ne conserver que les tickers avec des dates manquantes
        has_missing = missing_counts >= min_missing
        tickers_with_missing = tickers_info[has_missing].copy()
        
        if tickers_with_missing.empty:
            if verbose:
                print("Aucun ticker ne présente de dates manquantes avec les critères spécifiés.")
            return pd.DataFrame()
        
        # Ajouter une colonne pour le nombre de dates manquantes
        tickers_with_missing['NombreDatesMissing'] = missing_counts[has_missing]
        
        # Ajouter une colonne pour le pourcentage de dates manquantes par rapport à la période du ticker
        def calculate_missing_percentage(row):
            if row['StartDate'] is None or row['EndDate'] is None:
                return 0.0
            total_period = (row['EndDate'] - row['StartDate']).days + 1
            inactive_days_in_period = sum(1 for d in self.inactive_days if row['StartDate'] <= d <= row['EndDate'])
            active_days = total_period - inactive_days_in_period
            if active_days <= 0:
                return 0.0
            return (row['NombreDatesMissing'] / active_days) * 100
        
        tickers_with_missing['PourcentageMissing'] = tickers_with_missing.apply(calculate_missing_percentage, axis=1)
        
        # Trier selon le critère spécifié
        if sort_by == 'count':
            tickers_with_missing = tickers_with_missing.sort_values(by='NombreDatesMissing', ascending=False)
        elif sort_by == 'ticker':
            tickers_with_missing = tickers_with_missing.sort_values(by=tickers_with_missing.index)
        elif sort_by == 'percentage':
            tickers_with_missing = tickers_with_missing.sort_values(by='PourcentageMissing', ascending=False)
        
        # Réinitialiser l'index pour avoir 'Ticker' comme colonne
        tickers_with_missing = tickers_with_missing.reset_index()
        
        # Sélectionner les colonnes à retourner
        result_columns = ['Ticker', 'Sector', 'Type', 'NombreDatesMissing', 'PourcentageMissing', 'StartDate', 'EndDate', 'MissingDates']
        result = tickers_with_missing[result_columns]
        
        if verbose:
            print(f"{len(result)} tickers ont des dates manquantes:")
            print(f"  Nombre total de dates manquantes: {missing_counts[has_missing].sum()}")
            
            # Afficher le détail des dates manquantes pour chaque ticker
            for idx, row in result.iterrows():
                ticker = row['Ticker']
                nb_missing = row['NombreDatesMissing']
                pct_missing = row['PourcentageMissing']
                sector = row['Sector']
                instr_type = row['Type']
                
                # Formater le texte pour l'affichage
                date_word = "date" if nb_missing == 1 else "dates"
                print(f"  {ticker} ({sector}/{instr_type}): {nb_missing} {date_word} manquante(s) ({pct_missing:.2f}%)")
                
        return result
    
    # ===== GESTION DES DATES MANQUANTES =====
    
    def fill_missing_dates(self, method='previous', sector=None, instr_type=None, min_missing=1, verbose=None):
        """
        Complète les dates manquantes dans les données en utilisant la méthode spécifiée.
        Cette méthode sert de façade pour différentes stratégies de remplissage.
        
        Args:
            method (str): Méthode de remplissage à utiliser:
                - 'previous': Utilise les valeurs du jour précédent (par défaut)
                - 'next': Utilise les valeurs du jour suivant
                - 'interpolate': Utilise une interpolation linéaire entre les valeurs disponibles
                - 'mean': Utilise la moyenne des valeurs précédente et suivante
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            min_missing (int, optional): Nombre minimum de dates manquantes pour traiter un ticker
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            bool: True si des modifications ont été effectuées, False sinon
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if method == 'previous':
            return self._fill_missing_with_previous(sector, instr_type, min_missing, verbose)
        elif method == 'next':
            return self._fill_missing_with_next(sector, instr_type, min_missing, verbose)
        elif method == 'interpolate':
            return self._fill_missing_with_interpolation(sector, instr_type, min_missing, verbose)
        elif method == 'mean':
            return self._fill_missing_with_mean(sector, instr_type, min_missing, verbose)
        else:
            if verbose:
                print(f"Méthode de remplissage '{method}' non reconnue. Options disponibles: 'previous', 'next', 'interpolate', 'mean'")
            return False
        
    def _fill_missing_with_previous(self, sector=None, instr_type=None, min_missing=1, verbose=None):
        """
        Complète les dates manquantes en utilisant les valeurs du jour précédent disponible.
        
        Args:
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            min_missing (int, optional): Nombre minimum de dates manquantes pour traiter un ticker
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            bool: True si des modifications ont été effectuées, False sinon
        """
        if self.market.empty:
            if verbose:
                print("Aucune donnée disponible pour compléter les dates manquantes.")
            return False
        
        # Obtenir les tickers avec des dates manquantes
        tickers_with_missing = self.get_tickers_with_missing_dates(sector=sector, instr_type=instr_type, min_missing=min_missing, verbose=False)
        
        if tickers_with_missing.empty:
            if verbose:
                print("Aucun ticker ne présente de dates manquantes à compléter.")
            return False
        
        if verbose:
            print(f"Complétion des données manquantes pour {len(tickers_with_missing)} tickers (méthode: valeur précédente)...")
        
        # Compteurs pour le suivi des modifications
        total_dates_filled = 0
        tickers_modified = set()
        
        # Liste pour stocker les nouvelles données
        new_rows = []
        
        # Pour chaque ticker ayant des dates manquantes
        for _, row in tickers_with_missing.iterrows():
            ticker = row['Ticker']
            missing_dates = row['MissingDates']
            
            if not missing_dates:
                continue
                
            # Récupérer les données du ticker
            ticker_data = self.get_ticker_data(ticker)
            if ticker_data.empty:
                continue
            
            # Pour chaque date manquante
            dates_filled_for_ticker = 0
            
            # Trier les dates manquantes
            sorted_missing_dates = sorted(missing_dates)
            
            for missing_date in sorted_missing_dates:
                # Trouver la date disponible la plus récente avant la date manquante
                # Comme ticker_data.index est maintenant un simple index de dates, on peut l'utiliser directement
                available_dates = ticker_data.index
                previous_dates = available_dates[available_dates < missing_date]
                
                if previous_dates.empty:
                    # Si aucune date précédente, on ne peut pas compléter
                    continue
                
                # Obtenir la date disponible la plus récente
                prev_date = previous_dates.max()
                
                # Obtenir les données de cette date
                prev_data = ticker_data.loc[[prev_date]]
                
                # Créer une nouvelle ligne pour la date manquante
                for _, prev_row in prev_data.iterrows():
                    # Créer un dictionnaire pour la nouvelle ligne
                    new_row_dict = {'Ticker': ticker, 'Date': missing_date}
                    
                    # Ajouter les valeurs des colonnes au dictionnaire
                    for col in self.market.columns:
                        if col in prev_row:
                            new_row_dict[col] = prev_row[col]
                    
                    # Ajouter la nouvelle ligne
                    new_rows.append(new_row_dict)
                    dates_filled_for_ticker += 1
            
            if dates_filled_for_ticker > 0:
                total_dates_filled += dates_filled_for_ticker
                tickers_modified.add(ticker)
                if verbose:
                    print(f"  {ticker}: {dates_filled_for_ticker} date(s) complétée(s)")
        
        # Si des lignes ont été créées, les ajouter au DataFrame principal
        if new_rows:
            return self._add_new_data_rows(new_rows, total_dates_filled, tickers_modified, verbose)
        
        return False
    
    def _fill_missing_with_next(self, sector=None, instr_type=None, min_missing=1, verbose=None):
        """
        Complète les dates manquantes en utilisant les valeurs du jour suivant disponible.
        
        Args:
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            min_missing (int, optional): Nombre minimum de dates manquantes pour traiter un ticker
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            bool: True si des modifications ont été effectuées, False sinon
        """
        if self.market.empty:
            if verbose:
                print("Aucune donnée disponible pour compléter les dates manquantes.")
            return False
        
        # Obtenir les tickers avec des dates manquantes
        tickers_with_missing = self.get_tickers_with_missing_dates(sector=sector, instr_type=instr_type, min_missing=min_missing, verbose=False)
        
        if tickers_with_missing.empty:
            if verbose:
                print("Aucun ticker ne présente de dates manquantes à compléter.")
            return False
        
        if verbose:
            print(f"Complétion des données manquantes pour {len(tickers_with_missing)} tickers (méthode: valeur suivante)...")
        
        # Compteurs pour le suivi des modifications
        total_dates_filled = 0
        tickers_modified = set()
        
        # Liste pour stocker les nouvelles données
        new_rows = []
        
        # Pour chaque ticker ayant des dates manquantes
        for _, row in tickers_with_missing.iterrows():
            ticker = row['Ticker']
            missing_dates = row['MissingDates']
            
            if not missing_dates:
                continue
                
            # Récupérer les données du ticker
            ticker_data = self.get_ticker_data(ticker)
            if ticker_data.empty:
                continue
            
            # Pour chaque date manquante
            dates_filled_for_ticker = 0
            
            # Trier les dates manquantes
            sorted_missing_dates = sorted(missing_dates)
            
            for missing_date in sorted_missing_dates:
                # Trouver la date disponible la plus proche après la date manquante
                available_dates = ticker_data.index
                next_dates = available_dates[available_dates > missing_date]
                
                if next_dates.empty:
                    # Si aucune date suivante, on ne peut pas compléter
                    continue
                
                # Obtenir la date disponible la plus proche
                next_date = next_dates.min()
                
                # Obtenir les données de cette date
                next_data = ticker_data.loc[[next_date]]
                
                # Créer une nouvelle ligne pour la date manquante
                for _, next_row in next_data.iterrows():
                    # Créer un dictionnaire pour la nouvelle ligne
                    new_row_dict = {'Ticker': ticker, 'Date': missing_date}
                    
                    # Ajouter les valeurs des colonnes au dictionnaire
                    for col in self.market.columns:
                        if col in next_row:
                            new_row_dict[col] = next_row[col]
                    
                    # Ajouter la nouvelle ligne
                    new_rows.append(new_row_dict)
                    dates_filled_for_ticker += 1
            
            if dates_filled_for_ticker > 0:
                total_dates_filled += dates_filled_for_ticker
                tickers_modified.add(ticker)
                if verbose:
                    print(f"  {ticker}: {dates_filled_for_ticker} date(s) complétée(s)")
        
        # Si des lignes ont été créées, les ajouter au DataFrame principal
        if new_rows:
            return self._add_new_data_rows(new_rows, total_dates_filled, tickers_modified, verbose)
        
        return False
    
    def _fill_missing_with_interpolation(self, sector=None, instr_type=None, min_missing=1, verbose=None):
        """
        Complète les dates manquantes en utilisant une interpolation linéaire entre les valeurs disponibles.
        
        Args:
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            min_missing (int, optional): Nombre minimum de dates manquantes pour traiter un ticker
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            bool: True si des modifications ont été effectuées, False sinon
        """
        if self.market.empty:
            if verbose:
                print("Aucune donnée disponible pour compléter les dates manquantes.")
            return False
        
        # Obtenir les tickers avec des dates manquantes
        tickers_with_missing = self.get_tickers_with_missing_dates(sector=sector, instr_type=instr_type, min_missing=min_missing, verbose=False)
        
        if tickers_with_missing.empty:
            if verbose:
                print("Aucun ticker ne présente de dates manquantes à compléter.")
            return False
        
        if verbose:
            print(f"Complétion des données manquantes pour {len(tickers_with_missing)} tickers (méthode: interpolation)...")
        
        # Compteurs pour le suivi des modifications
        total_dates_filled = 0
        tickers_modified = set()
        
        # Liste pour stocker les nouvelles données
        new_rows = []
        
        # Colonnes numériques pour l'interpolation
        numeric_cols = self.market.select_dtypes(include=['number']).columns.tolist()
        
        # Pour chaque ticker ayant des dates manquantes
        for _, row in tickers_with_missing.iterrows():
            ticker = row['Ticker']
            missing_dates = row['MissingDates']
            
            if not missing_dates:
                continue
                
            # Récupérer les données du ticker
            ticker_data = self.get_ticker_data(ticker).copy()
            if ticker_data.empty:
                continue
            
            # Pour chaque date manquante
            dates_filled_for_ticker = 0
            
            # Pour chaque date manquante
            for missing_date in missing_dates:
                # Trouver les dates disponibles avant et après la date manquante
                available_dates = ticker_data.index
                previous_dates = available_dates[available_dates < missing_date]
                next_dates = available_dates[available_dates > missing_date]
                
                if previous_dates.empty or next_dates.empty:
                    # Si pas de date avant ou après, on ne peut pas interpoler
                    continue
                
                # Obtenir les dates les plus proches
                prev_date = previous_dates.max()
                next_date = next_dates.min()
                
                # Obtenir les données
                prev_data = ticker_data.loc[[prev_date]]
                next_data = ticker_data.loc[[next_date]]
                
                # Créer une nouvelle ligne pour la date manquante
                new_row_dict = {'Ticker': ticker, 'Date': missing_date}
                
                # Copier les colonnes non numériques depuis la ligne précédente
                for col in self.market.columns:
                    if col not in numeric_cols and col in prev_data:
                        new_row_dict[col] = prev_data[col].iloc[0]
                
                # Calculer l'interpolation linéaire pour les colonnes numériques
                for col in numeric_cols:
                    if col in prev_data and col in next_data:
                        prev_val = prev_data[col].iloc[0]
                        next_val = next_data[col].iloc[0]
                        
                        # Calculer le poids pour l'interpolation
                        total_days = (next_date - prev_date).days
                        days_passed = (missing_date - prev_date).days
                        weight = days_passed / total_days if total_days > 0 else 0
                        
                        # Interpolation linéaire
                        interpolated_val = prev_val + (next_val - prev_val) * weight
                        new_row_dict[col] = interpolated_val
                
                # Ajouter la nouvelle ligne
                new_rows.append(new_row_dict)
                dates_filled_for_ticker += 1
            
            if dates_filled_for_ticker > 0:
                total_dates_filled += dates_filled_for_ticker
                tickers_modified.add(ticker)
                if verbose:
                    print(f"  {ticker}: {dates_filled_for_ticker} date(s) complétée(s)")
        
        # Si des lignes ont été créées, les ajouter au DataFrame principal
        if new_rows:
            return self._add_new_data_rows(new_rows, total_dates_filled, tickers_modified, verbose)
        
        return False
    
    def _fill_missing_with_mean(self, sector=None, instr_type=None, min_missing=1, verbose=None):
        """
        Complète les dates manquantes en utilisant la moyenne des valeurs précédente et suivante.
        
        Args:
            sector (str, optional): Filtrer par secteur
            instr_type (str, optional): Filtrer par type d'instrument
            min_missing (int, optional): Nombre minimum de dates manquantes pour traiter un ticker
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            bool: True si des modifications ont été effectuées, False sinon
        """
        if self.market.empty:
            if verbose:
                print("Aucune donnée disponible pour compléter les dates manquantes.")
            return False
        
        # Obtenir les tickers avec des dates manquantes
        tickers_with_missing = self.get_tickers_with_missing_dates(sector=sector, instr_type=instr_type, min_missing=min_missing, verbose=False)
        
        if tickers_with_missing.empty:
            if verbose:
                print("Aucun ticker ne présente de dates manquantes à compléter.")
            return False
        
        if verbose:
            print(f"Complétion des données manquantes pour {len(tickers_with_missing)} tickers (méthode: moyenne)...")
        
        # Compteurs pour le suivi des modifications
        total_dates_filled = 0
        tickers_modified = set()
        
        # Liste pour stocker les nouvelles données
        new_rows = []
        
        # Colonnes numériques pour le calcul de la moyenne
        numeric_cols = self.market.select_dtypes(include=['number']).columns.tolist()
        
        # Pour chaque ticker ayant des dates manquantes
        for _, row in tickers_with_missing.iterrows():
            ticker = row['Ticker']
            missing_dates = row['MissingDates']
            
            if not missing_dates:
                continue
                
            # Récupérer les données du ticker
            ticker_data = self.get_ticker_data(ticker)
            if ticker_data.empty:
                continue
            
            # Pour chaque date manquante
            dates_filled_for_ticker = 0
            
            # Pour chaque date manquante
            for missing_date in missing_dates:
                # Trouver les dates disponibles avant et après la date manquante
                available_dates = ticker_data.index
                previous_dates = available_dates[available_dates < missing_date]
                next_dates = available_dates[available_dates > missing_date]
                
                if previous_dates.empty or next_dates.empty:
                    # Si pas de date avant ou après, on ne peut pas calculer la moyenne
                    continue
                
                # Obtenir les dates les plus proches
                prev_date = previous_dates.max()
                next_date = next_dates.min()
                
                # Obtenir les données
                prev_data = ticker_data.loc[[prev_date]]
                next_data = ticker_data.loc[[next_date]]
                
                # Créer une nouvelle ligne pour la date manquante
                new_row_dict = {'Ticker': ticker, 'Date': missing_date}
                
                # Copier les colonnes non numériques depuis la ligne précédente
                for col in self.market.columns:
                    if col not in numeric_cols and col in prev_data:
                        new_row_dict[col] = prev_data[col].iloc[0]
                
                # Calculer la moyenne pour les colonnes numériques
                for col in numeric_cols:
                    if col in prev_data and col in next_data:
                        prev_val = prev_data[col].iloc[0]
                        next_val = next_data[col].iloc[0]
                        mean_val = (prev_val + next_val) / 2
                        new_row_dict[col] = mean_val
                
                # Ajouter la nouvelle ligne
                new_rows.append(new_row_dict)
                dates_filled_for_ticker += 1
            
            if dates_filled_for_ticker > 0:
                total_dates_filled += dates_filled_for_ticker
                tickers_modified.add(ticker)
                if verbose:
                    print(f"  {ticker}: {dates_filled_for_ticker} date(s) complétée(s)")
        
        # Si des lignes ont été créées, les ajouter au DataFrame principal
        if new_rows:
            return self._add_new_data_rows(new_rows, total_dates_filled, tickers_modified, verbose)
        
        return False
    

    def _add_new_data_rows(self, new_rows, total_dates_filled, tickers_modified, verbose=None):
        """
        Ajoute les nouvelles lignes de données au DataFrame principal et met à jour les métadonnées.
        
        Args:
            new_rows (list): Liste des nouvelles lignes à ajouter
            total_dates_filled (int): Nombre total de dates complétées
            tickers_modified (set): Ensemble des tickers modifiés
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
            
        Returns:
            bool: True si des modifications ont été effectuées
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        # Créer un DataFrame avec les nouvelles lignes
        new_data = pd.DataFrame(new_rows)
        
        # Définir le même index que self.market
        new_data.set_index(['Date', 'Ticker'], inplace=True)
        
        # Combiner avec les données existantes
        self.market = pd.concat([self.market, new_data]).sort_index()
        
        # Nettoyer pour éviter les doublons éventuels
        self._clean_market_data(verbose=False)
        
        # Mettre à jour les informations des tickers
        self._generate_tickers_info(verbose=False)
        
        if verbose:
            print(f"Complétion terminée: {total_dates_filled} date(s) complétée(s) pour {len(tickers_modified)} ticker(s)")
        
        return True 
    
    # ===== SAUVEGARDE DES DONNÉES =====
    
    def save_market_data(self, filename=None, verbose=None):
        """
        Sauvegarde les données dans une structure de dossiers hiérarchiques:
        - Un dossier par secteur
        - Trois sous-dossiers par secteur (stocks, etfs, mutual_funds)
        - Un fichier CSV par ticker
        
        Args:
            filename (str, optional): Non utilisé. Maintenu pour compatibilité.
            verbose (bool, optional): Afficher les messages de progression. Si None, utilise self.verbose
        """
        # Déterminer si on doit être verbeux
        verbose = self.verbose if verbose is None else verbose
        
        if not self.save:
            if verbose:
                print("Sauvegarde désactivée (self.save=False)")
            return
            
        if self.market.empty:
            if verbose:
                print("Aucune donnée à sauvegarder")
            return
        
        if verbose:
            print("Sauvegarde des données en cours...")
        
        # Créer le répertoire principal si nécessaire
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # Parcourir chaque secteur
        for sector, instruments in self.instruments.items():
            # Chemin du dossier du secteur
            sector_dir = os.path.join(self.data_dir, sector)
            if not os.path.exists(sector_dir):
                os.makedirs(sector_dir)
            
            # Pour chaque type d'instrument
            for instr_type, tickers in instruments.items():
                # Chemin du dossier du type d'instrument
                type_dir = os.path.join(sector_dir, instr_type)
                if not os.path.exists(type_dir):
                    os.makedirs(type_dir)
                
                # Pour chaque ticker
                for ticker in tickers:
                    # Extraire les données du ticker
                    ticker_mask = self.market.index.get_level_values('Ticker') == ticker
                    ticker_data = self.market.loc[ticker_mask].copy()
                    
                    if ticker_data.empty:
                        continue
                    
                    # Réinitialiser l'index pour avoir la date comme colonne
                    ticker_data = ticker_data.reset_index(level='Ticker', drop=True)
                    
                    # Chemin du fichier CSV
                    ticker_file = os.path.join(type_dir, f"{ticker}.csv")
                    
                    # Sauvegarder les données du ticker
                    ticker_data.to_csv(ticker_file)
        
        total_tickers = sum(len(tickers) 
                           for sector_instrs in self.instruments.values() 
                           for tickers in sector_instrs.values())
        
        if verbose:
            print(f"Sauvegarde terminée: {total_tickers} fichiers CSV générés dans le dossier {self.data_dir}")
