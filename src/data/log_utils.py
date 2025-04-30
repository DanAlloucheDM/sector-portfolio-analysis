"""
Module d'utilitaires pour la gestion des logs.

Ce module fournit des fonctions pour contrôler les logs lors de l'utilisation
de bibliothèques externes comme yfinance.
"""

# ===== IMPORTS STANDARDS =====
import logging
import warnings

def disable_logs():
    """
    Désactive les logs de yfinance et les warnings pandas.
    
    Returns:
        dict: Niveaux de log originaux pour pouvoir les restaurer ultérieurement
    """
    original_log_levels = {}
    
    # Désactiver les loggers de yfinance
    for logger_name in ['yfinance', 'yahoo.search', 'yahoo.utils', 'yahoo.search.searchapp', 'yahoo.session']:
        logger = logging.getLogger(logger_name)
        original_log_levels[logger_name] = logger.level
        logger.setLevel(logging.CRITICAL + 1)  # Au-dessus de CRITICAL pour tout désactiver
    
    # Désactiver les warnings pandas
    warnings.filterwarnings("ignore", category=Warning)
    
    return original_log_levels

def restore_logs(original_log_levels):
    """
    Restaure les niveaux de log originaux.
    
    Args:
        original_log_levels (dict): Niveaux de log à restaurer, généralement obtenus via disable_logs()
    """
    # Restaurer les loggers
    for logger_name, level in original_log_levels.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Restaurer les warnings pandas
    warnings.resetwarnings() 