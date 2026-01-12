import numpy as np
import pandas as pd
from typing import Tuple, Dict, List
from datetime import datetime, timedelta


class StochasticSEOGenerator:
    """
    Generates realistic stochastic time-series data for SEO experiments.
    
    Philosophy:
    - Structured stochasticity (not purely random)
    - Interpretable components (trend, seasonality, noise)
    - Different every run, but realistic and repeatable
    """
    
    def __init__(self, seed: int = None):
        """
        Initialize the generator.
        
        Args:
            seed: Optional random seed for reproducibility
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Parameter ranges (internal only - hidden from user)
        self.baseline_mean_range = (500, 5000)
        self.trend_drift_range = (-0.005, 0.005)  # ±0.5% per week
        self.seasonality_amplitude_range = (0.10, 0.15)  # 10-15% of baseline
        self.noise_std_range = (0.05, 0.08)  # 5-8% of baseline
        self.control_correlation_range = (0.80, 0.90)
    
    def generate_baseline(
        self,
        n_days: int = 90,
        baseline_mean: float = None,
        trend_drift: float = None,
        seasonality_amplitude: float = None,
        noise_std: float = None
    ) -> np.ndarray:
        """
        Generate latent baseline series: trend + seasonality.
        
        Args:
            n_days: Number of days to generate
            baseline_mean: Average level (if None, sampled from range)
            trend_drift: Linear trend per day (if None, sampled)
            seasonality_amplitude: Seasonality strength (if None, sampled)
            noise_std: Noise std as % of baseline (if None, sampled)
        
        Returns:
            Array of baseline values
        """
        # Sample parameters if not provided
        if baseline_mean is None:
            baseline_mean = np.random.uniform(*self.baseline_mean_range)
        if trend_drift is None:
            trend_drift = np.random.uniform(*self.trend_drift_range)
        if seasonality_amplitude is None:
            seasonality_amplitude = np.random.uniform(*self.seasonality_amplitude_range)
        if noise_std is None:
            noise_std = np.random.uniform(*self.noise_std_range)
        
        # Build components
        days = np.arange(n_days)
        
        # Trend: Brownian motion with drift
        trend = baseline_mean + trend_drift * days * baseline_mean
        
        # Seasonality: Weekly sine wave
        # Day 0 = Monday, Day 4 = Friday, Day 5-6 = Weekend valley
        day_of_week = days % 7
        seasonality = seasonality_amplitude * baseline_mean * np.sin(2 * np.pi * day_of_week / 7)
        
        # Noise: Gaussian
        noise = np.random.normal(0, noise_std * baseline_mean, n_days)
        
        # Combine
        baseline = trend + seasonality + noise
        
        # Ensure non-negative
        baseline = np.maximum(baseline, 100)
        
        return baseline
    
    def generate_control_market(
        self,
        baseline: np.ndarray,
        correlation: float = None
    ) -> np.ndarray:
        """
        Generate control market as baseline + correlated noise.
        
        Args:
            baseline: Latent baseline series
            correlation: Desired correlation with baseline (if None, sampled)
        
        Returns:
            Control market series
        """
        if correlation is None:
            correlation = np.random.uniform(*self.control_correlation_range)
        
        n_days = len(baseline)
        
        # Correlated noise: ε_control ~ N(0, σ)
        # Correlation achieved by mixing with baseline
        noise = np.random.normal(0, baseline.std() * 0.5, n_days)
        
        # Mix: control = correlation * baseline + (1 - correlation) * independent_noise
        control = correlation * baseline + (1 - correlation) * noise
        
        # Ensure non-negative
        control = np.maximum(control, 100)
        
        return control, correlation
    
    def generate_treatment_market(
        self,
        baseline: np.ndarray,
        effect_params: Dict,
        correlation: float = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Generate treatment market with injected causal effect.
        
        Args:
            baseline: Latent baseline series
            effect_params: Dict with keys:
                - 'intervention_day': Day to start treatment (default 90)
                - 'mde_pct': Effect size as % (e.g., 0.08 for +8%)
                - 'effect_shape': 'step', 'ramp', or 'delayed_step'
            correlation: Control correlation (if None, sampled)
        
        Returns:
            Tuple of (treatment series, applied effects)
        """
        if correlation is None:
            correlation = np.random.uniform(*self.control_correlation_range)
        
        n_days = len(baseline)
        intervention_day = effect_params.get('intervention_day', 90)
        mde_pct = effect_params.get('mde_pct', 0.08)
        effect_shape = effect_params.get('effect_shape', 'step')
        
        # Add randomness to MDE: ±20%
        mde_actual = mde_pct * np.random.uniform(0.80, 1.20)
        
        # Generate correlated noise
        noise = np.random.normal(0, baseline.std() * 0.5, n_days)
        treatment = correlation * baseline + (1 - correlation) * noise
        
        # Build effect injection
        effect_array = np.zeros(n_days)
        
        if effect_shape == 'step':
            # Immediate effect
            effect_array[intervention_day:] = mde_actual * baseline[intervention_day:].mean()
        
        elif effect_shape == 'ramp':
            # Ramp up over 14 days
            ramp_length = 14
            for i in range(intervention_day, min(intervention_day + ramp_length, n_days)):
                ramp_progress = (i - intervention_day) / ramp_length
                effect_array[i] = mde_actual * ramp_progress * baseline[i].mean()
            effect_array[intervention_day + ramp_length:] = mde_actual * baseline[intervention_day:].mean()
        
        elif effect_shape == 'delayed_step':
            # Delay 7 days, then step
            delay = 7
            effect_array[intervention_day + delay:] = mde_actual * baseline[intervention_day:].mean()
        
        treatment = treatment + effect_array
        treatment = np.maximum(treatment, 100)
        
        applied_effects = {
            'intervention_day': intervention_day,
            'mde_requested': mde_pct,
            'mde_applied': mde_actual,
            'effect_shape': effect_shape,
            'correlation': correlation
        }
        
        return treatment, applied_effects
    
    def apply_confounder(
        self,
        series: np.ndarray,
        confounder_type: str,
        intervention_day: int = 90
    ) -> Tuple[np.ndarray, Dict]:
        """
        Apply confounding events to series.
        
        Args:
            series: Time series to modify
            confounder_type: 'algorithm_update', 'seasonality_spike', 'tracking_break'
            intervention_day: Day to start intervention
        
        Returns:
            Tuple of (modified series, confounder info)
        """
        series = series.copy()
        confounder_info = {'type': confounder_type}
        
        if confounder_type == 'algorithm_update':
            # Drop 15-25% for 7 days, starting at random day after intervention
            start_day = np.random.randint(intervention_day, len(series) - 7)
            magnitude = np.random.uniform(0.15, 0.25)
            series[start_day:start_day + 7] *= (1 - magnitude)
            confounder_info['start_day'] = start_day
            confounder_info['magnitude'] = magnitude
        
        elif confounder_type == 'seasonality_spike':
            # +20% for 5 days (simulates holiday/promo)
            start_day = np.random.randint(intervention_day, len(series) - 5)
            magnitude = 0.20
            series[start_day:start_day + 5] *= (1 + magnitude)
            confounder_info['start_day'] = start_day
            confounder_info['magnitude'] = magnitude
        
        elif confounder_type == 'tracking_break':
            # Remove 30% of data points randomly for 3 days
            start_day = np.random.randint(intervention_day, len(series) - 3)
            loss_fraction = 0.30
            for i in range(start_day, start_day + 3):
                if np.random.random() < loss_fraction:
                    series[i] = np.nan
            confounder_info['start_day'] = start_day
            confounder_info['loss_fraction'] = loss_fraction
        
        return series, confounder_info
    
    def generate_experiment_data(
        self,
        test_market: str,
        control_market: str,
        pre_period_days: int = 90,
        post_period_days: int = 42,
        mde_pct: float = 0.08,
        effect_shape: str = 'step',
        confounders: List[str] = None
    ) -> Dict:
        """
        Generate complete experiment dataset.
        
        Args:
            test_market: Name of test market
            control_market: Name of control market
            pre_period_days: Days of pre-intervention data
            post_period_days: Days of post-intervention data
            mde_pct: Effect size as percentage
            effect_shape: 'step', 'ramp', or 'delayed_step'
            confounders: List of confounders to apply
        
        Returns:
            Dict with dataframes and metadata
        """
        total_days = pre_period_days + post_period_days
        
        # Generate latent baseline
        baseline = self.generate_baseline(n_days=total_days)
        
        # Generate markets
        control, control_corr = self.generate_control_market(baseline)
        treatment, effect_info = self.generate_treatment_market(
            baseline,
            {
                'intervention_day': pre_period_days,
                'mde_pct': mde_pct,
                'effect_shape': effect_shape
            }
        )
        
        # Apply confounders if specified
        confounder_log = []
        if confounders:
            for confounder_type in confounders:
                treatment, conf_info = self.apply_confounder(
                    treatment,
                    confounder_type,
                    intervention_day=pre_period_days
                )
                confounder_log.append(conf_info)
        
        # Build dataframe
        dates = pd.date_range(start='2024-10-01', periods=total_days, freq='D')
        
        data = pd.DataFrame({
            'date': dates,
            'test_market': treatment,
            'control_market': control,
            'period': ['pre'] * pre_period_days + ['post'] * post_period_days,
            'day_num': range(1, total_days + 1)
        })
        
        metadata = {
            'test_market_name': test_market,
            'control_market_name': control_market,
            'pre_period_days': pre_period_days,
            'post_period_days': post_period_days,
            'effect_info': effect_info,
            'control_correlation': control_corr,
            'confounders': confounder_log
        }
        
        return {'data': data, 'metadata': metadata}
