import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from causalimpact import CausalImpact
import matplotlib.pyplot as plt
import io

st.set_page_config(page_title="Causal Analysis", layout="wide")

# Check if we have simulation data
if 'simulation_data' not in st.session_state:
    st.error("No simulation data found. Please run the simulation first.")
    if st.button("← Go Back to Simulation"):
        st.switch_page("pages/3_⚡_Simulation_Engine.py")
    st.stop()

st.title("📊 Causal Analysis & Validity Checks")

data = st.session_state['simulation_data']
metadata = st.session_state['simulation_metadata']
template = st.session_state['selected_template']

# Check if synthetic control was used
use_synthetic = st.session_state.get('synthetic_weights') is not None
control_label = "Synthetic Control" if use_synthetic else st.session_state['control_market']

st.markdown(f"**Template:** {template['name']} | **Test:** {st.session_state['test_market']} | **Control:** {control_label}")
st.markdown("---")

# ==============================================================================
# SECTION A: CausalImpact Analysis
# ==============================================================================

st.subheader("🔬 CausalImpact Analysis")

st.info("""
**Why CausalImpact?**

CausalImpact uses Bayesian structural time-series modeling to handle SEO's unique characteristics: 
trends, seasonality, and daily volatility. It's the industry standard for incrementality testing.
""")

# Debug: Show data statistics
with st.expander("🔍 Debug: Data Statistics"):
    st.write(f"Data shape: {data.shape}")
    st.write(f"Columns: {data.columns.tolist()}")
    st.write(f"Test market range: [{data['test_market'].min():.0f}, {data['test_market'].max():.0f}]")
    st.write(f"Control market range: [{data['control_market'].min():.0f}, {data['control_market'].max():.0f}]")
    st.write(f"Pre-period test mean: {data[data['period']=='pre']['test_market'].mean():.0f}")
    st.write(f"Post-period test mean: {data[data['period']=='post']['test_market'].mean():.0f}")

# Prepare data for CausalImpact (must have integer index)
ci_data = data[['test_market', 'control_market']].copy()
ci_data.columns = ['y', 'X']
# Reset index to integers (0, 1, 2, ...)
ci_data = ci_data.reset_index(drop=True)

# Find intervention point (day 91 = index 90)
intervention_day = 90

with st.spinner("Running CausalImpact..."):
    try:
        post_start = intervention_day
        post_end = len(ci_data)

        # Run CausalImpact
        ci = CausalImpact(ci_data, pre_period=[0, intervention_day - 1], post_period=[intervention_day, len(ci_data) - 1])
        inferences = ci.inferences.copy()
        predicted = inferences['preds'].values

        # Compute effects
        actual_post = ci_data['y'].iloc[post_start:].values
        predicted_post = inferences['preds'].iloc[post_start:].values

        if len(actual_post) > 0 and len(predicted_post) > 0 and len(actual_post) == len(predicted_post):
            pointwise_effects = actual_post - predicted_post
            point_est = np.nansum(pointwise_effects)
            avg_daily_effect = np.nanmean(pointwise_effects)
        else:
            point_est = np.nan
            avg_daily_effect = np.nan

        post_mean = ci_data['y'].iloc[post_start:].mean()
        post_sum = ci_data['y'].iloc[post_start:].sum()
        pct_effect = (point_est / post_sum * 100) if post_sum != 0 and not np.isnan(point_est) else 0.0

        # Statistical significance
        effect_se = np.nanstd(pointwise_effects) / np.sqrt(len(pointwise_effects)) if len(pointwise_effects) > 0 else np.nan
        z_score = point_est / effect_se if effect_se and effect_se > 0 else 0
        p_value = 2 * (1 - np.exp(-abs(z_score) / np.sqrt(2 * np.pi)))

        # Persist results for downstream pages
        st.session_state['causal_impact'] = ci

        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Estimated Effect",
                f"{point_est:+.0f}",
                help="Cumulative effect in post-period"
            )
        
        with col2:
            st.metric(
                "Effect %",
                f"{pct_effect:+.1f}%",
                help="Effect as % of post-period mean"
            )
        
        with col3:
            st.metric(
                "Post-Period Mean",
                f"{post_mean:+.0f}",
                help="Average value in post-period"
            )
        
        with col4:
            st.metric(
                "Method",
                "CausalImpact",
                help="Bayesian Structural Time-Series"
            )
        
        st.markdown("---")
        
        # Visualization (common for all methods)
        st.subheader("Causal Visualization")
        
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        
        days = np.arange(len(ci_data))
        actual = ci_data['y'].values
        predicted_all = inferences['preds'].values
        
        axes[0].plot(days, actual, 'k-', linewidth=2, label='Actual (y)')
        axes[0].plot(days, predicted_all, 'b--', linewidth=2, label='Predicted Counterfactual')
        axes[0].axvline(x=intervention_day, color='red', linestyle='--', linewidth=2, label='Intervention')
        axes[0].set_ylabel('Value', fontsize=11)
        axes[0].set_title('Original Data vs Predicted Counterfactual', fontsize=12, fontweight='bold')
        axes[0].legend(loc='upper left', fontsize=10)
        axes[0].grid(True, alpha=0.3)
        
        pointwise = actual - predicted_all
        
        axes[1].plot(days, pointwise, 'b-', linewidth=2, label='Pointwise Effect')
        axes[1].axhline(y=0, color='black', linestyle='-', linewidth=1)
        axes[1].axvline(x=intervention_day, color='red', linestyle='--', linewidth=2, label='Intervention')
        axes[1].set_ylabel('Effect', fontsize=11)
        axes[1].set_title('Pointwise Effect (Actual - Predicted)', fontsize=12, fontweight='bold')
        axes[1].legend(loc='upper left', fontsize=10)
        axes[1].grid(True, alpha=0.3)
        
        cumulative = np.zeros(len(ci_data))
        cumulative[:intervention_day] = 0
        cumulative[intervention_day:] = np.cumsum(pointwise[intervention_day:])
        
        axes[2].plot(days, cumulative, 'b-', linewidth=2, label='Cumulative Effect')
        axes[2].axhline(y=0, color='black', linestyle='-', linewidth=1)
        axes[2].axvline(x=intervention_day, color='red', linestyle='--', linewidth=2, label='Intervention')
        axes[2].set_xlabel('Days', fontsize=11)
        axes[2].set_ylabel('Cumulative Effect', fontsize=11)
        axes[2].set_title(f'Cumulative Effect (Final: {cumulative[-1]:+.0f})', fontsize=12, fontweight='bold')
        axes[2].legend(loc='upper left', fontsize=10)
        axes[2].grid(True, alpha=0.3)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        st.image(buf, use_container_width=True)
        plt.close()
        
    except Exception as e:
        st.error(f"Error running analysis: {str(e)}")
        st.info("The selected method encountered an issue. Please check the simulation results and try again.")

st.markdown("---")

# ==============================================================================
# SECTION B: Validity Checks (Traffic Lights)
# ==============================================================================

st.subheader("✓ Validity Checks & Diagnostics")

st.info("""
These checks validate whether the synthetic control is a good match and whether the results are reliable.
""")

# Pre-period similarity
pre_data = data[data['period'] == 'pre']
correlation = pre_data['test_market'].corr(pre_data['control_market'])

if correlation >= 0.85:
    status_sim = "🟢 High"
    color_sim = "green"
elif correlation >= 0.70:
    status_sim = "🟡 Medium"
    color_sim = "orange"
else:
    status_sim = "🔴 Low"
    color_sim = "red"

# Outlier detection
post_data = data[data['period'] == 'post']
differences = (post_data['test_market'] - post_data['control_market']).values
z_scores = np.abs((differences - differences.mean()) / differences.std())
outliers = np.sum(z_scores > 3)

if outliers == 0:
    status_outliers = "🟢 None"
    color_outliers = "green"
elif outliers <= 2:
    status_outliers = "🟡 1-2"
    color_outliers = "orange"
else:
    status_outliers = "🔴 3+"
    color_outliers = "red"

# RMSE check (if we calculated synthetic control fit)
if 'synthetic_weights' in st.session_state and st.session_state['synthetic_weights']:
    rmse_pct = st.session_state['synthetic_weights'].get('rmse', 0) / pre_data['test_market'].mean() * 100
    
    if rmse_pct < 10:
        status_rmse = "🟢 Good"
        color_rmse = "green"
    elif rmse_pct < 15:
        status_rmse = "🟡 Fair"
        color_rmse = "orange"
    else:
        status_rmse = "🔴 Poor"
        color_rmse = "red"
else:
    status_rmse = "⚪ N/A"
    color_rmse = "gray"
    rmse_pct = None

# Display checks
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    **Pre-Period Similarity** {status_sim}
    
    Correlation: {correlation:.3f}
    
    ✓ Good match if ≥ 0.85
    """)

with col2:
    st.markdown(f"""
    **Outlier Detection** {status_outliers}
    
    Outliers (Z>3): {outliers}
    
    ✓ Good if < 3
    """)

with col3:
    if rmse_pct:
        st.markdown(f"""
        **Synthetic Control Fit** {status_rmse}
        
        RMSE %: {rmse_pct:.1f}%
        
        ✓ Good if < 10%
        """)
    else:
        st.markdown(f"""
        **Synthetic Control Fit** {status_rmse}
        
        Not calculated
        """)

# Summary interpretation
st.markdown("---")
st.subheader("📋 Summary")

all_checks_pass = correlation >= 0.85 and outliers < 3
if rmse_pct and rmse_pct < 10:
    all_checks_pass = True

if all_checks_pass:
    st.success("""
    ✅ **Validity checks passed!** 
    
    - Pre-period correlation is strong
    - Minimal outliers detected
    - Results are likely reliable
    """)
else:
    st.warning("""
    ⚠️ **Some concerns noted:**
    
    - Review the pre-period match
    - Check for confounding events
    - Consider extending the test duration
    """)

# Data insights
with st.expander("🔍 SQL: Validity Checks Query"):
    st.code("""
SELECT
    AVG(CASE WHEN period='pre_period' THEN test_value END) as pre_test_avg,
    STDDEV(CASE WHEN period='pre_period' THEN test_value END) as pre_test_std,
    CORR(test_value, control_value) as pre_correlation,
    COUNT(DISTINCT CASE WHEN (test_value - control_value) > 3*STDDEV(test_value - control_value) THEN day_num END) as outlier_count
FROM experiment_metrics
WHERE run_id = :run_id AND period = 'pre_period'
    """, language="sql")

# Navigation
st.markdown("---")
col1, col2 = st.columns(2)

with col1:
    if st.button("← Back to Simulation", use_container_width=True):
        st.switch_page("pages/3_⚡_Simulation_Engine.py")

with col2:
    if st.button("Next: Executive Summary →", use_container_width=True):
        st.switch_page("pages/5_📈_Executive_Summary.py")
