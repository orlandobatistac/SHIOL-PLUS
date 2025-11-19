"""
SHIOL+ Batch Ticket Pre-Generation System
==========================================
Background processing module for pre-generating lottery tickets using ML models.

This module generates tickets in the background using threading, stores them in
the database, and provides fast retrieval for API endpoints.

Features:
- Background ticket generation (doesn't block main pipeline or API)
- Support for multiple prediction modes (random_forest, lstm)
- Error handling per mode (if one fails, continue with others)
- Optimized for 2 CPU cores
- Auto-cleanup of old tickets
- Comprehensive logging and metrics

Usage:
    # Initialize batch generator
    batch_gen = BatchTicketGenerator(batch_size=100, modes=['random_forest', 'lstm'])
    
    # Generate tickets in background
    batch_gen.generate_batch(pipeline_run_id="pipeline_2025-11-18")
    
    # Check status
    status = batch_gen.get_status()
"""

import threading
import time
from typing import List, Dict, Optional, Any
from loguru import logger
from datetime import datetime

# Import database functions
from src.database import insert_batch_tickets, clear_old_batch_tickets, get_batch_ticket_stats

# Import prediction engine
from src.prediction_engine import UnifiedPredictionEngine


class BatchTicketGenerator:
    """
    Batch ticket pre-generation system for background processing.
    
    This class manages background generation of lottery tickets using various
    prediction modes. Tickets are stored in the database for fast retrieval.
    
    Architecture:
    - Uses threading.Thread with daemon=True for background execution
    - Doesn't block main pipeline or API
    - Handles errors gracefully per mode
    - Optimized for 2 CPU cores
    
    Attributes:
        batch_size: Number of tickets to generate per mode
        modes: List of prediction modes to use
        generation_metrics: Statistics about generation runs
    """
    
    def __init__(
        self,
        batch_size: int = 100,
        modes: Optional[List[str]] = None,
        auto_cleanup: bool = True,
        cleanup_days: int = 7
    ):
        """
        Initialize BatchTicketGenerator.
        
        Args:
            batch_size: Number of tickets to generate per mode (default: 100)
            modes: List of prediction modes to use. If None, uses ['random_forest', 'lstm']
            auto_cleanup: Whether to automatically clean up old tickets (default: True)
            cleanup_days: Days to keep tickets before cleanup (default: 7)
        """
        self.batch_size = batch_size
        self.modes = modes or ['random_forest', 'lstm']
        self.auto_cleanup = auto_cleanup
        self.cleanup_days = cleanup_days
        
        # Validate modes
        valid_modes = ['random_forest', 'lstm', 'v1', 'v2', 'hybrid']
        for mode in self.modes:
            if mode not in valid_modes:
                logger.warning(
                    f"Invalid mode '{mode}' will be skipped. "
                    f"Valid modes: {valid_modes}"
                )
        
        # Filter to valid modes
        self.modes = [m for m in self.modes if m in valid_modes]
        
        if not self.modes:
            logger.warning("No valid modes provided, defaulting to ['random_forest', 'lstm']")
            self.modes = ['random_forest', 'lstm']
        
        # Generation state
        self._generation_thread = None
        self._is_generating = False
        self._generation_metrics = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'last_run_time': None,
            'last_run_status': None,
            'last_run_duration': None,
            'tickets_generated': 0,
            'by_mode': {}
        }
        
        logger.info(
            f"BatchTicketGenerator initialized: "
            f"batch_size={batch_size}, modes={self.modes}, "
            f"auto_cleanup={auto_cleanup}, cleanup_days={cleanup_days}"
        )
    
    def generate_batch(
        self,
        pipeline_run_id: Optional[str] = None,
        async_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a batch of tickets for all configured modes.
        
        This method can run synchronously or asynchronously (default).
        In async mode, it starts a background thread and returns immediately.
        In sync mode, it blocks until generation completes.
        
        Args:
            pipeline_run_id: Optional pipeline execution ID for tracking
            async_mode: If True, run in background thread (default: True)
        
        Returns:
            Dictionary with generation status:
            {
                'started': bool,
                'async': bool,
                'modes': List[str],
                'batch_size': int,
                'pipeline_run_id': str
            }
        """
        if self._is_generating:
            logger.warning("Batch generation already in progress, skipping new request")
            return {
                'started': False,
                'error': 'Generation already in progress',
                'async': async_mode
            }
        
        # Auto-cleanup old tickets if enabled
        if self.auto_cleanup:
            try:
                self._cleanup_old_tickets()
            except Exception as e:
                logger.warning(f"Auto-cleanup failed (continuing anyway): {e}")
        
        if async_mode:
            # Start background thread
            self._generation_thread = threading.Thread(
                target=self._generate_batch_internal,
                args=(pipeline_run_id,),
                daemon=True,  # Thread will terminate when main process exits
                name=f"BatchGen-{pipeline_run_id or 'unknown'}"
            )
            self._generation_thread.start()
            
            logger.info(
                f"Batch generation started in background: "
                f"modes={self.modes}, batch_size={self.batch_size}, "
                f"pipeline_run_id={pipeline_run_id}"
            )
            
            return {
                'started': True,
                'async': True,
                'modes': self.modes,
                'batch_size': self.batch_size,
                'pipeline_run_id': pipeline_run_id
            }
        else:
            # Run synchronously
            result = self._generate_batch_internal(pipeline_run_id)
            return {
                'started': True,
                'async': False,
                'result': result
            }
    
    def _generate_batch_internal(self, pipeline_run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Internal method to generate tickets (runs in thread or synchronously).
        
        This method:
        1. Generates tickets for each mode
        2. Stores tickets in database
        3. Updates metrics
        4. Handles errors per mode (continues if one mode fails)
        
        Args:
            pipeline_run_id: Optional pipeline execution ID for tracking
        
        Returns:
            Dictionary with generation results
        """
        self._is_generating = True
        start_time = time.time()
        
        logger.info(
            f"[BatchGen] Starting ticket generation: "
            f"modes={self.modes}, batch_size={self.batch_size}"
        )
        
        results = {
            'success': True,
            'modes_processed': [],
            'modes_failed': [],
            'total_tickets': 0,
            'by_mode': {},
            'errors': {},
            'duration_seconds': 0,
            'pipeline_run_id': pipeline_run_id
        }
        
        try:
            # Generate tickets for each mode
            for mode in self.modes:
                logger.info(f"[BatchGen] Generating tickets for mode: {mode}")
                
                try:
                    # Generate tickets using prediction engine
                    mode_start = time.time()
                    tickets = self._generate_tickets_for_mode(mode, self.batch_size)
                    mode_duration = time.time() - mode_start
                    
                    if not tickets:
                        logger.warning(f"[BatchGen] No tickets generated for mode: {mode}")
                        results['modes_failed'].append(mode)
                        results['errors'][mode] = "No tickets generated"
                        continue
                    
                    # Store tickets in database
                    inserted = insert_batch_tickets(tickets, mode, pipeline_run_id)
                    
                    # Update results
                    results['modes_processed'].append(mode)
                    results['total_tickets'] += inserted
                    results['by_mode'][mode] = {
                        'tickets': inserted,
                        'duration_seconds': round(mode_duration, 2)
                    }
                    
                    logger.info(
                        f"[BatchGen] ✓ Mode {mode}: {inserted} tickets in {mode_duration:.2f}s"
                    )
                    
                except Exception as e:
                    logger.error(f"[BatchGen] ✗ Mode {mode} failed: {e}")
                    logger.exception("Full traceback:")
                    results['modes_failed'].append(mode)
                    results['errors'][mode] = str(e)
                    # Continue with next mode (don't halt entire batch)
            
            # Calculate total duration
            results['duration_seconds'] = round(time.time() - start_time, 2)
            
            # Update metrics
            self._update_metrics(results)
            
            # Determine overall success
            if results['modes_failed'] and not results['modes_processed']:
                results['success'] = False
                logger.error(
                    f"[BatchGen] ✗ Batch generation FAILED: "
                    f"All modes failed, no tickets generated"
                )
            elif results['modes_failed']:
                results['success'] = True  # Partial success
                logger.warning(
                    f"[BatchGen] ⚠ Batch generation PARTIAL: "
                    f"{len(results['modes_processed'])} succeeded, "
                    f"{len(results['modes_failed'])} failed"
                )
            else:
                logger.info(
                    f"[BatchGen] ✓ Batch generation COMPLETE: "
                    f"{results['total_tickets']} tickets in {results['duration_seconds']}s"
                )
            
        except Exception as e:
            logger.error(f"[BatchGen] ✗ Batch generation EXCEPTION: {e}")
            logger.exception("Full traceback:")
            results['success'] = False
            results['error'] = str(e)
        finally:
            self._is_generating = False
        
        return results
    
    def _generate_tickets_for_mode(self, mode: str, count: int) -> List[Dict[str, Any]]:
        """
        Generate tickets for a specific prediction mode.
        
        Args:
            mode: Prediction mode ('random_forest', 'lstm', etc.)
            count: Number of tickets to generate
        
        Returns:
            List of ticket dictionaries
            
        Raises:
            Exception: If ticket generation fails
        """
        try:
            # Initialize prediction engine for this mode
            engine = UnifiedPredictionEngine(mode=mode)
            
            # Generate tickets
            tickets = engine.generate_tickets(count=count)
            
            return tickets
            
        except Exception as e:
            logger.error(f"Failed to generate tickets for mode {mode}: {e}")
            raise
    
    def _cleanup_old_tickets(self):
        """
        Clean up old pre-generated tickets from the database.
        
        Removes tickets older than self.cleanup_days.
        """
        try:
            deleted = clear_old_batch_tickets(days=self.cleanup_days)
            if deleted > 0:
                logger.info(f"[BatchGen] Cleaned up {deleted} old tickets (>{self.cleanup_days} days)")
        except Exception as e:
            logger.error(f"[BatchGen] Cleanup failed: {e}")
            raise
    
    def _update_metrics(self, results: Dict[str, Any]):
        """
        Update generation metrics based on results.
        
        Args:
            results: Generation results dictionary
        """
        self._generation_metrics['total_runs'] += 1
        
        if results['success']:
            self._generation_metrics['successful_runs'] += 1
        else:
            self._generation_metrics['failed_runs'] += 1
        
        self._generation_metrics['last_run_time'] = datetime.now().isoformat()
        self._generation_metrics['last_run_status'] = 'success' if results['success'] else 'failed'
        self._generation_metrics['last_run_duration'] = results.get('duration_seconds')
        self._generation_metrics['tickets_generated'] += results.get('total_tickets', 0)
        
        # Update per-mode metrics
        for mode, mode_data in results.get('by_mode', {}).items():
            if mode not in self._generation_metrics['by_mode']:
                self._generation_metrics['by_mode'][mode] = {
                    'total_tickets': 0,
                    'total_runs': 0,
                    'avg_duration': 0
                }
            
            mode_metrics = self._generation_metrics['by_mode'][mode]
            mode_metrics['total_tickets'] += mode_data['tickets']
            mode_metrics['total_runs'] += 1
            
            # Update rolling average duration
            prev_avg = mode_metrics['avg_duration']
            prev_count = mode_metrics['total_runs'] - 1
            new_duration = mode_data['duration_seconds']
            
            if prev_count > 0:
                mode_metrics['avg_duration'] = (
                    (prev_avg * prev_count + new_duration) / mode_metrics['total_runs']
                )
            else:
                mode_metrics['avg_duration'] = new_duration
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of batch generator.
        
        Returns:
            Dictionary with status information:
            {
                'is_generating': bool,
                'configured_modes': List[str],
                'batch_size': int,
                'metrics': dict,
                'db_stats': dict
            }
        """
        try:
            # Get database stats
            db_stats = get_batch_ticket_stats()
        except Exception as e:
            logger.error(f"Failed to get DB stats: {e}")
            db_stats = {'error': str(e)}
        
        return {
            'is_generating': self._is_generating,
            'configured_modes': self.modes,
            'batch_size': self.batch_size,
            'auto_cleanup': self.auto_cleanup,
            'cleanup_days': self.cleanup_days,
            'metrics': self._generation_metrics,
            'db_stats': db_stats
        }
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for current generation to complete.
        
        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)
        
        Returns:
            True if generation completed, False if timeout
        """
        if not self._generation_thread or not self._is_generating:
            return True
        
        try:
            self._generation_thread.join(timeout=timeout)
            return not self._is_generating
        except Exception as e:
            logger.error(f"Error waiting for generation: {e}")
            return False
