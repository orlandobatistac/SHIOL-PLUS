# Comandos Quick Reference - SHIOL+ Predictions

## 🔄 Repoblar TODOS los Recent Draws (50 más recientes)

**DEFAULT: Elimina TODA la base de datos y regenera desde cero**

```bash
# Repopular los 50 draws más recientes (frontend) - BORRA TODO primero
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/populate_recent_draws.py

# Ver qué haría sin ejecutar (dry run)
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/populate_recent_draws.py --dry-run

# Repopular más draws (ej: 100 más recientes)
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/populate_recent_draws.py --limit 100

# Repopular con menos tickets por draw
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/populate_recent_draws.py --tickets 300

# MODO INCREMENTAL: Solo genera para draws sin predicciones (NO borra)
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/populate_recent_draws.py --incremental
```

## Ver tickets por fecha de sorteo (últimos 90 días)

```bash
cd /var/www/SHIOL-PLUS && sqlite3 data/shiolplus.db "
SELECT
    pd.draw_date,
    COALESCE(COUNT(gt.id), 0) as total_tickets
FROM powerball_draws pd
LEFT JOIN generated_tickets gt ON pd.draw_date = gt.draw_date
WHERE pd.draw_date >= date('now', '-90 days')
GROUP BY pd.draw_date
ORDER BY pd.draw_date DESC;
"
```

## Regenerar predicciones para una fecha específica

```bash
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/regenerate_predictions_for_draw.py --draw-date 2025-11-17 --tickets 500
```

### Ejemplos para otras fechas:

```bash
# Sorteo del 15 de noviembre
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/regenerate_predictions_for_draw.py --draw-date 2025-11-15 --tickets 500

# Sorteo del 12 de noviembre
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/regenerate_predictions_for_draw.py --draw-date 2025-11-12 --tickets 500

# Sorteo del 10 de noviembre
cd /var/www/SHIOL-PLUS && /root/.venv_shiolplus/bin/python scripts/regenerate_predictions_for_draw.py --draw-date 2025-11-10 --tickets 500
```

## Regenerar múltiples fechas en un solo comando

```bash
cd /var/www/SHIOL-PLUS && for date in 2025-11-17 2025-11-15 2025-11-12 2025-11-10 2025-11-05; do
    echo "Procesando $date..."
    /root/.venv_shiolplus/bin/python scripts/regenerate_predictions_for_draw.py --draw-date $date --tickets 500
    echo "---"
done
```
