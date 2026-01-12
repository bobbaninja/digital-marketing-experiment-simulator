import numpy as np
from scipy import stats
from typing import Dict, Tuple


class PowerCalculator:
    """
    Calculates required sample size (duration) for SEO experiments.
    Uses two-sample t-test methodology.
    """
    
    def __init__(self):
        """Initialize the calculator."""
        pass
    
    def calculate_required_duration(
        self,
        baseline_mean: float,
        baseline_std: float,
        mde_pct: float,
        alpha: float = 0.05,
        power: float = 0.80
    ) -> Dict:
        """
        Calculate required duration (sample size) for experiment.
        
        Formula (two-sample t-test):
        n = 2 * (Z_alpha + Z_beta)^2 * sigma^2 / (delta)^2
        
        Where:
        - n = sample size per group (days)
        - Z_alpha = critical value for significance level
        - Z_beta = critical value for power (1 - beta)
        - sigma = pooled standard deviation
        - delta = minimum detectable effect (absolute)
        
        Args:
            baseline_mean: Average metric value in pre-period
            baseline_std: Standard deviation in pre-period
            mde_pct: Minimum detectable effect as percentage (e.g., 0.08 for 8%)
            alpha: Significance level (default 0.05 for 95% confidence)
            power: Statistical power (default 0.80 for 80% power)
        
        Returns:
            Dict with sample size and related metrics
        """
        # Critical values from standard normal distribution
        z_alpha = stats.norm.ppf(1 - alpha / 2)  # Two-tailed
        z_beta = stats.norm.ppf(power)
        
        # Absolute effect size
        delta = baseline_mean * mde_pct
        
        # Sample size formula
        n = 2 * ((z_alpha + z_beta) ** 2) * (baseline_std ** 2) / (delta ** 2)
        
        # Round up to nearest day
        n = int(np.ceil(n))
        
        # Ensure minimum of 7 days (1 week)
        n = max(n, 7)
        
        # Ensure maximum of 90 days (about 3 months)
        n = min(n, 90)
        
        result = {
            'required_days': n,
            'baseline_mean': baseline_mean,
            'baseline_std': baseline_std,
            'mde_pct': mde_pct,
            'alpha': alpha,
            'power': power,
            'z_alpha': z_alpha,
            'z_beta': z_beta,
            'delta_absolute': delta,
        }
        
        return result
    
    def calculate_achieved_power(
        self,
        baseline_mean: float,
        baseline_std: float,
        mde_pct: float,
        duration_days: int,
        alpha: float = 0.05
    ) -> Dict:
        """
        Calculate achieved power given a fixed duration.
        (Inverse of calculate_required_duration)
        
        Args:
            baseline_mean: Average metric value
            baseline_std: Standard deviation
            mde_pct: Minimum detectable effect as percentage
            duration_days: Number of days in experiment
            alpha: Significance level
        
        Returns:
            Dict with achieved power and related metrics
        """
        # Critical value
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        
        # Absolute effect size
        delta = baseline_mean * mde_pct
        
        # Non-centrality parameter
        ncp = (delta / baseline_std) * np.sqrt(duration_days / 2)
        
        # Achieved power (probability of rejecting H0)
        achieved_power = 1 - stats.nct.cdf(z_alpha, df=2*duration_days - 2, nc=ncp)
        
        # Ensure power is between 0 and 1
        achieved_power = np.clip(achieved_power, 0, 1)
        
        result = {
            'achieved_power': achieved_power,
            'duration_days': duration_days,
            'baseline_mean': baseline_mean,
            'baseline_std': baseline_std,
            'mde_pct': mde_pct,
            'alpha': alpha,
            'ncp': ncp,
        }
        
        return result
    
    def get_power_status(self, achieved_power: float) -> Tuple[str, str]:
        """
        Get status indicator and message for achieved power.
        
        Args:
            achieved_power: Achieved power value (0-1)
        
        Returns:
            Tuple of (status, message)
            status: 'high', 'medium', 'low'
        """
        if achieved_power >= 0.80:
            return ('high', f'✓ High power ({achieved_power:.1%})')
        elif achieved_power >= 0.70:
            return ('medium', f'⚠ Medium power ({achieved_power:.1%}) - Consider extending')
        else:
            return ('low', f'✗ Low power ({achieved_power:.1%}) - Increase duration')
    
    def estimate_sample_characteristics(
        self,
        pre_period_data: np.ndarray
    ) -> Dict:
        """
        Estimate baseline mean and std from pre-period data.
        
        Args:
            pre_period_data: Array of pre-period metric values
        
        Returns:
            Dict with mean and std
        """
        return {
            'baseline_mean': np.mean(pre_period_data),
            'baseline_std': np.std(pre_period_data, ddof=1),  # Sample std
            'baseline_cv': np.std(pre_period_data, ddof=1) / np.mean(pre_period_data),  # Coefficient of variation
        }
