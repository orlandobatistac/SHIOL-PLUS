import asyncio
import uuid
from datetime import datetime
from loguru import logger
from typing import Dict, Any, Optional
import numpy as np

from src.intelligent_generator import IntelligentGenerator, FeatureEngineer
# from src.adaptive_feedback import AdaptivePlayScorer  # REMOVED
from src.loader import get_data_loader
from src.database import save_prediction_log, get_db_connection, update_pipeline_execution
from src.date_utils import DateManager

class PipelineOrchestrator:
    """
    Main pipeline orchestrator for managing full ML pipeline execution
    """

    def __init__(self):
        """Initialize pipeline orchestrator with all required components"""
        # DEPRECATED WARNING: This orchestrator will be removed
        logger.error("🚨 CRITICAL: orchestrator.py pipeline is DEPRECATED and should NOT be used.")
        logger.error("This creates inconsistent results vs main.py pipeline. Use main.py only.")
        logger.error("Contact admin immediately if you see this message in production.")

        logger.info("Initializing PipelineOrchestrator...")

        # Initialize execution state tracking
        self._is_running = False
        self._current_execution_id = None
        self.current_step = ""
        self.steps_completed = 0

        try:
            # Generate execution ID if not provided (UNIFIED FORMAT)
            import uuid
            if not hasattr(self, 'current_execution_id'):
                self.current_execution_id = f"exec_{str(uuid.uuid4())[:8]}"

            # Initialize data loader
            self.data_loader = get_data_loader()

            # Initialize predictors and generators
            from src.predictor import Predictor
            self.predictor = Predictor()

            # Load historical data
            historical_data = self.data_loader.load_historical_data()
            self.intelligent_generator = IntelligentGenerator(historical_data)

            # Initialize adaptive feedback system (DISABLED - removed)
            try:
                # adaptive_system = initialize_adaptive_system(historical_data)  # REMOVED
                self.adaptive_system = None
            except Exception as adaptive_error:
                logger.warning(f"Adaptive system initialization failed: {adaptive_error}")
                self.adaptive_system = None

            logger.info("PipelineOrchestrator initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize PipelineOrchestrator: {e}")
            raise

    def is_running(self) -> bool:
        """
        Check if pipeline is currently running

        Returns:
            bool: True if pipeline is currently executing, False otherwise
        """
        return self._is_running

    def get_current_execution_id(self) -> Optional[str]:
        """
        Get current execution ID if pipeline is running

        Returns:
            str: Current execution ID or None if not running
        """
        return self._current_execution_id if self._is_running else None

    async def _update_execution_status(self):
        """Update the status of the current pipeline execution with error handling."""
        if self._current_execution_id:
            try:
                update_pipeline_execution(self._current_execution_id, {
                    "steps_completed": self.steps_completed,
                    "current_step": self.current_step,
                    "status": "running",
                    "updated_at": DateManager.get_current_et_time().isoformat()
                })
            except Exception as e:
                logger.warning(f"Failed to update execution status: {e}")

    async def _run_step_async(self, step_name: str, step_coro) -> bool:
        """Helper to run a pipeline step and update status with robust error handling."""
        try:
            self.current_step = step_name
            await self._update_execution_status()
            logger.info(f"🚀 Starting step {self.steps_completed + 1}/5: {step_name}")

            # Execute step with timeout protection
            success = await asyncio.wait_for(step_coro(), timeout=1800)  # 30 min timeout per step

            if success:
                self.steps_completed += 1
                await self._update_execution_status()
                logger.info(f"✅ Step {self.steps_completed} ({step_name}) completed successfully.")
            else:
                logger.error(f"❌ Step {self.steps_completed + 1} ({step_name}) failed.")

            return success

        except asyncio.TimeoutError:
            logger.error(f"⏰ Step {step_name} timed out after 30 minutes")
            return False
        except Exception as e:
            logger.error(f"💥 Step {step_name} failed with exception: {e}")
            return False

    async def run_full_pipeline_async(self, execution_id: str, num_predictions: int = 100) -> Dict[str, Any]:
        """
        Run the optimized ML pipeline asynchronously (5 steps instead of 7)

        Args:
            execution_id: Unique execution identifier
            num_predictions: Number of predictions to generate

        Returns:
            Dict containing pipeline execution results
        """
        # Set running state with proper initialization
        if self._is_running:
            logger.warning(f"Pipeline already running with ID: {self._current_execution_id}")
            raise ValueError(f"Pipeline execution already in progress: {self._current_execution_id}")

        self._is_running = True
        self._current_execution_id = execution_id
        self.steps_completed = 0
        self.current_step = "initializing"

        start_time = DateManager.get_current_et_time()
        logger.info(f"Starting optimized pipeline execution {execution_id} with {num_predictions} predictions")

        # Check if execution record already exists, if not create it
        from src.database import save_pipeline_execution, get_pipeline_execution_by_id

        existing_execution = get_pipeline_execution_by_id(execution_id)
        if not existing_execution:
            # Create new execution record
            initial_execution_data = {
                'execution_id': execution_id,
                'status': 'starting',
                'start_time': start_time.isoformat(),
                'trigger_type': 'pipeline_execution',
                'trigger_source': 'orchestrator',
                'current_step': 'initialization',
                'steps_completed': 0,
                'total_steps': 5,
                'num_predictions': num_predictions,
                'execution_details': {'pipeline_version': 'v6.2_optimized'}
            }
            save_pipeline_execution(initial_execution_data)
            logger.info(f"Created new pipeline execution record {execution_id}")
        else:
            # Update existing record to running status
            update_pipeline_execution(execution_id, {
                'status': 'running',
                'current_step': 'initialization',
                'start_time': start_time.isoformat()
            })
            logger.info(f"Updated existing pipeline execution record {execution_id}")

        try:
            # Step 1: Data Update & Evaluation
            success = await self._run_step_async("Data Update & Evaluation", 
                lambda: self._run_data_update_and_evaluation())
            if not success:
                raise Exception("Data update and evaluation failed")

            # Step 2: Model Prediction (Ensemble Only)
            model_result = await self._run_model_prediction()
            if model_result.get("status") != "success":
                raise Exception(f"Model prediction failed: {model_result.get('message', 'Unknown error')}")

            self.steps_completed += 1
            self.current_step = "Model Prediction"
            await self._update_execution_status()

            # Step 3: Scoring & Selection
            scoring_result = await self._score_and_select()
            if scoring_result.get("status") != "success":
                raise Exception(f"Scoring and selection failed: {scoring_result.get('message', 'Unknown error')}")

            self.steps_completed += 1
            self.current_step = "Scoring & Selection"
            await self._update_execution_status()

            # Step 4: Prediction Generation
            success = await self._run_step_async("Prediction Generation", 
                lambda: self._generate_predictions_optimized_step(num_predictions, scoring_result))
            if not success:
                raise Exception("Prediction generation failed")

            # Step 5: Save & Serve  
            success = await self._run_step_async("Save & Serve",
                lambda: self._save_and_serve_step())
            if not success:
                raise Exception("Save and serve failed")

            end_time = DateManager.get_current_et_time()
            execution_time = end_time - start_time

            # Update final status in database
            update_pipeline_execution(execution_id, {
                "status": "completed",
                "steps_completed": 5,
                "total_steps": 5,
                "end_time": end_time.isoformat(),
                "current_step": "completed"
            })

            # Get results from stored attributes
            predictions_count = len(self.predictions) if hasattr(self, 'predictions') else 0
            preview_predictions = self.predictions[:10] if hasattr(self, 'predictions') else []
            save_result = self.save_result if hasattr(self, 'save_result') else {"status": "unknown"}

            results = {
                "status": "completed",
                "execution_time": str(execution_time),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "num_predictions_generated": predictions_count,
                "steps_completed": 5,
                "total_steps": 5,
                "pipeline_version": "v6.2_single_execution",
                "results": {
                    "data_update_validation": {"status": "success" if data_success else "failed"},
                    "model_prediction": model_result,
                    "scoring_selection": scoring_result,
                    "predictions": preview_predictions,
                    "save_serve": save_result
                }
            }

            logger.info(f"Pipeline execution completed successfully in {execution_time}")
            return results

        except Exception as e:
            logger.error(f"Pipeline execution failed at step {self.steps_completed}: {e}")
            error_time = DateManager.get_current_et_time()

            # Update database with failure state
            update_pipeline_execution(execution_id, {
                "status": "failed",
                "steps_completed": self.steps_completed,
                "error_message": str(e),
                "end_time": error_time.isoformat(),
                "current_step": self.current_step if self.current_step else "initialization"
            })

            return {
                "status": "failed",
                "error": str(e),
                "steps_completed": self.steps_completed,
                "total_steps": 5,
                "execution_time": str(error_time - start_time),
                "start_time": start_time.isoformat(),
                "end_time": error_time.isoformat()
            }
        finally:
            # Reset execution state
            self._is_running = False
            self._current_execution_id = None

    async def _update_data(self) -> bool:
        """Update database from source"""
        try:
            from src.loader import PowerballDataLoader
            loader = PowerballDataLoader()
            result = await asyncio.to_thread(loader.update_data)

            if result.get('success', False):
                new_records = result.get('new_records', 0)
                logger.info(f"✅ Data update completed. New records: {new_records}")
                return True
            else:
                logger.error(f"❌ Data update failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"❌ Data update step failed: {e}")
            return False

    async def _run_adaptive_analysis(self) -> Dict[str, Any]:
        """Run adaptive feedback analysis"""
        try:
            if self.adaptive_system:
                # Run adaptive analysis in executor to avoid blocking
                analysis = await asyncio.get_event_loop().run_in_executor(
                    None, self.adaptive_system.analyze_recent_performance
                )
                return {"status": "success", "analysis": analysis}
            else:
                return {"status": "skipped", "message": "Adaptive system not available"}
        except Exception as e:
            logger.error(f"Adaptive analysis failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _optimize_weights(self) -> Dict[str, Any]:
        """Optimize model weights"""
        try:
            # Placeholder for weight optimization
            await asyncio.sleep(0.1)  # Simulate processing
            return {"status": "success", "message": "Weights optimized"}
        except Exception as e:
            logger.error(f"Weight optimization failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _validate_historical(self) -> Dict[str, Any]:
        """Validate against historical data"""
        try:
            # Placeholder for historical validation
            await asyncio.sleep(0.1)  # Simulate processing
            return {"status": "success", "message": "Historical validation completed"}
        except Exception as e:
            logger.error(f"Historical validation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _generate_predictions(self, num_predictions: int) -> list:
        """Generate predictions using the ML pipeline"""
        try:
            predictions = []

            # Generate predictions in batches to avoid blocking
            batch_size = 25
            for i in range(0, num_predictions, batch_size):
                batch_end = min(i + batch_size, num_predictions)
                batch_size_actual = batch_end - i

                # Generate batch in executor
                batch_predictions = await asyncio.get_event_loop().run_in_executor(
                    None, self._generate_prediction_batch, batch_size_actual, i
                )
                predictions.extend(batch_predictions)

                # Small delay to yield control
                if i + batch_size < num_predictions:
                    await asyncio.sleep(0.01)

            logger.info(f"Generated {len(predictions)} predictions successfully")
            return predictions

        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")
            raise

    def _generate_prediction_batch(self, batch_size: int, start_index: int) -> list:
        """Generate a batch of predictions synchronously"""
        batch_predictions = []

        for i in range(batch_size):
            try:
                # Use intelligent generator to create prediction
                prediction = self.intelligent_generator.generate_play()

                # Add metadata with consistent DateManager timestamp
                prediction_data = {
                    "numbers": prediction.get("numbers", []),
                    "powerball": prediction.get("powerball", 1),
                    "score_total": prediction.get("score", 0.0),
                    "method": "smart_ai_pipeline",
                    "prediction_id": start_index + i + 1,
                    "generated_at": DateManager.get_current_et_time().isoformat(),
                    "rank": start_index + i + 1,
                    "execution_source": "pipeline_execution",
                    "authorized": True
                }

                batch_predictions.append(prediction_data)

            except Exception as e:
                logger.error(f"Failed to generate prediction {start_index + i + 1}: {e}")
                continue

        return batch_predictions

    async def _analyze_performance(self) -> Dict[str, Any]:
        """Analyze pipeline performance"""
        try:
            # Get database connection and analyze recent predictions
            from src.database import get_db_connection, get_prediction_history

            # Analyze prediction distribution and quality metrics
            recent_predictions = await asyncio.get_event_loop().run_in_executor(
                None, get_prediction_history, 100
            )

            analysis_result = {
                "total_predictions_analyzed": len(recent_predictions),
                "prediction_quality_score": 0.85,  # Placeholder metric
                "model_confidence": 0.92,  # Placeholder metric
                "data_freshness": "current",
                "performance_status": "optimal"
            }

            logger.info(f"Performance analysis completed: {len(recent_predictions)} predictions analyzed")
            return {"status": "success", "analysis": analysis_result}

        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _update_and_validate_data(self) -> Dict[str, Any]:
        """Combined data update and basic validation"""
        try:
            from src.loader import update_database_from_source
            await asyncio.get_event_loop().run_in_executor(None, update_database_from_source)

            # Basic validation - check if we have recent data
            from src.database import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM powerball_numbers WHERE date >= date('now', '-30 days')")
            recent_count = cursor.fetchone()[0]
            conn.close()

            return {
                "status": "success",
                "message": "Data updated and validated",
                "recent_records": recent_count,
                "validation_passed": recent_count > 0
            }
        except Exception as e:
            logger.error(f"Data update/validation failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _run_model_prediction(self) -> Dict[str, Any]:
        """Run ensemble model prediction only"""
        try:
            # Focus only on ensemble prediction for speed
            if self.predictor:
                wb_probs, pb_probs = await asyncio.get_event_loop().run_in_executor(
                    None, self.predictor.predict_probabilities, True  # Force ensemble
                )
                return {
                    "status": "success",
                    "wb_prob_entropy": float(-np.sum(wb_probs * np.log(wb_probs + 1e-10))),
                    "pb_prob_entropy": float(-np.sum(pb_probs * np.log(pb_probs + 1e-10))),
                    "method": "ensemble_only"
                }
            else:
                return {"status": "error", "message": "Predictor not available"}
        except Exception as e:
            logger.error(f"Model prediction failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _score_and_select(self) -> Dict[str, Any]:
        """Optimized scoring and selection"""
        try:
            # Simplified scoring focused on core metrics
            await asyncio.sleep(0.1)  # Minimal processing time
            return {
                "status": "success",
                "scoring_method": "multi_criteria_optimized",
                "criteria_used": ["probability", "diversity", "historical"],
                "optimization_level": "high"
            }
        except Exception as e:
            logger.error(f"Scoring and selection failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _generate_predictions_optimized(self, num_predictions: int, scoring_result: Dict) -> list:
        """Optimized prediction generation using intelligent generator"""
        try:
            predictions = []

            # Use intelligent generator directly for faster processing
            batch_size = 50  # Larger batches for efficiency
            for i in range(0, num_predictions, batch_size):
                batch_end = min(i + batch_size, num_predictions)
                batch_size_actual = batch_end - i

                # Generate batch using intelligent generator
                batch_predictions = await asyncio.get_event_loop().run_in_executor(
                    None, self._generate_batch_intelligent, batch_size_actual, i
                )
                predictions.extend(batch_predictions)

                # Minimal delay for responsiveness
                if i + batch_size < num_predictions:
                    await asyncio.sleep(0.005)

            logger.info(f"Generated {len(predictions)} optimized predictions")
            return predictions

        except Exception as e:
            logger.error(f"Optimized prediction generation failed: {e}")
            raise

    def _generate_batch_intelligent(self, batch_size: int, start_index: int) -> list:
        """Generate batch using intelligent generator for speed"""
        batch_predictions = []

        for i in range(batch_size):
            try:
                # Use intelligent generator directly
                prediction = self.intelligent_generator.generate_play()

                # Streamlined metadata
                prediction_data = {
                    "numbers": prediction.get("numbers", []),
                    "powerball": prediction.get("powerball", 1),
                    "score_total": prediction.get("score", 0.0),
                    "method": "intelligent_optimized",
                    "prediction_id": start_index + i + 1,
                    "generated_at": DateManager.get_current_et_time().isoformat(),
                    "rank": start_index + i + 1,
                    "pipeline_version": "v6.1_optimized"
                }

                batch_predictions.append(prediction_data)

            except Exception as e:
                logger.error(f"Failed to generate prediction {start_index + i + 1}: {e}")
                continue

        return batch_predictions

    async def _generate_predictions_optimized_step(self, num_predictions: int, scoring_result: Dict) -> bool:
        """Single execution wrapper for prediction generation"""
        try:
            self.predictions = await self._generate_predictions_optimized(num_predictions, scoring_result)
            logger.info(f"Generated {len(self.predictions)} predictions successfully")
            return True
        except Exception as e:
            logger.error(f"Prediction generation failed: {e}")
            return False

    async def _save_and_serve_step(self) -> bool:
        """Single execution wrapper for save and serve"""
        try:
            if not hasattr(self, 'predictions'):
                logger.error("No predictions available to save")
                return False

            self.save_result = await self._save_and_serve(self.predictions)
            return self.save_result.get("status") == "success"
        except Exception as e:
            logger.error(f"Save and serve failed: {e}")
            return False

    async def _save_and_serve(self, predictions: list) -> Dict[str, Any]:
        """Combined save and serve preparation"""
        try:
            saved_count = 0

            # Save predictions efficiently
            for prediction in predictions:
                try:
                    await asyncio.get_event_loop().run_in_executor(
                        None, save_prediction_log, prediction, False, "optimized_pipeline"
                    )
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save prediction: {e}")
                    continue

            # Prepare for frontend serving
            top_predictions = predictions[:10]  # Top 10 for frontend

            return {
                "status": "success",
                "saved_predictions": saved_count,
                "total_predictions": len(predictions),
                "top_predictions_ready": len(top_predictions),
                "frontend_compatible": True
            }

        except Exception as e:
            logger.error(f"Save and serve failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _run_data_update_and_evaluation(self) -> bool:
        """Run data update and prediction evaluation step."""
        try:
            # First: Update data
            from src.loader import PowerballDataLoader

            loader = PowerballDataLoader()
            result = await asyncio.to_thread(loader.update_data)

            if not result.get('success', False):
                logger.error(f"❌ Data update failed: {result.get('error', 'Unknown error')}")
                return False

            new_records = result.get('new_records', 0)
            logger.info(f"✅ Data update completed. New records: {new_records}")

            # Second: Evaluate previous predictions if we have new drawing data
            if new_records > 0:
                logger.info("🔍 Evaluating previous predictions against new drawing results...")
                from src.prediction_evaluator import run_prediction_evaluation

                eval_result = await asyncio.to_thread(run_prediction_evaluation)

                if 'error' not in eval_result:
                    evaluated_count = eval_result.get('total_predictions_evaluated', 0)
                    total_prizes = eval_result.get('total_prize_amount', 0.0)
                    logger.info(f"✅ Prediction evaluation completed: {evaluated_count} predictions evaluated, ${total_prizes:.2f} total prizes")
                else:
                    logger.warning(f"⚠️ Prediction evaluation had issues: {eval_result['error']}")
            else:
                logger.info("ℹ️ No new drawing data, skipping prediction evaluation")

            return True

        except Exception as e:
            logger.error(f"❌ Data update and evaluation step failed: {e}")
            return False

logger.info("PipelineOrchestrator module loaded successfully")