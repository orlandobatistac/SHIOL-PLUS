#!/usr/bin/env python3
"""
SHIOL+ Phase 5 Pipeline Orchestrator
====================================

Main pipeline orchestrator that coordinates all 6 pipeline steps:
1. Data Update
2. Adaptive Analysis
3. Prediction Generation
4. Weight Optimization
5. Historical Validation
6. Performance Analysis

Usage:
    python main.py                    # Run full pipeline
    python main.py --step data        # Run specific step
    python main.py --status           # Check pipeline status
    python main.py --help             # Show help
"""

import argparse
import configparser
import os
import sys
import traceback
import subprocess
import requests
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# Configure logging before importing other modules
from loguru import logger
import pandas as pd
import numpy as np

# Import SHIOL+ modules
from src.loader import update_database_from_source, get_data_loader
from src.intelligent_generator import DeterministicGenerator, FeatureEngineer
from src.database import (
    initialize_database,
    get_performance_analytics,
    save_prediction_log,
    get_all_draws
)
from src.predictor import Predictor


class PipelineOrchestrator:
    """
    Main pipeline orchestrator that coordinates all SHIOL+ Phase 5 pipeline steps.
    Handles execution, error recovery, logging, and status tracking.
    """

    def __init__(self, config_path: str = "config/config.ini"):
        """
        Initialize the pipeline orchestrator.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = self._load_configuration()
        self.pipeline_status = {}
        self.execution_start_time = None
        self.historical_data = None
        self.adaptive_system = None

        # Setup logging
        self._setup_logging()

        # Initialize database
        self._initialize_database()

        logger.info("SHIOL+ Phase 5 Pipeline Orchestrator initialized")

    def _load_configuration(self) -> configparser.ConfigParser:
        """Load configuration from config.ini file."""
        try:
            config = configparser.ConfigParser()
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

            config.read(self.config_path)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config

        except Exception as e:
            print(f"ERROR: Failed to load configuration: {e}")
            sys.exit(1)

    def _setup_logging(self):
        """Configure standard logging without date corrections."""
        # Remove default handler
        logger.remove()

        # Add standard console handler
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True,
            enqueue=True,
            serialize=False,
            catch=True
        )

        logger.info("Standard logging system initialized")

    def _initialize_database(self):
        """Initialize database and ensure all tables exist."""
        try:
            initialize_database()
            logger.info("Database initialization completed")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    def run_full_pipeline(self, num_predictions=100, requested_steps=None, execution_source="scheduled_pipeline", trigger_details=None) -> Dict[str, Any]:
        """
        Execute the complete pipeline with all steps, enhanced logging, and metadata tracking.

        Args:
            num_predictions (int): Number of predictions to generate (default: 100)
            requested_steps (list): Specific steps to run, or None for all 6 steps
            execution_source (str): Source of execution ('scheduled_pipeline', 'manual_dashboard', etc.)
            trigger_details (dict): Additional trigger metadata
        """
        # Production timeout: 15 minutes maximum
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError("Pipeline execution timeout after 15 minutes")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(900)  # 15 minutes timeout
        logger.info("=" * 60)
        logger.info("STARTING SHIOL+ PHASE 5 OPTIMIZED PIPELINE EXECUTION")
        logger.info("=" * 60)

        self.execution_start_time = datetime.now()
        self.trigger_details = trigger_details  # Store trigger details for report generation
        pipeline_results = {}
        current_date = datetime.now()

        # Determine if today is a drawing day (Monday=0, Wednesday=2, Saturday=5)
        is_drawing_day = current_date.weekday() in [0, 2, 5]
        hours_after_drawing = current_date.hour >= 23  # After 11 PM ET

        logger.info(f"Pipeline execution context: Drawing day: {is_drawing_day}, After 11PM: {hours_after_drawing}")
        logger.info("Pipeline configuration: {num_predictions} predictions, Full 6-step execution")
        logger.info(f"Execution source: {execution_source}")

        try:
            # Generate execution ID if not provided (UNIFIED FORMAT)
            import uuid
            if not hasattr(self, 'current_execution_id'):
                self.current_execution_id = f"exec_{str(uuid.uuid4())[:8]}"
            
            # Save initial execution record to database
            from src.database import save_pipeline_execution
            initial_record = {
                'execution_id': self.current_execution_id,
                'status': 'starting',
                'start_time': self.execution_start_time.isoformat(),
                'trigger_type': execution_source,
                'trigger_source': execution_source,
                'steps_completed': 0,
                'total_steps': 6,
                'num_predictions': num_predictions,
                'current_step': 'initialization'
            }
            save_pipeline_execution(initial_record)
            logger.info(f"Pipeline execution {self.current_execution_id} started and saved to database")

            # Check available resources before starting
            self._check_system_resources()

            # STEP 1: Data Update & Drawing Detection (LIGHTWEIGHT)
            logger.info("STEP 1/6: Data Update & Drawing Detection (Resource-Optimized)")
            pipeline_results['data_update'] = self._execute_step('data_update', self.step_data_update)

            # STEP 2: Adaptive Analysis (Regular maintenance)
            logger.info("STEP 2/6: Adaptive Analysis (Maintenance Mode)")
            pipeline_results['adaptive_analysis'] = self._execute_step('adaptive_analysis', self.step_adaptive_analysis)

            # STEP 3: Weight Optimization (Regular optimization)
            logger.info("STEP 3/6: Weight Optimization (Scheduled)")
            pipeline_results['weight_optimization'] = self._execute_step('weight_optimization', self.step_weight_optimization)

            # STEP 4: Historical Validation (Maintenance validation)
            logger.info("STEP 4/6: Historical Validation (Maintenance)")
            pipeline_results['historical_validation'] = self._execute_step('historical_validation', self.step_historical_validation)

            # STEP 5: Prediction Generation (ALWAYS generate for next drawing)
            logger.info("STEP 5/6: Prediction Generation (Next Drawing)")
            pipeline_results['prediction_generation'] = self._execute_step('prediction_generation', self.step_prediction_generation)

            # STEP 6: Performance Analysis
            logger.info("STEP 6/6: Performance Analysis")
            pipeline_results['performance_analysis'] = self._execute_step('performance_analysis', self.step_performance_analysis)


            # Calculate execution time
            execution_time = datetime.now() - self.execution_start_time

            # Generate final summary
            pipeline_summary = self._generate_pipeline_summary(pipeline_results, execution_time)

            # Update final execution status in database
            from src.database import update_pipeline_execution
            update_pipeline_execution(self.current_execution_id, {
                'status': 'completed',
                'end_time': datetime.now().isoformat(),
                'steps_completed': pipeline_summary.get('successful_steps', 0),
                'current_step': 'completed'
            })

            logger.info("=" * 60)
            logger.info("SHIOL+ PHASE 5 PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
            logger.info(f"Total execution time: {execution_time}")
            logger.info(f"Steps completed: {pipeline_summary.get('successful_steps', 0)}/6")
            logger.info(f"Pipeline health: {pipeline_summary.get('pipeline_health', 'unknown')}")
            logger.info("=" * 60)

            return {
                'status': 'success',
                'execution_time': str(execution_time),
                'results': pipeline_results,
                'summary': pipeline_summary,
                'steps_completed': pipeline_summary.get('successful_steps', 0),
                'total_steps': 6  # Updated to 6 steps
            }

        except TimeoutError as e:
            execution_time = datetime.now() - self.execution_start_time if self.execution_start_time else None
            error_msg = f"Pipeline execution timeout: {str(e)}"
            logger.error(error_msg)

            return {
                'status': 'timeout',
                'error': error_msg,
                'execution_time': str(execution_time) if execution_time else None,
                'results': pipeline_results,
                'resource_limited': True
            }
        except Exception as e:
            execution_time = datetime.now() - self.execution_start_time if self.execution_start_time else None
            error_msg = f"Pipeline execution failed: {str(e)}"
            logger.error(error_msg)
            logger.error(f"Traceback: {traceback.format_exc()}")

            # Update failed execution status in database
            if hasattr(self, 'current_execution_id'):
                from src.database import update_pipeline_execution
                update_pipeline_execution(self.current_execution_id, {
                    'status': 'failed',
                    'end_time': datetime.now().isoformat(),
                    'error_message': error_msg,
                    'current_step': 'failed'
                })

            return {
                'status': 'failed',
                'error': error_msg,
                'execution_time': str(execution_time) if execution_time else None,
                'results': pipeline_results,
                'traceback': traceback.format_exc()
            }
        finally:
            signal.alarm(0)  # Cancel timeout

    def _execute_step(self, step_name: str, step_function) -> Dict[str, Any]:
        """
        Execute a single pipeline step with error handling.

        Args:
            step_name: Name of the step
            step_function: Function to execute

        Returns:
            Dict with step execution results
        """
        step_start_time = datetime.now()

        try:
            logger.info(f"Executing {step_name}...")
            result = step_function()

            execution_time = datetime.now() - step_start_time

            self.pipeline_status[step_name] = {
                'status': 'success',
                'execution_time': str(execution_time),
                'timestamp': datetime.now().isoformat()
            }

            # Update step completion in database
            if hasattr(self, 'current_execution_id'):
                try:
                    from src.database import update_pipeline_execution
                    steps_completed = len([s for s in self.pipeline_status.values() if s.get('status') == 'success'])
                    update_pipeline_execution(self.current_execution_id, {
                        'steps_completed': steps_completed,
                        'current_step': step_name
                    })
                except Exception as e:
                    logger.warning(f"Could not update step completion in database: {e}")

            logger.info(f"✓ {step_name} completed successfully in {execution_time}")

            return {
                'status': 'success',
                'execution_time': str(execution_time),
                'result': result,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            execution_time = datetime.now() - step_start_time
            error_msg = f"Step {step_name} failed: {str(e)}"

            self.pipeline_status[step_name] = {
                'status': 'failed',
                'error': error_msg,
                'execution_time': str(execution_time),
                'timestamp': datetime.now().isoformat()
            }

            logger.error(f"✗ {error_msg}")
            logger.error(f"Step traceback: {traceback.format_exc()}")

            return {
                'status': 'failed',
                'error': error_msg,
                'execution_time': str(execution_time),
                'timestamp': datetime.now().isoformat(),
                'traceback': traceback.format_exc()
            }

    def _calculate_next_drawing_date(self) -> str:
        """
        Calculate the next Powerball drawing date using centralized DateManager.
        Drawings are: Monday (0), Wednesday (2), Saturday (5) at 11 PM ET

        Returns:
            str: Next drawing date in YYYY-MM-DD format
        """
        from src.date_utils import DateManager

        logger.debug("Calculating next drawing date using centralized DateManager")
        return DateManager.calculate_next_drawing_date()

    def step_data_update(self) -> Dict[str, Any]:
        """
        Step 1: Data Update - Update database from source.

        Returns:
            Dict with data update results
        """
        try:
            # Update database from source
            total_rows = update_database_from_source()

            # Load updated historical data
            data_loader = get_data_loader()
            self.historical_data = data_loader.load_historical_data()

            result = {
                'total_rows_in_database': total_rows,
                'historical_data_loaded': len(self.historical_data),
                'latest_draw_date': self.historical_data['draw_date'].max().strftime('%Y-%m-%d') if not self.historical_data.empty else None
            }

            logger.info(f"Data update completed: {total_rows} total rows, {len(self.historical_data)} historical records")
            return result

        except Exception as e:
            logger.error(f"Data update step failed: {e}")
            raise

    def step_adaptive_analysis(self) -> Dict[str, Any]:
        """
        Step 2: Adaptive Analysis - Run adaptive analysis on recent data.

        Returns:
            Dict with adaptive analysis results
        """
        try:
            # Ensure we have historical data
            if self.historical_data is None or self.historical_data.empty:
                self.historical_data = get_all_draws()

            # Initialize adaptive system if not already done
            if self.adaptive_system is None:
                self.adaptive_system = initialize_adaptive_system(self.historical_data)

            # Run adaptive analysis
            analysis_results = run_adaptive_analysis(days_back=30)

            logger.info(f"Adaptive analysis completed: {analysis_results.get('total_predictions_analyzed', 0)} predictions analyzed")
            return analysis_results

        except Exception as e:
            logger.error(f"Adaptive analysis step failed: {e}")
            raise

    def _check_system_resources(self):
        """Check system resources and warn about constraints in Replit environment."""
        try:
            import psutil

            # Check memory usage
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)

            logger.info(f"System resources: Memory {memory.percent:.1f}%, CPU {cpu_percent:.1f}%")

            # Warn if resources are high (Replit has limited resources)
            if memory.percent > 80:
                logger.warning("HIGH MEMORY USAGE: Pipeline may run slowly or timeout")
            if cpu_percent > 80:
                logger.warning("HIGH CPU USAGE: Pipeline may run slowly or timeout")

            # Replit-specific resource management
            if memory.percent > 90:
                raise RuntimeError("Insufficient memory to run full pipeline safely")

        except ImportError:
            logger.warning("psutil not available - cannot monitor system resources")
        except Exception as e:
            logger.warning(f"Resource check failed: {e}")

    def step_weight_optimization(self) -> Dict[str, Any]:
        """
        Step 4: Weight Optimization - Optimize scoring weights based on performance.

        Returns:
            Dict with weight optimization results
        """
        try:
            # Ensure adaptive system is initialized
            if self.adaptive_system is None:
                if self.historical_data is None:
                    self.historical_data = get_all_draws()
                self.adaptive_system = initialize_adaptive_system(self.historical_data)

            # Get performance data for optimization
            performance_data = get_performance_analytics(30)

            # Check if we have enough data for optimization
            total_predictions = performance_data.get('total_predictions', 0)

            # If we just generated predictions in step 3, check the database directly
            if total_predictions < 10:
                try:
                    from src.database import get_prediction_history
                    recent_predictions = get_prediction_history(limit=100)
                    total_predictions = len(recent_predictions)
                    logger.info(f"Found {total_predictions} total predictions in database for optimization")
                except Exception as e:
                    logger.warning(f"Could not check recent predictions: {e}")

            if total_predictions < 5:  # Reduced threshold since we just generated predictions
                logger.warning(f"Still insufficient data for weight optimization (have {total_predictions}, need at least 5)")
                return {
                    'status': 'skipped',
                    'reason': 'insufficient_data',
                    'predictions_available': total_predictions,
                    'minimum_required': 5
                }

            logger.info(f"Proceeding with weight optimization using {total_predictions} predictions")

            # Get weight optimizer
            weight_optimizer = self.adaptive_system['weight_optimizer']

            # Get current weights (default if none exist)
            current_weights = {
                'probability': 0.40,
                'diversity': 0.25,
                'historical': 0.20,
                'risk_adjusted': 0.15
            }

            # Optimize weights
            optimized_weights = weight_optimizer.optimize_weights(
                current_weights=current_weights,
                performance_data=performance_data,
                algorithm='differential_evolution'
            )

            result = {
                'optimization_performed': optimized_weights is not None,
                'current_weights': current_weights,
                'optimized_weights': optimized_weights,
                'performance_data_used': performance_data,
                'algorithm_used': 'differential_evolution'
            }

            if optimized_weights:
                logger.info(f"Weight optimization completed: {optimized_weights}")
            else:
                logger.warning("Weight optimization failed to find better weights")

            return result

        except Exception as e:
            logger.error(f"Weight optimization step failed: {e}")
            raise

    def step_prediction_generation(self) -> Dict[str, Any]:
        """
        Step 5: Prediction Generation - Generate Smart AI predictions for next drawing (OPTIMIZED FOR REPLIT).

        FUNCIONALIDAD OPTIMIZADA PARA PRODUCCIÓN:
        - Reduce número de predicciones para evitar timeout en Replit
        - Genera 50 predicciones (en lugar de 100) para optimizar recursos
        - Calcula fecha del próximo sorteo (Lunes, Miércoles, Sábado)
        - Aplica pesos adaptativos optimizados

        Returns:
            Dict with prediction generation results including next drawing date
        """
        try:
            # NUEVA FUNCIONALIDAD: Validar modelo antes de generar predicciones
            try:
                from src.model_validator import validate_model_before_prediction, is_model_ready_for_prediction
                from src.auto_retrainer import execute_automatic_retrain_if_needed

                logger.info("Validating model quality before prediction generation...")
                model_validation = validate_model_before_prediction()

                # Check for specific issues that require retraining
                needs_retrain = False
                retrain_reason = "model_quality_acceptable"

                # Check recent performance metrics for feature mismatch
                if isinstance(model_validation.get('validation_metrics'), dict):
                    recent_perf = model_validation['validation_metrics'].get('recent_performance', {})
                    if recent_perf.get('status') == 'feature_mismatch':
                        logger.warning("Feature shape mismatch detected - forcing model retrain...")
                        needs_retrain = True
                        retrain_reason = "feature_compatibility_issue"

                # Check overall model readiness
                if not needs_retrain and not is_model_ready_for_prediction():
                    logger.warning("Model quality below acceptable threshold - attempting automatic retrain...")
                    needs_retrain = True
                    retrain_reason = "quality_below_threshold"

                if needs_retrain:
                    retrain_results = execute_automatic_retrain_if_needed()

                    if retrain_results.get('retrain_executed', False):
                        logger.info(f"Model successfully retrained due to: {retrain_reason}")
                    else:
                        logger.warning(f"Model retrain not executed despite {retrain_reason} - proceeding with caution")
                else:
                    retrain_results = {'retrain_executed': False, 'reason': retrain_reason}

            except ImportError as e:
                logger.warning(f"Model validation not available: {e}")
                model_validation = {'validation_available': False}
                retrain_results = {'retrain_executed': False, 'error': 'validation_unavailable'}
            except Exception as e:
                logger.error(f"Error during model validation: {e}")
                model_validation = {'validation_error': str(e)}
                retrain_results = {'retrain_executed': False, 'error': f'validation_error: {str(e)}'}

            # Calculate next drawing date (Monday=0, Wednesday=2, Saturday=5)
            next_drawing_date = self._calculate_next_drawing_date()
            logger.info(f"Generating predictions for next drawing date: {next_drawing_date}")

            # Initialize predictor (it loads data internally)
            predictor = Predictor()

            # Generate 100 Smart AI predictions (optimized for Replit resources)
            logger.info("Generating 100 Smart AI predictions (Replit-optimized)...")
            smart_predictions = predictor.predict_diverse_plays(
                num_plays=100,
                save_to_log=True,
                target_draw_date=next_drawing_date
            )

            # Prepare result with all 100 plays
            plays_info = []
            for i, prediction in enumerate(smart_predictions):
                play_info = {
                    'play_number': i + 1,
                    'prediction_id': prediction.get('log_id'),
                    'numbers': prediction['numbers'],
                    'powerball': prediction['powerball'],
                    'total_score': prediction['score_total'],
                    'score_details': prediction['score_details'],
                    'play_rank': prediction.get('play_rank', i + 1),
                    'method': 'smart_ai'
                }
                plays_info.append(play_info)

            # Calculate statistics
            avg_score = sum(p['score_total'] for p in smart_predictions) / len(smart_predictions)
            top_10_avg = sum(p['score_total'] for p in smart_predictions[:10]) / 10

            result = {
                'predictions_generated': True,
                'method': 'smart_ai',
                'num_plays_generated': len(smart_predictions),
                'target_drawing_date': next_drawing_date,  # NUEVA: Fecha del próximo sorteo
                'plays': plays_info,
                'statistics': {
                    'average_score': avg_score,
                    'top_10_average_score': top_10_avg,
                    'best_score': smart_predictions[0]['score_total'],
                    'worst_score': smart_predictions[-1]['score_total']
                },
                'model_version': smart_predictions[0]['model_version'],
                'dataset_hash': smart_predictions[0]['dataset_hash'],
                'candidates_evaluated': smart_predictions[0]['num_candidates_evaluated'],
                'generation_method': 'smart_ai_diverse_deterministic',
                'diversity_algorithm': 'intelligent_selection_100_plays',
                'drawing_schedule': {
                    'next_drawing_date': next_drawing_date,
                    'is_drawing_day': datetime.now().weekday() in [0, 2, 5],
                    'drawing_days': ['Monday', 'Wednesday', 'Saturday']
                },
                # Validación y reentrenamiento automático
                'model_validation': model_validation,
                'retrain_executed': retrain_results.get('retrain_executed', False) if 'retrain_results' in locals() else False
            }

            # Log summary of generated plays
            logger.info(f"Generated {len(smart_predictions)} Smart AI predictions for next drawing")
            logger.info(f"Average score: {avg_score:.4f}")
            logger.info(f"Top 10 average score: {top_10_avg:.4f}")
            logger.info(f"Best prediction: {smart_predictions[0]['numbers']} + {smart_predictions[0]['powerball']} (Score: {smart_predictions[0]['score_total']:.4f})")
            logger.info("All 100 Smart AI predictions have been saved to the database")

            return result

        except Exception as e:
            logger.error(f"Smart AI prediction generation step failed: {e}")
            raise

    def step_historical_validation(self) -> Dict[str, Any]:
        """
        Step 4: Historical Validation - Evaluate predictions against known results in database
        """
        logger.info("Starting prediction evaluation step...")

        try:
            # Check if we have new drawing data from step 1
            recent_data_update = self.pipeline_status.get('data_update', {})
            new_records = recent_data_update.get('result', {}).get('total_rows_in_database', 0)
            
            # Always evaluate, but log the context
            if new_records > 0:
                logger.info(f"🔍 New drawing data available, proceeding with evaluation of recent predictions...")
            else:
                logger.info("ℹ️ No new drawing data detected, but evaluating recent predictions for maintenance...")

            from src.prediction_evaluator import PredictionEvaluator

            # Initialize evaluator and run evaluation
            evaluator = PredictionEvaluator()
            evaluation_results = evaluator.evaluate_recent_predictions(days_back=7)

            result = {
                'evaluation_completed': True,
                'predictions_evaluated': evaluation_results.get('predictions_evaluated', 0),
                'predictions_with_prizes': evaluation_results.get('predictions_with_prizes', 0),
                'total_prize_amount': evaluation_results.get('total_prize_amount', 0),
                'best_prize': evaluation_results.get('best_prize', 0),
                'learning_enabled': True,
                'database_updated': True
            }

            logger.info(f"Prediction evaluation completed: {evaluation_results}")
            return result

        except Exception as e:
            logger.error(f"Prediction evaluation step failed: {e}")
            raise

    def step_performance_analysis(self) -> Dict[str, Any]:
        """
        Step 6: Performance Analysis - Analyze system performance metrics.

        Returns:
            Dict with performance analysis results
        """
        try:
            # Get performance analytics for different time periods
            analytics_30d = get_performance_analytics(30)
            analytics_7d = get_performance_analytics(7)
            analytics_1d = get_performance_analytics(1)

            result = {
                'analytics_30_days': analytics_30d,
                'analytics_7_days': analytics_7d,
                'analytics_1_day': analytics_1d,
                'analysis_timestamp': datetime.now().isoformat()
            }

            # Generate performance insights
            insights = []

            if analytics_30d.get('total_predictions', 0) > 0:
                win_rate = analytics_30d.get('win_rate', 0)
                avg_accuracy = analytics_30d.get('avg_accuracy', 0)

                if win_rate > 5:
                    insights.append(f"Good win rate: {win_rate:.1f}% over 30 days")
                elif win_rate > 0:
                    insights.append(f"Low win rate: {win_rate:.1f}% over 30 days")
                else:
                    insights.append("No wins recorded in the last 30 days")

                if avg_accuracy > 0.5:
                    insights.append(f"High prediction accuracy: {avg_accuracy:.1%}")
                else:
                    insights.append(f"Low prediction accuracy: {avg_accuracy:.1%}")
            else:
                insights.append("No performance data available for analysis")

            result['performance_insights'] = insights

            logger.info(f"Performance analysis completed: {len(insights)} insights generated")
            return result

        except Exception as e:
            logger.error(f"Performance analysis step failed: {e}")
            raise


    def _generate_execution_report(self) -> Dict[str, Any]:
        """Generate comprehensive execution report with enhanced metadata."""
        current_time = datetime.now()
        current_day = current_time.strftime('%A').lower()
        current_time_str = current_time.strftime('%H:%M')

        # Get scheduler configuration
        expected_days = ['monday', 'wednesday', 'saturday']
        expected_time = '23:30'
        timezone = 'America/New_York'

        # Check if execution matches expected schedule
        matches_schedule = (
            current_day in expected_days and
            abs((current_time.hour * 60 + current_time.minute) - (23 * 60 + 30)) <= 30  # 30 minute tolerance for reports
        )

        # Use provided trigger_details or create default ones
        if not hasattr(self, 'trigger_details') or self.trigger_details is None: # Check if trigger_details is set in the instance
            trigger_details = {
                "type": "scheduled" if current_day in expected_days else "manual", # Infer type based on day if not provided
                "scheduled_config": {
                    "days": expected_days,
                    "time": expected_time,
                    "timezone": timezone
                },
                "actual_execution": {
                    "day": current_day,
                    "time": current_time_str,
                    "matches_schedule": matches_schedule
                },
                "triggered_by": "automatic_scheduler" if current_day in expected_days else "user_dashboard" # Infer trigger if not provided
            }
        else:
            trigger_details = self.trigger_details # Use the provided trigger_details

        # Create comprehensive execution report
        report_data = {
            "pipeline_execution": {
                "start_time": self.execution_start_time.isoformat() if self.execution_start_time else None,
                "end_time": current_time.isoformat(),
                "total_execution_time": str(current_time - self.execution_start_time) if self.execution_start_time else None,
                "status": self.pipeline_status,
                "execution_source": "scheduled_pipeline" if current_day in expected_days else "manual_dashboard", # Simplified source based on day
                "trigger_details": trigger_details,
            },
            "system_info": {
                "config_file": self.config_path,
                "historical_data_records": len(self.historical_data) if self.historical_data is not None else 0,
                "adaptive_system_initialized": self.adaptive_system is not None,
                "execution_context": {
                    "is_drawing_day": current_day in expected_days,
                    "expected_vs_actual": {
                        "expected_days": expected_days,
                        "actual_day": current_day,
                        "expected_time": expected_time,
                        "actual_time": current_time_str,
                        "schedule_compliance": matches_schedule
                    }
                }
            },
            "generated_at": current_time.isoformat()
        }

        return report_data


    def _generate_pipeline_summary(self, pipeline_results: Dict[str, Any], execution_time) -> Dict[str, Any]:
        """Generate pipeline execution summary."""
        successful_steps = sum(1 for result in pipeline_results.values() if result.get('status') == 'success')
        total_steps = len(pipeline_results)

        return {
            'total_steps': total_steps,
            'successful_steps': successful_steps,
            'failed_steps': total_steps - successful_steps,
            'success_rate': f"{(successful_steps / total_steps * 100):.1f}%" if total_steps > 0 else "0%",
            'total_execution_time': str(execution_time),
            'pipeline_health': 'healthy' if successful_steps == total_steps else 'degraded' if successful_steps > 0 else 'failed'
        }

    def run_single_step(self, step_name: str) -> Dict[str, Any]:
        """
        Run a single pipeline step.

        Args:
            step_name: Name of the step to run

        Returns:
            Dict with step execution results
        """
        step_mapping = {
            'data': self.step_data_update,
            'data_update': self.step_data_update,
            'adaptive': self.step_adaptive_analysis,
            'adaptive_analysis': self.step_adaptive_analysis,
            'weights': self.step_weight_optimization,
            'weight_optimization': self.step_weight_optimization,
            'prediction': self.step_prediction_generation,
            'prediction_generation': self.step_prediction_generation,
            'validation': self.step_historical_validation,
            'historical_validation': self.step_historical_validation,
            'performance': self.step_performance_analysis,
            'performance_analysis': self.step_performance_analysis,
        }

        if step_name not in step_mapping:
            available_steps = list(step_mapping.keys())
            raise ValueError(f"Unknown step '{step_name}'. Available steps: {available_steps}")

        logger.info(f"Running single step: {step_name}")
        self.execution_start_time = datetime.now()

        return self._execute_step(step_name, step_mapping[step_name])

    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get current pipeline status and health information.

        Returns:
            Dict with pipeline status information
        """
        try:
            # Get basic system status
            status = {
                'timestamp': datetime.now().isoformat(),
                'database_initialized': True,  # We initialize in __init__
                'configuration_loaded': self.config is not None,
                'historical_data_available': self.historical_data is not None and not self.historical_data.empty,
                'adaptive_system_initialized': self.adaptive_system is not None,
                'recent_execution_status': self.pipeline_status
            }

            # Get database statistics
            try:
                historical_data = get_all_draws()
                performance_analytics = get_performance_analytics(7)

                # Ensure all values are converted to native Python types
                status.update({
                    'database_records': int(len(historical_data)),
                    'latest_draw_date': historical_data['draw_date'].max().strftime('%Y-%m-%d') if not historical_data.empty else None,
                    'recent_predictions': int(performance_analytics.get('total_predictions', 0)),
                    'recent_win_rate': f"{float(performance_analytics.get('win_rate', 0)):.1f}%"
                })
            except Exception as e:
                logger.warning(f"Could not retrieve database statistics: {e}")
                status['database_error'] = str(e)

            # Import and apply convert_numpy_types to ensure all numpy types are converted
            from src.api import convert_numpy_types
            return convert_numpy_types(status)

        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'status': 'error'
            }


def get_public_ip() -> Optional[str]:
    """
    Detect the public IP address of the server automatically.

    Returns:
        str: Public IP address or None if detection fails
    """
    services = [
        'https://api.ipify.org',
        'https://ipinfo.io/ip',
        'https://icanhazip.com',
        'https://ident.me'
    ]

    for service in services:
        try:
            logger.debug(f"Trying to get public IP from {service}")
            response = requests.get(service, timeout=5)
            if response.status_code == 200:
                ip = response.text.strip()
                # Basic IP validation
                if ip and '.' in ip and len(ip.split('.')) == 4:
                    logger.info(f"Public IP detected: {ip}")
                    return ip
        except Exception as e:
            logger.debug(f"Failed to get IP from {service}: {e}")
            continue

    logger.warning("Could not detect public IP address")
    return None


def start_api_server(host: str = "0.0.0.0", port: int = 3000, auto_detect_ip: bool = True):
    """
    Start the API server optimized for VPN access.

    Args:
        host: Host to bind to (default: 0.0.0.0 for external access)
        port: Port to bind to (default: 8000)
        auto_detect_ip: Whether to auto-detect and display public IP
    """
    print("🚀 Starting SHIOL+ API Server...")
    print("=" * 50)

    # Verify that we're in the correct directory
    if not os.path.exists("src/api.py"):
        print("❌ Error: src/api.py not found")
        print("   Make sure to run this script from the project root directory")
        sys.exit(1)

    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: No virtual environment detected")
        print("   It's recommended to activate the virtual environment first:")
        print("   source venv/bin/activate  # Linux/Mac")
        print("   .\\venv\\Scripts\\activate  # Windows")
        print()

    # Server configuration
    print(f"📡 Server Configuration:")
    print(f"   Host: {host} (allows external connections)")
    print(f"   Port: {port}")
    print(f"   CORS: Enabled for all origins")
    print()

    # Display access URLs
    print("🌐 Access URLs:")
    print(f"   Local: http://127.0.0.1:{port}")

    if auto_detect_ip:
        public_ip = get_public_ip()
        if public_ip:
            print(f"   External/VPN: http://{public_ip}:{port}")
            print()
            print("📱 For mobile/remote access:")
            print(f"   Use: http://{public_ip}:{port}")
        else:
            print("   External/VPN: Could not detect public IP")
            print("   Check your network configuration or use manual IP")
    print()

    print("🔧 Starting uvicorn server...")
    print("   Press Ctrl+C to stop the server")
    print("=" * 50)

    try:
        import shlex

        # Validate and sanitize inputs to prevent command injection
        # Only allow safe characters for host and validate port range
        if not re.match(r'^[0-9a-zA-Z\.-]+$', host):
            raise ValueError(f"Invalid host format: {host}")

        if not isinstance(port, int) or not (1024 <= port <= 65535):
            raise ValueError(f"Invalid port number: {port}")

        # Use manual escaping for safety and build command as list to prevent injection
        # shlex.escape() not available in Python 3.12, using manual validation
        safe_host = str(host)
        safe_port = str(port)

        # Command to start uvicorn - using list format prevents shell injection
        cmd = [
            "uvicorn",
            "src.api:app",
            "--host", safe_host,
            "--port", safe_port,
            "--reload",  # Auto-reload in development
            "--access-log",  # Access logs
            "--log-level", "info"
        ]

        # Execute the server with shell=False for additional security
        subprocess.run(cmd, check=True, shell=False)

    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting server: {e}")
        print("\n🔍 Possible solutions:")
        print("1. Install uvicorn: pip install uvicorn")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Check that the port is not in use")
    except FileNotFoundError:
        print("\n❌ Error: uvicorn not found")
        print("   Install with: pip install uvicorn")


def main():
    """Main entry point for the pipeline orchestrator."""
    parser = argparse.ArgumentParser(
        description="SHIOL+ Phase 5 Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run full pipeline
  python main.py --step data        # Run data update step only
  python main.py --step prediction  # Run prediction generation only
  python main.py --status           # Check pipeline status
  python main.py --migrate          # Execute Fase 2 date correction migration
  python main.py --server           # Start API server for VPN access
  python main.py --api --port 8080  # Start API server on custom port
  python main.py --help             # Show this help message

Available steps:
  data, weights, prediction, validation, performance

Server mode:
  --server or --api starts the web API server optimized for VPN access
  Automatically detects public IP and configures CORS for external access
        """
    )

    parser.add_argument(
        '--step',
        type=str,
        help='Run a specific pipeline step only'
    )

    parser.add_argument(
        '--status',
        action='store_true',
        help='Check pipeline status and exit'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config/config.ini',
        help='Path to configuration file (default: config/config.ini)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging output'
    )

    parser.add_argument(
        '--server',
        action='store_true',
        help='Start API server optimized for VPN access'
    )

    parser.add_argument(
        '--api',
        action='store_true',
        help='Alias for --server (start API server)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind server to (default: 0.0.0.0 for external access)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=3000,
        help='Port to bind server to (default: 3000)'
    )

    parser.add_argument(
        '--migrate',
        action='store_true',
        help='Execute data migration to fix corrupted dates (Fase 2)'
    )

    parser.add_argument(
        '--diagnose',
        action='store_true',
        help='Run comprehensive system diagnostics and health check'
    )

    parser.add_argument(
        '--predictions',
        type=int,
        default=100,
        help='Number of predictions to generate (default: 100)'
    )

    args = parser.parse_args()

    try:
        # Handle server mode
        if args.server or args.api:
            start_api_server(host=args.host, port=args.port, auto_detect_ip=True)
            return

        # Initialize pipeline orchestrator
        orchestrator = PipelineOrchestrator(config_path=args.config)

        # Handle diagnostics execution
        if args.diagnose:
            print("\n" + "=" * 60)
            print("EJECUTANDO DIAGNÓSTICO COMPLETO DEL SISTEMA")
            print("=" * 60)

            try:
                from src.system_diagnostics import SystemDiagnostics
                report = SystemDiagnostics.run_system_health_check()

                print(f"\nEstado del sistema: {report['health_status'].upper()}")

                if report['issues_found']:
                    print(f"Problemas detectados: {', '.join(report['issues_found'])}")
                    print(f"\nRecomendaciones:")
                    for rec in report['recommendations']:
                        print(f"  • {rec['issue']}: {rec['action']} (Prioridad: {rec['priority']})")
                else:
                    print("✓ No se encontraron problemas críticos")

                print(f"\nDiagnóstico de reloj:")
                clock = report['clock_diagnosis']
                print(f"  Drift detectado: {'SÍ' if clock['drift_detected'] else 'NO'}")
                print(f"  Fecha esperada: {clock['expected_date']}")
                print(f"  Fecha actual: {clock['actual_date']}")

                print(f"\nDiagnóstico de corrupción:")
                corruption = report['corruption_diagnosis']
                print(f"  Registros corruptos: {corruption['total_corrupted_records']}")

                # Save detailed report
                import json
                with open("reports/system_diagnostics.json", "w") as f:
                    json.dump(report, f, indent=2, default=str)
                print(f"\n✓ Reporte detallado guardado en: reports/system_diagnostics.json")

            except Exception as e:
                print(f"\n✗ Error ejecutando diagnósticos: {e}")
                sys.exit(1)

            print("=" * 60)
            return

        # Handle migration execution
        if args.migrate:
            print("\n" + "=" * 60)
            print("EJECUTANDO MIGRACIÓN DE CORRECCIÓN DE FECHAS - FASE 2")
            print("=" * 60)

            try:
                from src.data_migration import run_date_correction_migration
                results = run_date_correction_migration()

                print(f"\nResultados de la migración:")
                print(f"Estado: {results.get('status', 'unknown')}")
                print(f"Registros corruptos encontrados: {results.get('corrupted_records_found', 0)}")
                print(f"Registros corregidos: {results.get('records_corrected', 0)}")
                print(f"Errores de validación: {results.get('validation_failures', 0)}")

                if results.get('final_validation'):
                    validation = results['final_validation']
                    print(f"\nValidación final:")
                    print(f"Total de registros: {validation.get('total_records', 0)}")
                    print(f"Fechas válidas: {validation.get('valid_target_dates', 0)}")
                    print(f"Tasa de éxito: {validation.get('success_rate', '0%')}")

                if results.get('status') == 'completed':
                    print("\n✓ Migración completada exitosamente")
                elif results.get('status') == 'no_action_needed':
                    print("\n✓ No se encontraron datos que requieran migración")
                else:
                    print("\n✗ Migración falló")
                    if results.get('errors'):
                        for error in results['errors']:
                            print(f"  Error: {error}")

            except Exception as e:
                print(f"\n✗ Error ejecutando migración: {e}")
                sys.exit(1)

            print("=" * 60)
            return

        # Handle status check
        if args.status:
            status = orchestrator.get_pipeline_status()
            print("\n" + "=" * 50)
            print("SHIOL+ PIPELINE STATUS")
            print("=" * 50)

            for key, value in status.items():
                if key != 'recent_execution_status':
                    print(f"{key.replace('_', ' ').title()}: {value}")

            if status.get('recent_execution_status'):
                print("\nRecent Execution Status:")
                for step, step_status in status['recent_execution_status'].items():
                    status_symbol = "✓" if step_status.get('status') == 'success' else "✗"
                    print(f"  {status_symbol} {step}: {step_status.get('status', 'unknown')}")

            print("=" * 50)
            return

        # Handle single step execution
        if args.step:
            result = orchestrator.run_single_step(args.step)

            print(f"\nStep '{args.step}' execution result:")
            print(f"Status: {result.get('status', 'unknown')}")
            print(f"Execution time: {result.get('execution_time', 'unknown')}")

            if result.get('status') == 'failed':
                print(f"Error: {result.get('error', 'unknown error')}")
                sys.exit(1)
            else:
                print("Step completed successfully!")
            return

        # Run full pipeline with proper parameters (UNIFIED APPROACH)
        # Get execution ID from environment if set by API
        import os
        if os.environ.get('PIPELINE_EXECUTION_ID'):
            orchestrator.current_execution_id = os.environ.get('PIPELINE_EXECUTION_ID')
            
        # Use predictions argument
        num_predictions = args.predictions
        
        # Set trigger_details for dashboard execution if available, otherwise use defaults
        if args.server or args.api: # If server is started, it might be triggered by dashboard/external call
            # In a real scenario, 'trigger_details' would be passed from the API handler
            # For this example, we'll simulate it based on the presence of server args.
            # If triggered via the CLI with --server, we can infer it's not a scheduled run.
            simulated_trigger_details = {
                "type": "manual",
                "scheduled_config": None, # Not applicable for manual trigger
                "actual_execution": {
                    "day": datetime.now().strftime('%A').lower(),
                    "time": datetime.now().strftime('%H:%M'),
                    "matches_schedule": False # Assume no match if manually triggered
                },
                "triggered_by": "user_dashboard"
            }
            result = orchestrator.run_full_pipeline(
                num_predictions=num_predictions,
                execution_source="manual_dashboard",
                trigger_details=simulated_trigger_details
            )
        else:
            # Default to scheduled pipeline if not running in server mode
            execution_source = os.environ.get('PIPELINE_EXECUTION_SOURCE', 'scheduled_pipeline')
            result = orchestrator.run_full_pipeline(
                num_predictions=num_predictions,
                execution_source=execution_source
            )


        # Print results summary
        print("\n" + "=" * 60)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Execution time: {result.get('execution_time', 'unknown')}")

        if result.get('summary'):
            summary = result['summary']
            print(f"Steps completed: {summary.get('successful_steps', 0)}/{summary.get('total_steps', 0)}")
            print(f"Success rate: {summary.get('success_rate', '0%')}")
            print(f"Pipeline health: {summary.get('pipeline_health', 'unknown')}")

        if result.get('status') == 'failed':
            print(f"Error: {result.get('error', 'unknown error')}")
            sys.exit(1)
        else:
            print("Pipeline execution completed successfully!")

    except KeyboardInterrupt:
        print("\nPipeline execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        if args.verbose:
            print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


# Import the FastAPI app for deployment compatibility
try:
    from src.api import app
except ImportError as e:
    # Fallback FastAPI app if main API fails to load
    logger.warning(f"Failed to import main API: {e}")
    from fastapi import FastAPI
    
    app = FastAPI(title="SHIOL+ Fallback API", version="3.0.0")
    
    @app.get("/")
    async def fallback_root():
        return {"error": "API failed to load", "fallback": True}
    
    @app.get("/health")
    async def fallback_health():
        return {"status": "fallback", "error": "Main API failed to load"}

if __name__ == "__main__":
    main()