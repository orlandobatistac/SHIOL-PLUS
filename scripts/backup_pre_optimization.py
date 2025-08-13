
#!/usr/bin/env python3
"""
Backup script para el proyecto SHIOL+ antes de la optimización del pipeline
Crea copias de seguridad de la base de datos, modelos y configuraciones críticas
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
import json
from loguru import logger

def create_backup():
    """Crear backup completo del proyecto antes de optimización"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"data/backups/pre_optimization_{timestamp}"
    
    try:
        # Crear directorio de backup
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup de la base de datos
        if os.path.exists("data/shiolplus.db"):
            shutil.copy2("data/shiolplus.db", f"{backup_dir}/shiolplus_pre_opt.db")
            logger.info("✅ Database backed up")
        
        # Backup de modelos
        if os.path.exists("models/shiolplus.pkl"):
            os.makedirs(f"{backup_dir}/models", exist_ok=True)
            shutil.copy2("models/shiolplus.pkl", f"{backup_dir}/models/shiolplus.pkl")
            logger.info("✅ Model backed up")
        
        # Backup de configuraciones
        if os.path.exists("config/config.ini"):
            os.makedirs(f"{backup_dir}/config", exist_ok=True)
            shutil.copy2("config/config.ini", f"{backup_dir}/config/config.ini")
            logger.info("✅ Config backed up")
        
        # Crear manifiesto del backup
        manifest = {
            "backup_date": datetime.now().isoformat(),
            "version": "SHIOL+ v6.0",
            "purpose": "Pre-optimization backup",
            "files_backed_up": [
                "data/shiolplus.db",
                "models/shiolplus.pkl", 
                "config/config.ini"
            ],
            "backend_optimization_plan": "v6.0 pipeline streamlining"
        }
        
        with open(f"{backup_dir}/backup_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"🎯 Backup completo creado en: {backup_dir}")
        return backup_dir
        
    except Exception as e:
        logger.error(f"❌ Error creating backup: {e}")
        return None

if __name__ == "__main__":
    create_backup()
