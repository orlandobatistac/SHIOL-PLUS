import configparser
import os
from datetime import datetime
import hashlib
import numpy as np
import pandas as pd
import statsmodels.api as sm
from loguru import logger
from scipy.spatial.distance import euclidean
from typing import Dict, List, Tuple

class FeatureEngineer:
    def __init__(self, historical_data):
        self.data = historical_data.copy()
        self.row_count = len(self.data)
        logger.info(
            f"FeatureEngineer initialized with {self.row_count} rows of historical data."
        )
        self.expected_columns = ["draw_date", "n1", "n2", "n3", "n4", "n5", "pb"]
        self._validate_required_columns()
        self._load_temporal_config()

    def _load_temporal_config(self):
        """
        Loads temporal analysis configuration parameters from config.ini
        """
        try:
            config = configparser.ConfigParser()
            config.read(os.path.join("config", "config.ini"))
            self.time_decay_function = config.get(
                "temporal_analysis", "time_decay_function", fallback="exponential"
            )
            self.time_decay_rate = config.getfloat(
                "temporal_analysis", "time_decay_rate", fallback=0.05
            )
            self.min_weight_percent = (
                config.getfloat("temporal_analysis", "min_weight_percent", fallback=10)
                / 100
            )
            self.moving_window_size = config.getint(
                "temporal_analysis", "moving_window_size", fallback=20
            )
            self.num_windows = config.getint(
                "temporal_analysis", "num_windows", fallback=5
            )
            self.seasonality_period = config.getint(
                "temporal_analysis", "seasonality_period", fallback=30
            )
            self.seasonality_threshold = config.getfloat(
                "temporal_analysis", "seasonality_threshold", fallback=0.6
            )
            logger.info("Temporal analysis configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading temporal analysis configuration: {e}")
            self.time_decay_function = "exponential"
            self.time_decay_rate = 0.05
            self.min_weight_percent = 0.1
            self.moving_window_size = 20
            self.num_windows = 5
            self.seasonality_period = 30
            self.seasonality_threshold = 0.6
            logger.warning("Using default temporal analysis parameters")

    def _validate_required_columns(self):
        """
        Validates that the required columns exist in the dataset.
        """
        try:
            missing_columns = [
                col for col in self.expected_columns if col not in self.data.columns
            ]
            if missing_columns:
                logger.warning(f"Missing required columns: {missing_columns}")
                for col in missing_columns:
                    if col in ["n1", "n2", "n3", "n4", "n5", "pb"]:
                        self.data[col] = np.nan
                        logger.info(f"Added missing column '{col}' with NaN values")
            number_cols = [
                col
                for col in ["n1", "n2", "n3", "n4", "n5", "pb"]
                if col in self.data.columns
            ]
            for col in number_cols:
                if not pd.api.types.is_numeric_dtype(self.data[col]):
                    logger.warning(
                        f"Column '{col}' is not numeric. Attempting to convert."
                    )
                    try:
                        self.data[col] = pd.to_numeric(self.data[col], errors="coerce")
                    except Exception as e:
                        logger.error(
                            f"Failed to convert column '{col}' to numeric: {e}"
                        )
            logger.info("Column validation complete")
        except Exception as e:
            logger.error(f"Error during column validation: {e}")

    def _validate_date_column(self):
        """
        Centralized validation for the draw_date column.
        """
        try:
            if "draw_date" not in self.data.columns:
                date_column_alternatives = [
                    "date",
                    "draw date",
                    "drawdate",
                    "datetime",
                    "timestamp",
                ]
                found_column = None
                for alt_col in date_column_alternatives:
                    if alt_col in self.data.columns:
                        found_column = alt_col
                        logger.info(
                            f"Found alternative date column '{alt_col}'. "
                            f"Renaming to 'draw_date'."
                        )
                        self.data["draw_date"] = self.data[alt_col]
                        break
                if found_column is None:
                    logger.warning(
                        "'draw_date' column not found. Creating synthetic dates."
                    )
                    self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                        self.data.index, unit="D"
                    )
                    return False
            if not pd.api.types.is_datetime64_dtype(self.data["draw_date"]):
                logger.info("Converting draw_date column to datetime format.")
                try:
                    self.data["draw_date"] = pd.to_datetime(
                        self.data["draw_date"], errors="coerce"
                    )
                    nat_count = self.data["draw_date"].isna().sum()
                    if nat_count > 0:
                        logger.warning(
                            f"Found {nat_count} invalid date values that were "
                            f"converted to NaT."
                        )
                except Exception as e:
                    logger.error(f"Error converting draw_date to datetime: {e}")
                    self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                        self.data.index, unit="D"
                    )
                    return False
            today = pd.to_datetime("today")
            future_dates = self.data[self.data["draw_date"] > today]
            if len(future_dates) > 0:
                logger.warning(
                    f"Found {len(future_dates)} future dates. Setting to today's date."
                )
                self.data.loc[self.data["draw_date"] > today, "draw_date"] = today
            missing_dates = self.data["draw_date"].isna().sum()
            if missing_dates > 0:
                logger.warning(
                    f"Found {missing_dates} missing dates. "
                    f"Filling with synthetic dates."
                )
                missing_mask = self.data["draw_date"].isna()
                self.data.loc[missing_mask, "draw_date"] = pd.to_datetime(
                    "today"
                ) - pd.to_timedelta(self.data.index[missing_mask], unit="D")
            self.data.sort_values(by="draw_date", inplace=True)
            self.data.reset_index(drop=True, inplace=True)
            return True
        except Exception as e:
            logger.error(f"Error during date validation: {e}")
            self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                self.data.index, unit="D"
            )
            return False

    def engineer_features(self, use_temporal_analysis=True):
        self._standardize_column_names()
        try:
            initial_row_count = len(self.data)
            logger.info(
                f"Starting feature engineering with {initial_row_count} rows"
                f"{' with' if use_temporal_analysis else ' without'} temporal analysis"
                f"..."
            )
            self._validate_required_columns()
            white_ball_cols = ["n1", "n2", "n3", "n4", "n5"]
            missing_cols = [
                col for col in white_ball_cols if col not in self.data.columns
            ]
            if missing_cols:
                logger.warning(
                    f"Missing white ball columns: {missing_cols}. "
                    f"Some features may not be calculated correctly."
                )
            self._calculate_basic_features(white_ball_cols)
            if use_temporal_analysis:
                self._calculate_temporal_features()
            self._add_prize_tier()
            self.calculate_euclidean_distance_features()
            
            # Remove duplicate columns, keeping first occurrence
            if self.data.columns.duplicated().any():
                num_duplicates = self.data.columns.duplicated().sum()
                logger.info(f"Removing {num_duplicates} duplicate feature columns")
                self.data = self.data.loc[:, ~self.data.columns.duplicated(keep='first')]
                logger.info(f"Final feature count after deduplication: {len(self.data.columns)}")
            
            final_row_count = len(self.data)
            logger.info(
                f"Feature engineering complete with {final_row_count} rows"
                f"{' with' if use_temporal_analysis else ' without'} temporal features"
                "."
            )
            if final_row_count != initial_row_count:
                logger.warning(
                    f"Row count changed during feature engineering: "
                    f"{initial_row_count} -> {final_row_count}"
                )
            return self.data
        except Exception as e:
            logger.error(f"Error during feature engineering: {e}")
            logger.info("Returning partially processed data due to errors.")
            return self.data

    def _calculate_basic_features(self, white_ball_cols):
        self._calculate_parity_features(white_ball_cols)
        self._calculate_sum_features(white_ball_cols)
        self._calculate_spread_features(white_ball_cols)
        self._calculate_consecutive_features(white_ball_cols)
        self._calculate_low_high_balance(white_ball_cols)

    def _calculate_parity_features(self, white_ball_cols):
        try:
            even_mask = (self.data[white_ball_cols] % 2 == 0) & self.data[
                white_ball_cols
            ].notna()
            self.data["even_count"] = even_mask.sum(axis=1)
            valid_count = self.data[white_ball_cols].notna().sum(axis=1)
            self.data["odd_count"] = valid_count - self.data["even_count"]
        except Exception as e:
            logger.error(f"Error calculating parity features: {e}")
            self.data["even_count"] = np.nan
            self.data["odd_count"] = np.nan

    def _calculate_sum_features(self, white_ball_cols):
        try:
            self.data["sum"] = self.data[white_ball_cols].sum(axis=1)
        except Exception as e:
            logger.error(f"Error calculating sum features: {e}")
            self.data["sum"] = np.nan

    def _calculate_spread_features(self, white_ball_cols):
        try:
            self.data["spread"] = self.data[white_ball_cols].max(axis=1) - self.data[
                white_ball_cols
            ].min(axis=1)
        except Exception as e:
            logger.error(f"Error calculating spread features: {e}")
            self.data["spread"] = np.nan

    def _calculate_consecutive_features(self, white_ball_cols):
        try:
            def count_consecutive(row):
                valid_numbers = [x for x in row if pd.notna(x)]
                if not valid_numbers:
                    return 0
                numbers = sorted(valid_numbers)
                consecutive_count = 0
                for i in range(len(numbers) - 1):
                    if numbers[i + 1] - numbers[i] == 1:
                        consecutive_count += 1
                return consecutive_count
            self.data["consecutive_count"] = self.data[white_ball_cols].apply(
                count_consecutive, axis=1
            )
        except Exception as e:
            logger.error(f"Error calculating consecutive number features: {e}")
            self.data["consecutive_count"] = np.nan

    def _calculate_low_high_balance(self, white_ball_cols):
        try:
            def low_high_balance(row):
                valid_numbers = [x for x in row if pd.notna(x)]
                if not valid_numbers:
                    return "0L-0H"
                low_count = sum(1 for x in valid_numbers if x <= 35)
                high_count = len(valid_numbers) - low_count
                return f"{low_count}L-{high_count}H"
            self.data["low_high_balance"] = self.data[white_ball_cols].apply(
                low_high_balance, axis=1
            )
        except Exception as e:
            logger.error(f"Error calculating low/high balance features: {e}")
            self.data["low_high_balance"] = "0L-0H"

    def _calculate_temporal_features(self):
        date_valid = self._validate_date_column()
        if not date_valid:
            logger.warning(
                "Using synthetic dates for temporal analysis. "
                "Results may be less accurate."
            )
        self._calculate_recency()
        self._calculate_time_weights()
        self._detect_trends()
        self._detect_seasonal_patterns()

    def _standardize_column_names(self):
        try:
            column_patterns = {
                "date": "draw_date", "draw date": "draw_date", "drawdate": "draw_date",
                "datetime": "draw_date", "timestamp": "draw_date", "white_ball_1": "n1",
                "white_ball_2": "n2", "white_ball_3": "n3", "white_ball_4": "n4",
                "white_ball_5": "n5", "number 1": "n1", "number 2": "n2",
                "number 3": "n3", "number 4": "n4", "number 5": "n5",
                "ball1": "n1", "ball2": "n2", "ball3": "n3", "ball4": "n4",
                "ball5": "n5", "powerball": "pb", "power_ball": "pb",
                "power ball": "pb", "ball6": "pb",
            }
            rename_map = {}
            for col in self.data.columns:
                col_lower = col.lower()
                if col_lower in column_patterns:
                    rename_map[col] = column_patterns[col_lower]
            if rename_map:
                logger.info(f"Standardizing column names: {rename_map}")
                self.data.rename(columns=rename_map, inplace=True)
        except Exception as e:
            logger.error(f"Error during column name standardization: {e}")

    def _add_prize_tier(self):
        try:
            required_cols = ["sum", "even_count", "consecutive_count"]
            missing_cols = [
                col for col in required_cols if col not in self.data.columns
            ]
            if missing_cols:
                logger.warning(
                    f"Missing columns for prize tier classification: {missing_cols}. "
                    f"Using default tier."
                )
                self.data["prize_tier"] = "LowTier"
                return
            for col in required_cols:
                if self.data[col].isna().any():
                    if col == "sum": self.data[col].fillna(0, inplace=True)
                    elif col == "even_count": self.data[col].fillna(0, inplace=True)
                    elif col == "consecutive_count": self.data[col].fillna(0, inplace=True)
            conditions = [
                (self.data["sum"].between(120, 240))
                & (self.data["even_count"].isin([2, 3]))
                & (self.data["consecutive_count"] <= 1),
                (self.data["sum"].between(100, 260))
                & (self.data["even_count"].isin([1, 2, 3, 4])),
            ]
            choices = ["TopTier", "MidTier"]
            self.data["prize_tier"] = np.select(conditions, choices, default="LowTier")
        except Exception as e:
            logger.error(f"Error during prize tier classification: {e}")
            self.data["prize_tier"] = "LowTier"

    def _calculate_recency(self):
        try:
            if len(self.data) < 10: # Corresponds to min_draws_for_recency
                self.data["avg_delay"] = 0
                self.data["max_delay"] = 0
                self.data["min_delay"] = 0
                return
            self.data.sort_values(by="draw_date", inplace=True)
            self.data.reset_index(drop=True, inplace=True)
            last_seen = {}
            delays = []
            white_ball_cols = ["n1", "n2", "n3", "n4", "n5"]
            for index, row in self.data.iterrows():
                current_delays = []
                numbers_in_draw = []
                for col in white_ball_cols:
                    if col in row:
                        num = row.get(col)
                        if pd.notna(num):
                            numbers_in_draw.append(num)
                for num in numbers_in_draw:
                    delay = index - last_seen.get(num, index)
                    current_delays.append(delay)
                    last_seen[num] = index
                if not current_delays:
                    current_delays = [0] * 5
                while len(current_delays) < 5:
                    current_delays.append(0)
                if len(current_delays) > 5:
                    current_delays = current_delays[:5]
                delays.append(current_delays)
            delay_df = pd.DataFrame(delays, columns=[f"delay_n{i+1}" for i in range(5)])
            self.data["avg_delay"] = delay_df.mean(axis=1)
            self.data["max_delay"] = delay_df.max(axis=1)
            self.data["min_delay"] = delay_df.min(axis=1)
        except Exception as e:
            logger.error(f"Error calculating recency features: {e}")
            self.data["avg_delay"] = np.nan
            self.data["max_delay"] = np.nan
            self.data["min_delay"] = np.nan

    def calculate_euclidean_distance_features(self, top_n=5):
        white_ball_cols = ["n1", "n2", "n3", "n4", "n5"]
        if "draw_date" not in self.data.columns or len(self.data) == 0:
            self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                self.data.index, unit="D"
            )
        if len(self.data) < 5: # Corresponds to min_draws_for_distance
            self.data["dist_to_recent"] = 0.5
            self.data["avg_dist_to_top_n"] = 0.5
            self.data["dist_to_centroid"] = 0.5
            return
        self.data.sort_values(by="draw_date", inplace=True)
        self.data.reset_index(drop=True, inplace=True)
        self._calculate_distance_to_recent(white_ball_cols)
        self._calculate_distance_to_top_n(white_ball_cols, top_n)
        self._calculate_distance_to_centroid(white_ball_cols)
        self._normalize_distance_features()

    def _calculate_distance_to_recent(self, white_ball_cols):
        if len(self.data) == 0:
            self.data["dist_to_recent"] = np.nan
            return
        most_recent = self.data[white_ball_cols].iloc[-1].values
        self.data["dist_to_recent"] = self.data[white_ball_cols].apply(
            lambda row: self._safe_euclidean(row.values, most_recent), axis=1
        )

    def _calculate_distance_to_top_n(self, white_ball_cols, top_n):
        if len(self.data) <= top_n:
            self.data["avg_dist_to_top_n"] = np.nan
            return
        top_combinations = self.data[white_ball_cols].iloc[-top_n - 1 : -1].values
        top_combinations_float = []
        for combo in top_combinations:
            try:
                combo_array = np.array(combo, dtype=float)
                if not np.isnan(combo_array).any() and not np.isinf(combo_array).any():
                    top_combinations_float.append(combo_array)
            except Exception:
                continue
        distances = []
        for _, row in self.data.iterrows():
            current = row[white_ball_cols].values
            try:
                current = np.array(current, dtype=float)
                if np.isnan(current).any() or np.isinf(current).any():
                    distances.append(np.nan)
                    continue
                valid_distances = [
                    euclidean(current, combo) for combo in top_combinations_float
                ]
                if valid_distances:
                    avg_dist = np.mean(valid_distances)
                    distances.append(avg_dist)
                else:
                    distances.append(np.nan)
            except Exception:
                distances.append(np.nan)
        self.data["avg_dist_to_top_n"] = distances

    def _calculate_distance_to_centroid(self, white_ball_cols):
        if len(self.data) <= 1:
            self.data["dist_to_centroid"] = np.nan
            return
        centroid = self.data[white_ball_cols].mean().values
        self.data["dist_to_centroid"] = self.data[white_ball_cols].apply(
            lambda row: self._safe_euclidean(row.values, centroid), axis=1
        )

    def _normalize_distance_features(self):
        for col in ["dist_to_recent", "avg_dist_to_top_n", "dist_to_centroid"]:
            if col in self.data.columns and not self.data[col].isna().all():
                max_val = self.data[col].max()
                if max_val > 0:
                    self.data[f"{col}_norm"] = self.data[col] / max_val

    def _safe_euclidean(self, row_values, reference_values):
        try:
            row_values = np.array(row_values, dtype=float)
            reference_values = np.array(reference_values, dtype=float)
            if (
                np.isnan(row_values).any()
                or np.isinf(row_values).any()
                or np.isnan(reference_values).any()
                or np.isinf(reference_values).any()
            ):
                return np.nan
            return euclidean(row_values, reference_values)
        except Exception as e:
            logger.warning(f"Error calculating Euclidean distance: {e}")
            return np.nan

    def _calculate_time_weights(self):
        if "draw_date" not in self.data.columns or len(self.data) == 0:
            self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                self.data.index, unit="D"
            )
        if len(self.data) < 30: # Corresponds to min_draws_for_analysis
            return
        self.data.sort_values(by="draw_date", inplace=True)
        self.data.reset_index(drop=True, inplace=True)
        if not pd.api.types.is_datetime64_dtype(self.data["draw_date"]):
            self.data["draw_date"] = pd.to_datetime(self.data["draw_date"])
        first_draw_date = self.data["draw_date"].min()
        self.data["days_since_first"] = (
            self.data["draw_date"] - first_draw_date
        ).dt.days
        max_days = self.data["days_since_first"].max()
        if max_days == 0:
            self.data["time_weight"] = 1.0
            return
        if self.time_decay_function == "linear":
            self.data["time_weight"] = 1 - (
                self.data["days_since_first"] / max_days
            ) * (1 - self.min_weight_percent)
        elif self.time_decay_function == "exponential":
            self.data["time_weight"] = (
                np.exp(-self.time_decay_rate * self.data["days_since_first"])
                * (1 - self.min_weight_percent)
                + self.min_weight_percent
            )
        elif self.time_decay_function == "inverse_square":
            self.data["time_weight"] = (
                1 / (1 + (self.data["days_since_first"] * self.time_decay_rate) ** 2)
            ) * (1 - self.min_weight_percent) + self.min_weight_percent
        else:
            self.data["time_weight"] = (
                np.exp(-self.time_decay_rate * self.data["days_since_first"])
                * (1 - self.min_weight_percent)
                + self.min_weight_percent
            )
        weight_sum = self.data["time_weight"].sum()
        if weight_sum > 0:
            self.data["time_weight_norm"] = self.data["time_weight"] / weight_sum
        else:
            self.data["time_weight_norm"] = 1.0 / len(self.data)

    def _detect_trends(self):
        if "draw_date" not in self.data.columns:
            self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                self.data.index, unit="D"
            )
        if len(self.data) < 20: # Corresponds to min_draws_for_trends
            return
        if len(self.data) < self.moving_window_size:
            return
        self.data.sort_values(by="draw_date", inplace=True)
        self.data.reset_index(drop=True, inplace=True)
        number_trends = {i: [] for i in range(1, 70)}
        pb_trends = {i: [] for i in range(1, 27)}
        window_count = min(self.num_windows, len(self.data) // self.moving_window_size)
        if window_count < 2:
            return
        for w in range(window_count):
            end_idx = len(self.data) - w * self.moving_window_size
            start_idx = max(0, end_idx - self.moving_window_size)
            window_data = self.data.iloc[start_idx:end_idx]
            white_counts = {i: 0 for i in range(1, 70)}
            pb_counts = {i: 0 for i in range(1, 27)}
            for _, row in window_data.iterrows():
                for col in ["n1", "n2", "n3", "n4", "n5"]:
                    num = row[col]
                    if 1 <= num <= 69:
                        white_counts[num] += 1
                pb = row.get("pb")
                if pd.notna(pb) and 1 <= pb <= 26:
                    pb_counts[pb] += 1
            for num, count in white_counts.items():
                number_trends[num].append(count / len(window_data))
            for num, count in pb_counts.items():
                pb_trends[num].append(count / len(window_data))
        white_ball_trends = {}
        pb_ball_trends = {}
        for num, freqs in number_trends.items():
            if len(freqs) >= 2:
                x = np.arange(len(freqs))
                poly_coeffs = np.polyfit(x, freqs, 1)
                slope = poly_coeffs[0]
                if slope > 0.005: white_ball_trends[num] = "increasing"
                elif slope < -0.005: white_ball_trends[num] = "decreasing"
                else: white_ball_trends[num] = "stable"
        for num, freqs in pb_trends.items():
            if len(freqs) >= 2:
                x = np.arange(len(freqs))
                poly_coeffs = np.polyfit(x, freqs, 1)
                slope = poly_coeffs[0]
                if slope > 0.005: pb_ball_trends[num] = "increasing"
                elif slope < -0.005: pb_ball_trends[num] = "decreasing"
                else: pb_ball_trends[num] = "stable"
        def get_trends_for_draw(row):
            trends = []
            for col in ["n1", "n2", "n3", "n4", "n5"]:
                num = row[col]
                if num in white_ball_trends:
                    trends.append(white_ball_trends[num])
            pb = row.get("pb")
            if pd.notna(pb) and pb in pb_ball_trends:
                trends.append(pb_ball_trends[pb])
            increasing = trends.count("increasing")
            decreasing = trends.count("decreasing")
            stable = trends.count("stable")
            return pd.Series(
                {
                    "increasing_trend_count": increasing,
                    "decreasing_trend_count": decreasing,
                    "stable_trend_count": stable,
                    "dominant_trend": max(
                        ["increasing", "decreasing", "stable"],
                        key=lambda x: [increasing, decreasing, stable][
                            ["increasing", "decreasing", "stable"].index(x)
                        ],
                    ),
                }
            )
        trend_features = self.data.apply(get_trends_for_draw, axis=1)
        self.data = pd.concat([self.data, trend_features], axis=1)

    def _detect_seasonal_patterns(self):
        if "draw_date" not in self.data.columns:
            self.data["draw_date"] = pd.to_datetime("today") - pd.to_timedelta(
                self.data.index, unit="D"
            )
        if len(self.data) < 60: # Corresponds to min_draws_for_seasonality
            return
        if len(self.data) < 2 * self.seasonality_period:
            return
        self.data.sort_values(by="draw_date", inplace=True)
        self.data.reset_index(drop=True, inplace=True)
        if not pd.api.types.is_datetime64_dtype(self.data["draw_date"]):
            self.data["draw_date"] = pd.to_datetime(self.data["draw_date"])
        self.data["day_of_week"] = self.data["draw_date"].dt.dayofweek
        self.data["day_of_month"] = self.data["draw_date"].dt.day
        self.data["month"] = self.data["draw_date"].dt.month
        self.data["quarter"] = self.data["draw_date"].dt.quarter
        seasonal_numbers = set()
        for num in range(1, 70):
            time_series = pd.Series(0, index=self.data.index)
            for col in ["n1", "n2", "n3", "n4", "n5"]:
                time_series = time_series | (self.data[col] == num)
            time_series = time_series.astype(int)
            if time_series.sum() == 0:
                continue
            try:
                acf = sm.tsa.acf(
                    time_series, nlags=self.seasonality_period * 2, fft=True
                )
                if (
                    len(acf) > self.seasonality_period
                    and abs(acf[self.seasonality_period]) > self.seasonality_threshold
                ):
                    seasonal_numbers.add(num)
            except Exception as e:
                logger.warning(
                    f"Error calculating autocorrelation for number {num}: {e}"
                )
        seasonal_pb_numbers = set()
        for num in range(1, 27):
            time_series = (self.data["pb"] == num).astype(int)
            if time_series.sum() == 0:
                continue
            try:
                acf = sm.tsa.acf(
                    time_series, nlags=self.seasonality_period * 2, fft=True
                )
                if (
                    len(acf) > self.seasonality_period
                    and abs(acf[self.seasonality_period]) > self.seasonality_threshold
                ):
                    seasonal_pb_numbers.add(num)
            except Exception as e:
                logger.warning(
                    f"Error calculating autocorrelation for Powerball {num}: {e}"
                )
        def count_seasonal_numbers(row):
            count = sum(
                1
                for col in ["n1", "n2", "n3", "n4", "n5"]
                if row[col] in seasonal_numbers
            )
            pb_seasonal = 1 if row.get("pb") in seasonal_pb_numbers else 0
            return pd.Series(
                {
                    "seasonal_number_count": count,
                    "pb_seasonal": pb_seasonal,
                    "has_seasonality": count > 0 or pb_seasonal > 0,
                }
            )
        seasonality_features = self.data.apply(count_seasonal_numbers, axis=1)
        self.data = pd.concat([self.data, seasonality_features], axis=1)
        day_counts = self.data.groupby("day_of_week").size()
        month_counts = self.data.groupby("month").size()
        day_freq = day_counts / day_counts.sum()
        month_freq = month_counts / month_counts.sum()
        high_freq_days = day_freq[day_freq > 1.0 / 7 + 0.05].index.tolist()
        high_freq_months = month_freq[month_freq > 1.0 / 12 + 0.05].index.tolist()
        self.data["high_freq_day"] = self.data["day_of_week"].isin(high_freq_days)
        self.data["high_freq_month"] = self.data["month"].isin(high_freq_months)

class IntelligentGenerator:
    """
    Generates lottery plays based on predicted probabilities from the model.
    """
    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data

    def generate_plays(self, n_samples: int) -> List[List[int]]:
        """
        Genera combinaciones utilizando probabilidades mejoradas y métricas avanzadas.

        Args:
            n_samples (int): El número de combinaciones a generar.

        Returns:
            List[List[int]]: A list of generated combinations.
        """
        logger.info("Generating combinations with IntelligentGenerator...")
        # Implement improved logic here
        return [[1, 2, 3, 4, 5, 6] for _ in range(n_samples)]  # Example

    def generate_smart_play(self) -> Dict:
        """
        Generates a single intelligent combination with scoring.

        Returns:
            Dict: Dictionary with numbers, powerball and score
        """
        try:
            # Use DeterministicGenerator to generate a quality prediction
            from datetime import datetime
            import numpy as np

            # Generate numbers based on simple historical analysis
            if not self.historical_data.empty:
                # Basic frequency analysis
                white_ball_cols = ["n1", "n2", "n3", "n4", "n5"]
                pb_col = "pb"

                # Calculate white ball number frequencies
                wb_frequencies = {}
                for col in white_ball_cols:
                    if col in self.historical_data.columns:
                        for num in range(1, 70):
                            wb_frequencies[num] = wb_frequencies.get(num, 0) + (self.historical_data[col] == num).sum()

                # Calculate powerball frequencies
                pb_frequencies = {}
                if pb_col in self.historical_data.columns:
                    for num in range(1, 27):
                        pb_frequencies[num] = (self.historical_data[pb_col] == num).sum()

                # Select numbers with balance of frequency and diversity
                # Use numbers with medium-high frequency but not the most common
                sorted_wb = sorted(wb_frequencies.items(), key=lambda x: x[1], reverse=True)
                sorted_pb = sorted(pb_frequencies.items(), key=lambda x: x[1], reverse=True)

                # Take numbers from medium-high range (avoid extremes)
                top_count = min(25, len(sorted_wb))
                candidate_wb = [num for num, _ in sorted_wb[5:top_count]]  # Skip top 5, take next 20

                # If there aren't enough candidates, use full range
                if len(candidate_wb) < 5:
                    candidate_wb = list(range(1, 70))

                # Select 5 unique numbers
                np.random.seed(42)  # For reproducibility
                selected_wb = sorted(np.random.choice(candidate_wb, size=5, replace=False))

                # Select powerball from medium range
                pb_count = min(15, len(sorted_pb))
                candidate_pb = [num for num, _ in sorted_pb[2:pb_count]]  # Skip top 2, take next 13
                if not candidate_pb:
                    candidate_pb = list(range(1, 27))

                selected_pb = np.random.choice(candidate_pb)

                # Calculate basic score
                score = self._calculate_basic_score(selected_wb, selected_pb)

                return {
                    'numbers': selected_wb,
                    'powerball': int(selected_pb),
                    'score': score,
                    'method': 'intelligent_generator',
                    'timestamp': datetime.now().isoformat()
                }

            else:
                # Fallback if there's no historical data
                np.random.seed(42)
                numbers = sorted(np.random.choice(range(1, 70), size=5, replace=False))
                powerball = np.random.choice(range(1, 27))

                return {
                    'numbers': numbers.tolist(),
                    'powerball': int(powerball),
                    'score': 0.5,  # Score neutral
                    'method': 'intelligent_generator_fallback',
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            logger.error(f"Error generating smart play: {e}")
            # Fallback simple
            return {
                'numbers': [1, 15, 25, 35, 45],
                'powerball': 10,
                'score': 0.3,
                'method': 'intelligent_generator_error_fallback',
                'timestamp': datetime.now().isoformat()
            }

    def _calculate_basic_score(self, white_balls: List[int], powerball: int) -> float:
        """
        Calcula un score básico para la combinación.
        """
        try:
            score = 0.0

            # Score por balance par/impar
            even_count = sum(1 for num in white_balls if num % 2 == 0)
            if even_count in [2, 3]:
                score += 0.25
            else:
                score += 0.1

            # Score por spread (diferencia entre max y min)
            spread = max(white_balls) - min(white_balls)
            if 30 <= spread <= 50:
                score += 0.25
            else:
                score += 0.1

            # Score by total sum
            total_sum = sum(white_balls)
            if 120 <= total_sum <= 240:
                score += 0.25
            else:
                score += 0.1

            # Score by distribution in ranges
            range1 = sum(1 for num in white_balls if 1 <= num <= 23)
            range2 = sum(1 for num in white_balls if 24 <= num <= 46)
            range3 = sum(1 for num in white_balls if 47 <= num <= 69)

            # Penalize excessive concentration in one range
            max_in_range = max(range1, range2, range3)
            if max_in_range <= 3:
                score += 0.25
            else:
                score += 0.1

            return min(1.0, score)  # Limit to 1.0

        except Exception as e:
            logger.warning(f"Error calculating basic score: {e}")
            return 0.4


class PlayScorer:
    """
    Multi-criteria scoring system to evaluate number combinations.
    Implements 4 scoring components with specific weights.
    """

    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data.copy()
        self.white_ball_cols = ["n1", "n2", "n3", "n4", "n5"]
        self.pb_col = "pb"

        # Weights for each scoring component
        self.weights = {
            'probability': 0.40,
            'diversity': 0.25,
            'historical': 0.20,
            'risk_adjusted': 0.15
        }

        logger.info("PlayScorer initialized with multi-criteria scoring system")

    def calculate_total_score(self, white_balls: List[int], powerball: int,
                            wb_probs, pb_probs) -> Dict:
        """
        Calculates the total score for a number combination.

        Args:
            white_balls: List of 5 white numbers
            powerball: Powerball number
            wb_probs: White ball probabilities
            pb_probs: Powerball probabilities

        Returns:
            Dict with individual and total scores
        """
        scores = {}

        # Calcular cada componente de scoring
        scores['probability'] = self._calculate_probability_score(white_balls, powerball, wb_probs, pb_probs)
        scores['diversity'] = self._calculate_diversity_score(white_balls, powerball)
        scores['historical'] = self._calculate_historical_score(white_balls, powerball)
        scores['risk_adjusted'] = self._calculate_risk_adjusted_score(white_balls, powerball)

        # Calcular score total ponderado
        total_score = sum(scores[component] * self.weights[component]
                         for component in scores.keys())

        scores['total'] = total_score

        return scores

    def _calculate_probability_score(self, white_balls: List[int], powerball: int,
                                   wb_probs, pb_probs) -> float:
        """
        Score basado en las probabilidades predichas por el modelo (40%).
        """
        try:
            # Manejar tanto arrays numpy como diccionarios
            if isinstance(wb_probs, np.ndarray):
                wb_dict = {i+1: prob for i, prob in enumerate(wb_probs[:69])}
            else:
                wb_dict = wb_probs

            if isinstance(pb_probs, np.ndarray):
                pb_dict = {i+1: prob for i, prob in enumerate(pb_probs[:26])}
            else:
                pb_dict = pb_probs

            # White ball score (average of probabilities)
            wb_score = np.mean([wb_dict.get(num, 0.0) for num in white_balls])

            # Powerball score
            pb_score = pb_dict.get(powerball, 0.0)

            # Combine scores (80% white balls, 20% powerball)
            probability_score = 0.8 * wb_score + 0.2 * pb_score

            return probability_score

        except Exception as e:
            logger.warning(f"Error calculating probability score: {e}")
            return 0.0

    def _calculate_diversity_score(self, white_balls: List[int], powerball: int) -> float:
        """
        Score based on combination diversity (25%).
        Evaluates even/odd distribution, ranges, spread, etc.
        """
        try:
            scores = []

            # 1. Even/odd balance (ideal: 2-3 or 3-2)
            even_count = sum(1 for num in white_balls if num % 2 == 0)
            parity_score = 1.0 if even_count in [2, 3] else 0.5
            scores.append(parity_score)

            # 2. Distribution by ranges (1-23, 24-46, 47-69)
            range1 = sum(1 for num in white_balls if 1 <= num <= 23)
            range2 = sum(1 for num in white_balls if 24 <= num <= 46)
            range3 = sum(1 for num in white_balls if 47 <= num <= 69)

            # Penalize excessive concentration in one range
            max_in_range = max(range1, range2, range3)
            range_score = 1.0 if max_in_range <= 3 else 0.5
            scores.append(range_score)

            # 3. Spread (difference between max and min)
            spread = max(white_balls) - min(white_balls)
            spread_score = min(1.0, spread / 50.0)  # Normalize to [0,1]
            scores.append(spread_score)

            # 4. Consecutive numbers (penalize many consecutive)
            consecutive_count = 0
            sorted_balls = sorted(white_balls)
            for i in range(len(sorted_balls) - 1):
                if sorted_balls[i + 1] - sorted_balls[i] == 1:
                    consecutive_count += 1

            consecutive_score = 1.0 if consecutive_count <= 1 else 0.5
            scores.append(consecutive_score)

            return np.mean(scores)

        except Exception as e:
            logger.warning(f"Error calculating diversity score: {e}")
            return 0.5

    def _calculate_historical_score(self, white_balls: List[int], powerball: int) -> float:
        """
        Score basado en patrones históricos (20%).
        Evalúa frecuencia histórica y recencia de aparición.
        """
        try:
            if self.historical_data.empty:
                return 0.5

            scores = []

            # 1. Historical frequency of white balls
            wb_frequencies = {}
            for col in self.white_ball_cols:
                if col in self.historical_data.columns:
                    freq_counts = self.historical_data[col].value_counts()
                    for num in range(1, 70):
                        wb_frequencies[num] = freq_counts.get(num, 0)

            total_draws = len(self.historical_data)
            if total_draws > 0:
                wb_freq_scores = []
                for num in white_balls:
                    freq = wb_frequencies.get(num, 0)
                    # Normalize frequency (numbers with medium frequency get better score)
                    expected_freq = total_draws * 5 / 69  # Expected frequency
                    freq_score = 1.0 - abs(freq - expected_freq) / expected_freq
                    wb_freq_scores.append(max(0.0, freq_score))

                scores.append(np.mean(wb_freq_scores))

            # 2. Historical frequency of powerball
            if self.pb_col in self.historical_data.columns and total_draws > 0:
                pb_freq = self.historical_data[self.pb_col].value_counts().get(powerball, 0)
                expected_pb_freq = total_draws / 26
                pb_freq_score = 1.0 - abs(pb_freq - expected_pb_freq) / expected_pb_freq
                scores.append(max(0.0, pb_freq_score))

            # 3. Recency (penalize numbers that appeared very recently)
            recent_draws = self.historical_data.tail(10)  # Last 10 draws
            recent_numbers = set()
            for col in self.white_ball_cols:
                if col in recent_draws.columns:
                    recent_numbers.update(recent_draws[col].dropna().tolist())

            recent_pb = set(recent_draws[self.pb_col].dropna().tolist()) if self.pb_col in recent_draws.columns else set()

            # Recency score (better if they haven't appeared recently)
            wb_recent_score = np.mean([0.3 if num in recent_numbers else 1.0 for num in white_balls])
            pb_recent_score = 0.3 if powerball in recent_pb else 1.0

            scores.extend([wb_recent_score, pb_recent_score])

            return np.mean(scores) if scores else 0.5

        except Exception as e:
            logger.warning(f"Error calculating historical score: {e}")
            return 0.5

    def _calculate_risk_adjusted_score(self, white_balls: List[int], powerball: int) -> float:
        """
        Risk-adjusted score (15%).
        Evaluates patterns that might be too obvious or popular.
        """
        try:
            scores = []

            # 1. Avoid obvious patterns (sequences, multiples)
            sorted_balls = sorted(white_balls)

            # Penalize long sequences
            is_sequence = all(sorted_balls[i+1] - sorted_balls[i] == 1
                            for i in range(len(sorted_balls)-1))
            sequence_score = 0.1 if is_sequence else 1.0
            scores.append(sequence_score)

            # Penalize multiples of the same number
            multiples_score = 1.0
            for base in range(2, 11):
                multiples = [num for num in white_balls if num % base == 0]
                if len(multiples) >= 4:  # 4 or more multiples of the same number
                    multiples_score = 0.3
                    break
            scores.append(multiples_score)

            # 2. Total sum (avoid extreme sums)
            total_sum = sum(white_balls)
            # Ideal range approximately: 120-240
            if 120 <= total_sum <= 240:
                sum_score = 1.0
            elif 100 <= total_sum <= 260:
                sum_score = 0.7
            else:
                sum_score = 0.3
            scores.append(sum_score)

            # 3. Avoid "popular" numbers (common endings)
            popular_endings = [1, 7, 11, 13, 21, 23]
            popular_count = sum(1 for num in white_balls if num in popular_endings)
            popular_score = 1.0 if popular_count <= 2 else 0.5
            scores.append(popular_score)

            return np.mean(scores)

        except Exception as e:
            logger.warning(f"Error calculating risk adjusted score: {e}")
            return 0.5


class DeterministicGenerator:
    """
    Deterministic prediction generator based on multi-criteria scoring.
    Always produces the same prediction for the same historical dataset.
    """

    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data.copy()
        self.scorer = PlayScorer(historical_data)
        self.model_version = "1.0.0"

        # Configure fixed seed for determinism
        np.random.seed(42)

        logger.info("DeterministicGenerator initialized with deterministic scoring system")

    def generate_top_prediction(self, wb_probs, pb_probs,
                              num_candidates: int = 1000) -> Dict:
        """
        Generates the top prediction based on deterministic scoring.

        Args:
            wb_probs: White ball number probabilities from the model
            pb_probs: Powerball probabilities from the model
            num_candidates: Number of candidate combinations to evaluate

        Returns:
            Dict with the top prediction and its details
        """
        logger.info(f"Generating deterministic top prediction from {num_candidates} candidates...")

        # Generate candidate combinations deterministically
        candidates = self._generate_candidate_combinations(wb_probs, pb_probs, num_candidates)

        # Handle both numpy arrays and dictionaries for scoring
        if isinstance(wb_probs, np.ndarray):
            wb_dict = {i+1: prob for i, prob in enumerate(wb_probs[:69])}
        else:
            wb_dict = wb_probs

        if isinstance(pb_probs, np.ndarray):
            pb_dict = {i+1: prob for i, prob in enumerate(pb_probs[:26])}
        else:
            pb_dict = pb_dict

        # Evaluate each combination with the scoring system
        scored_candidates = []
        for white_balls, powerball in candidates:
            scores = self.scorer.calculate_total_score(white_balls, powerball, wb_dict, pb_dict)

            scored_candidates.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'scores': scores,
                'total_score': scores['total']
            })

        # Sort by total score (descending) and take the top
        scored_candidates.sort(key=lambda x: x['total_score'], reverse=True)
        top_prediction = scored_candidates[0]

        # Prepare result with metadata
        result = {
            'numbers': top_prediction['white_balls'],
            'powerball': top_prediction['powerball'],
            'score_total': top_prediction['total_score'],
            'score_details': top_prediction['scores'],
            'model_version': self.model_version,
            'dataset_hash': self._calculate_dataset_hash(),
            'timestamp': datetime.now().isoformat(),
            'num_candidates_evaluated': len(candidates)
        }

        logger.info(f"Top prediction generated with total score: {result['score_total']:.4f}")
        return result

    def generate_diverse_predictions(self, wb_probs, pb_probs,
                                   num_plays: int = 5, num_candidates: int = 2000) -> List[Dict]:
        """
        Genera múltiples predicciones diversas de alta calidad.

        Args:
            wb_probs: Probabilidades de números blancos del modelo
            pb_probs: Probabilidades de powerball del modelo
            num_plays: Número de plays diversos a generar (default: 5)
            num_candidates: Número de combinaciones candidatas a evaluar

        Returns:
            List of Dict with the diverse predictions and their details
        """
        logger.info(f"Generating {num_plays} diverse high-quality predictions from {num_candidates} candidates...")

        # Generate more candidates for greater diversity
        candidates = self._generate_candidate_combinations(wb_probs, pb_probs, num_candidates)

        # Handle both numpy arrays and dictionaries for scoring
        if isinstance(wb_probs, np.ndarray):
            wb_dict = {i+1: prob for i, prob in enumerate(wb_probs[:69])}
        else:
            wb_dict = wb_probs

        if isinstance(pb_probs, np.ndarray):
            pb_dict = {i+1: prob for i, prob in enumerate(pb_probs[:26])}
        else:
            pb_dict = pb_probs

        # Evaluate each combination with the scoring system
        scored_candidates = []
        for white_balls, powerball in candidates:
            scores = self.scorer.calculate_total_score(white_balls, powerball, wb_dict, pb_dict)

            scored_candidates.append({
                'white_balls': white_balls,
                'powerball': powerball,
                'scores': scores,
                'total_score': scores['total']
            })

        # Sort by total score (descending)
        scored_candidates.sort(key=lambda x: x['total_score'], reverse=True)

        # Select diverse plays using diversity algorithm
        diverse_plays = self._select_diverse_plays(scored_candidates, num_plays)

        # Prepare results with metadata
        results = []
        dataset_hash = self._calculate_dataset_hash()
        timestamp = datetime.now().isoformat()

        for i, play in enumerate(diverse_plays):
            result = {
                'numbers': play['white_balls'],
                'powerball': play['powerball'],
                'score_total': play['total_score'],
                'score_details': play['scores'],
                'model_version': self.model_version,
                'dataset_hash': dataset_hash,
                'timestamp': timestamp,
                'num_candidates_evaluated': len(candidates),
                'play_rank': i + 1,
                'diversity_method': 'intelligent_selection'
            }
            results.append(result)

        logger.info(f"Generated {len(results)} diverse predictions with scores ranging from "
                   f"{results[0]['score_total']:.4f} to {results[-1]['score_total']:.4f}")
        return results

    def _select_diverse_plays(self, scored_candidates: List[Dict], num_plays: int) -> List[Dict]:
        """
        Selects diverse high-quality plays using an intelligent diversity algorithm.

        Args:
            scored_candidates: List of evaluated candidates sorted by score
            num_plays: Number of diverse plays to select

        Returns:
            List of selected diverse plays
        """
        if len(scored_candidates) < num_plays:
            logger.warning(f"Not enough candidates ({len(scored_candidates)}) for {num_plays} diverse plays")
            return scored_candidates

        selected_plays = []
        remaining_candidates = scored_candidates.copy()

        # 1. Select the best candidate as base
        best_play = remaining_candidates.pop(0)
        selected_plays.append(best_play)
        logger.info(f"Selected play 1 with score {best_play['total_score']:.4f}: {best_play['white_balls']} + {best_play['powerball']}")

        # 2. For the remaining plays, use diversity + quality criteria
        for play_num in range(2, num_plays + 1):
            best_candidate = None
            best_diversity_score = -1
            best_candidate_idx = -1

            # Evaluate each remaining candidate by diversity relative to already selected ones
            for idx, candidate in enumerate(remaining_candidates):
                # Calculate diversity score relative to already selected plays
                diversity_score = self._calculate_diversity_from_selected(candidate, selected_plays)

                # Combine diversity with quality (70% quality, 30% diversity)
                combined_score = 0.7 * candidate['total_score'] + 0.3 * diversity_score

                if combined_score > best_diversity_score:
                    best_diversity_score = combined_score
                    best_candidate = candidate
                    best_candidate_idx = idx

            if best_candidate:
                selected_plays.append(best_candidate)
                remaining_candidates.pop(best_candidate_idx)
                logger.info(f"Selected play {play_num} with score {best_candidate['total_score']:.4f} "
                           f"(diversity: {best_diversity_score:.4f}): {best_candidate['white_balls']} + {best_candidate['powerball']}")
            else:
                logger.warning(f"Could not find suitable candidate for play {play_num}/{num_plays}. "
                              f"Remaining candidates: {len(remaining_candidates)}, "
                              f"Best diversity score found: {best_diversity_score:.4f}")

        logger.info(f"Selection complete: {len(selected_plays)}/{num_plays} plays selected")
        return selected_plays

    def _calculate_diversity_from_selected(self, candidate: Dict, selected_plays: List[Dict]) -> float:
        """
        Calculates how diverse a candidate is relative to already selected plays.

        Args:
            candidate: Candidate to evaluate
            selected_plays: Already selected plays

        Returns:
            Diversity score (0-1, higher is more diverse)
        """
        if not selected_plays:
            return 1.0

        diversity_scores = []
        candidate_numbers = set(candidate['white_balls'] + [candidate['powerball']])

        for selected_play in selected_plays:
            selected_numbers = set(selected_play['white_balls'] + [selected_play['powerball']])

            # Calculate diversity based on unique numbers
            intersection = len(candidate_numbers.intersection(selected_numbers))
            union = len(candidate_numbers.union(selected_numbers))

            # Jaccard distance (1 - Jaccard similarity)
            jaccard_diversity = 1.0 - (intersection / union if union > 0 else 0)

            # Additional diversity based on numerical differences
            wb_diff = self._calculate_numerical_diversity(candidate['white_balls'], selected_play['white_balls'])
            pb_diff = abs(candidate['powerball'] - selected_play['powerball']) / 26.0

            # Combine diversity metrics
            combined_diversity = 0.6 * jaccard_diversity + 0.3 * wb_diff + 0.1 * pb_diff
            diversity_scores.append(combined_diversity)

        # Return the minimum diversity (more conservative)
        return min(diversity_scores)

    def _calculate_numerical_diversity(self, numbers1: List[int], numbers2: List[int]) -> float:
        """
        Calculates numerical diversity between two sets of white balls.

        Args:
            numbers1: First list of numbers
            numbers2: Second list of numbers

        Returns:
            Numerical diversity score (0-1)
        """
        # Calculate differences in numerical characteristics
        sum1, sum2 = sum(numbers1), sum(numbers2)
        spread1 = max(numbers1) - min(numbers1)
        spread2 = max(numbers2) - min(numbers2)

        # Diversity based on sum
        sum_diversity = min(1.0, abs(sum1 - sum2) / 100.0)

        # Diversity based on spread
        spread_diversity = min(1.0, abs(spread1 - spread2) / 30.0)

        # Diversity based on ranges
        range1_count = sum(1 for n in numbers1 if 1 <= n <= 23)
        range2_count = sum(1 for n in numbers2 if 1 <= n <= 23)
        range_diversity = abs(range1_count - range2_count) / 5.0

        return (sum_diversity + spread_diversity + range_diversity) / 3.0

    def _generate_candidate_combinations(self, wb_probs, pb_probs,
                                       num_candidates: int) -> List[Tuple[List[int], int]]:
        """
        Generates candidate combinations deterministically based on probabilities.
        """
        candidates = []

        # Handle both numpy arrays and dictionaries for probabilities
        if isinstance(wb_probs, np.ndarray):
            wb_dict = {i+1: prob for i, prob in enumerate(wb_probs[:69])}
        else:
            wb_dict = wb_probs

        if isinstance(pb_probs, np.ndarray):
            pb_dict = {i+1: prob for i, prob in enumerate(pb_probs[:26])}
        else:
            pb_dict = pb_dict

        # Prepare lists sorted by probability for deterministic sampling
        wb_sorted = sorted(wb_dict.items(), key=lambda x: x[1], reverse=True)
        pb_sorted = sorted(pb_dict.items(), key=lambda x: x[1], reverse=True)

        # Use fixed seed for reproducibility
        rng = np.random.RandomState(42)

        # Hybrid strategy: combine top probabilities with diversity
        top_wb_count = min(20, len(wb_sorted))  # Top 20 white balls
        top_pb_count = min(10, len(pb_sorted))  # Top 10 powerballs

        attempts = 0
        max_attempts = num_candidates * 3

        while len(candidates) < num_candidates and attempts < max_attempts:
            # Select 5 unique white balls
            if rng.random() < 0.7:  # 70% of the time use top probabilities
                wb_pool = [num for num, _ in wb_sorted[:top_wb_count]]
            else:  # 30% of the time use wider pool for diversity
                wb_pool = [num for num, _ in wb_sorted[:min(40, len(wb_sorted))]]

            white_balls = sorted(rng.choice(wb_pool, size=5, replace=False))

            # Select powerball
            if rng.random() < 0.8:  # 80% of the time use top probabilities
                pb_pool = [num for num, _ in pb_sorted[:top_pb_count]]
            else:
                pb_pool = [num for num, _ in pb_sorted[:min(15, len(pb_sorted))]]

            powerball = rng.choice(pb_pool)

            # Verify that the combination is not duplicated
            combination = (white_balls, powerball)
            if combination not in candidates:
                candidates.append(combination)

            attempts += 1

        logger.info(f"Generated {len(candidates)} unique candidate combinations")
        return candidates

    def _calculate_dataset_hash(self) -> str:
        """
        Calculates SHA256 hash of the historical dataset for version tracking.
        """
        try:
            # Create representative string of the dataset
            dataset_str = ""

            # Include key information from the dataset
            if not self.historical_data.empty:
                # Sort by date for consistency
                sorted_data = self.historical_data.sort_values('draw_date') if 'draw_date' in self.historical_data.columns else self.historical_data

                # Concatenate key values
                for _, row in sorted_data.iterrows():
                    row_str = ""
                    for col in ['draw_date', 'n1', 'n2', 'n3', 'n4', 'n5', 'pb']:
                        if col in row:
                            row_str += str(row[col])
                    dataset_str += row_str

            # Calculate SHA256 hash
            hash_obj = hashlib.sha256(dataset_str.encode('utf-8'))
            dataset_hash = hash_obj.hexdigest()[:16]  # Use first 16 characters

            return dataset_hash

        except Exception as e:
            logger.warning(f"Error calculating dataset hash: {e}")
            return "unknown_hash"
