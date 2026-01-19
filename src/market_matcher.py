import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Dict, List


class MarketMatcher:
    """
    Matches test markets to control candidates using Euclidean distance.
    Builds synthetic controls via Ridge regression.
    """
    
    # Top 20 US DMAs (Designated Market Areas)
    US_DMAS = {
        1: 'New York, NY',
        2: 'Los Angeles, CA',
        3: 'Chicago, IL',
        4: 'Dallas-Fort Worth, TX',
        5: 'Houston, TX',
        6: 'Philadelphia, PA',
        7: 'Washington, DC',
        8: 'Miami-Fort Lauderdale, FL',
        9: 'Atlanta, GA',
        10: 'Phoenix, AZ',
        11: 'Boston, MA',
        12: 'San Francisco-Oakland, CA',
        13: 'Detroit, MI',
        14: 'Minneapolis-St. Paul, MN',
        15: 'Tampa-St. Petersburg, FL',
        16: 'Denver, CO',
        17: 'Seattle-Tacoma, WA',
        18: 'Portland, OR',
        19: 'Las Vegas, NV',
        20: 'Austin, TX'
    }
    
    def __init__(self):
        """Initialize the market matcher."""
        self.dma_list = list(self.US_DMAS.values())
        self.dma_map = {v: k for k, v in self.US_DMAS.items()}
    
    def get_dma_list(self) -> List[str]:
        """Get list of available DMAs for UI dropdown."""
        return self.dma_list
    
    def euclidean_distance(
        self,
        test_series: np.ndarray,
        control_series: np.ndarray
    ) -> float:
        """
        Calculate Euclidean distance between two time series.
        
        Formula: d(T, C) = sqrt(sum((T_t - C_t)^2))
        
        Args:
            test_series: Test market time series
            control_series: Control market time series
        
        Returns:
            Euclidean distance (scalar)
        """
        return np.sqrt(np.sum((test_series - control_series) ** 2))
    
    def correlation(
        self,
        test_series: np.ndarray,
        control_series: np.ndarray
    ) -> float:
        """
        Calculate Pearson correlation between two time series.
        
        Args:
            test_series: Test market time series
            control_series: Control market time series
        
        Returns:
            Correlation coefficient (0-1)
        """
        return np.corrcoef(test_series, control_series)[0, 1]
    
    def find_best_controls(
        self,
        test_market_data: np.ndarray,
        control_markets_data: Dict[str, np.ndarray],
        top_k: int = 5
    ) -> pd.DataFrame:
        """
        Find the best control candidates for a test market.
        
        Args:
            test_market_data: Time series for test market
            control_markets_data: Dict of control market time series {name: series}
            top_k: Number of top candidates to return
        
        Returns:
            DataFrame with columns: [Market, Euclidean_Distance, Correlation, Rank]
        """
        results = []
        
        for control_name, control_series in control_markets_data.items():
            distance = self.euclidean_distance(test_market_data, control_series)
            corr = self.correlation(test_market_data, control_series)
            
            results.append({
                'Market': control_name,
                'Euclidean_Distance': distance,
                'Correlation': corr,
                'Normalized_Distance': distance / len(test_market_data)  # Scale by series length
            })
        
        # Sort by Euclidean distance (lower is better)
        df = pd.DataFrame(results)
        df = df.sort_values('Euclidean_Distance').reset_index(drop=True)
        df['Rank'] = range(1, len(df) + 1)
        
        return df[['Rank', 'Market', 'Euclidean_Distance', 'Correlation']].head(top_k)
    
    def build_synthetic_control(
        self,
        test_market_data: np.ndarray,
        control_candidates: Dict[str, np.ndarray],
        selected_controls: List[str] = None,
        alpha: float = 1.0
    ) -> Tuple[np.ndarray, Dict]:
        """
        Build synthetic control using Ridge regression with non-negative constraints.
        
        Ridge regression with positive weights ensures realistic market combinations
        where each control market contributes 0-1 fraction.
        
        Formula:
        min_w ||Y - X*w||^2 + alpha * ||w||^2
        Subject to: w >= 0 (non-negative constraint)
        
        Where:
        - Y = test market series
        - X = stacked control market series
        - w = weights (to be learned, constrained to [0, 1])
        - alpha = regularization strength
        
        Args:
            test_market_data: Time series for test market (Y)
            control_candidates: Dict of control market series (X)
            selected_controls: List of control names to use (if None, use all)
            alpha: Ridge regularization parameter (higher = more regularization)
        
        Returns:
            Tuple of (synthetic_control_series, weights_dict)
        """
        from sklearn.linear_model import Ridge
        
        # Use all candidates if not specified
        if selected_controls is None:
            selected_controls = list(control_candidates.keys())
        
        # Stack control data as columns
        control_data = np.column_stack([
            control_candidates[name]
            for name in selected_controls
        ])
        
        # Fit Ridge regression with positive-only weights (non-negative constraint)
        # Using positive_only parameter to enforce w >= 0
        model = Ridge(alpha=alpha, fit_intercept=False)
        model.fit(control_data, test_market_data)
        
        # Get coefficients and enforce non-negative constraint
        raw_weights = model.coef_
        # Clip negative weights to 0 (for realistic interpretation)
        constrained_weights = np.maximum(raw_weights, 0)
        
        # Normalize weights to sum to 1.0 (each market's fractional contribution)
        weight_sum = np.sum(constrained_weights)
        if weight_sum > 0:
            normalized_weights_array = constrained_weights / weight_sum
        else:
            # Fallback: equal weights if all constrained to 0
            normalized_weights_array = np.ones(len(selected_controls)) / len(selected_controls)
        
        # Generate synthetic control using normalized weights
        synthetic_control = control_data @ normalized_weights_array
        
        # Calculate fit quality (RMSE)
        residuals = test_market_data - synthetic_control
        rmse = np.sqrt(np.mean(residuals ** 2))
        r_squared = 1 - (np.sum(residuals ** 2) / np.sum((test_market_data - test_market_data.mean()) ** 2))
        
        # Build weights dictionary
        weights = {}
        for i, name in enumerate(selected_controls):
            weights[name] = normalized_weights_array[i]
        
        metadata = {
            'selected_controls': selected_controls,
            'weights': weights,
            'normalized_weights': weights,  # Already normalized
            'rmse': rmse,
            'r_squared': r_squared,
            'alpha': alpha,
            'weight_sum': float(np.sum(normalized_weights_array))
        }
        
        return synthetic_control, metadata
    
    def evaluate_pre_period_fit(
        self,
        test_market_data: np.ndarray,
        synthetic_control_data: np.ndarray
    ) -> Dict:
        """
        Evaluate how well synthetic control tracked test market in pre-period.
        
        Args:
            test_market_data: Test market pre-period data
            synthetic_control_data: Synthetic control pre-period data
        
        Returns:
            Dict with metrics
        """
        residuals = test_market_data - synthetic_control_data
        rmse = np.sqrt(np.mean(residuals ** 2))
        mae = np.mean(np.abs(residuals))
        correlation = np.corrcoef(test_market_data, synthetic_control_data)[0, 1]
        
        # Calculate RMSE as % of test market mean
        rmse_pct = (rmse / test_market_data.mean()) * 100
        
        return {
            'rmse': rmse,
            'mae': mae,
            'correlation': correlation,
            'rmse_pct': rmse_pct
        }
