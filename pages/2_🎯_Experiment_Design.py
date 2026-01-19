import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from src.market_matcher import MarketMatcher
from src.power_calculator import PowerCalculator
from src.data_generator import StochasticSEOGenerator
import yaml

st.set_page_config(page_title="Experiment Design", layout="wide")

# Initialize session state
if 'test_market' not in st.session_state:
    st.session_state['test_market'] = None
if 'control_market' not in st.session_state:
    st.session_state['control_market'] = None
if 'pre_period_data' not in st.session_state:
    st.session_state['pre_period_data'] = None
if 'synthetic_weights' not in st.session_state:
    st.session_state['synthetic_weights'] = None
if 'control_markets_data_cached' not in st.session_state:
    st.session_state['control_markets_data_cached'] = None

st.title("🎯 Experiment Design & Power Calculation")

# Get selected template
template = st.session_state.get('selected_template')
if not template:
    st.error("No template selected. Please go back and select a template.")
    if st.button("← Back to Template Selection"):
        st.switch_page("pages/1_📋_SEO_Template.py")
    st.stop()

st.markdown(f"**Template:** {template['name']}")
st.markdown(f"**Primary Metric:** {template['primary_metric']}")
st.markdown("---")

# Initialize tools
matcher = MarketMatcher()
power_calc = PowerCalculator()

# ==============================================================================
# GENERATE & CACHE CONTROL MARKET DATA (one-time on page load)
# ==============================================================================

if st.session_state['control_markets_data_cached'] is None:
    with st.spinner("Generating control market data (one-time cache)..."):
        # Use a fixed seed for reproducible control markets across page loads
        data_gen = StochasticSEOGenerator(seed=42)
        
        control_markets_data = {}
        for dma in matcher.get_dma_list():
            baseline_other = data_gen.generate_baseline(n_days=90)
            control_markets_data[dma], _ = data_gen.generate_control_market(baseline_other)
        
        # Cache in session state
        st.session_state['control_markets_data_cached'] = control_markets_data
else:
    control_markets_data = st.session_state['control_markets_data_cached']

# ==============================================================================
# SECTION A: Market Selection & Matching
# ==============================================================================

st.subheader("📍 Section 1: Market Selection")

col1, col2 = st.columns(2)

with col1:
    test_market = st.selectbox(
        "Test Market",
        options=matcher.get_dma_list(),
        key="test_market_select"
    )
    st.session_state['test_market'] = test_market

with col2:
    st.info("""
    **Test Market:** The market where you're implementing the SEO initiative.
    This is where the treatment effect will be injected.
    """)

# Generate test market data (unique for each test market selection)
with st.spinner("Generating test market data..."):
    # Use test market name to generate unique but reproducible seed
    test_market_seed = hash(test_market) % 10000
    data_gen = StochasticSEOGenerator(seed=test_market_seed)
    
    # Generate baseline data (90 days)
    baseline = data_gen.generate_baseline(n_days=90)
    
    # Generate test market
    test_data, _ = data_gen.generate_control_market(baseline)

# Market matching via Euclidean distance
st.subheader("📊 Section 2: Find Best Control Markets")

with st.spinner("Calculating Euclidean distances..."):
    matches = matcher.find_best_controls(test_data, control_markets_data, top_k=5)

st.dataframe(matches, use_container_width=True, hide_index=True)

# Select control market
selected_control = st.selectbox(
    "Select Control Market",
    options=matches['Market'].tolist(),
    key="control_market_select"
)

st.session_state['control_market'] = selected_control

# Level-align control to test market mean (best practice for fair comparison)
control_raw = control_markets_data[selected_control]
test_mean = np.mean(test_data)
control_mean = np.mean(control_raw)
control_aligned = control_raw * (test_mean / control_mean) if control_mean != 0 else control_raw

st.session_state['pre_period_data'] = {
    'test': test_data,
    'control': control_aligned
}

# Show pre-period similarity
pre_similarity = matcher.correlation(test_data, control_markets_data[selected_control])
st.metric("Pre-Period Correlation", f"{pre_similarity:.3f}")

st.markdown("---")

# ==============================================================================
# SECTION B: Synthetic Control Builder
# ==============================================================================

st.subheader("🔧 Section 3: Synthetic Control Builder (Optional)")

use_synthetic = st.checkbox(
    "Use Synthetic Control (Ridge Regression)",
    value=True,
    help="Build a weighted combination of multiple controls for better pre-period fit"
)

if use_synthetic:
    st.info("Building synthetic control from top 3 candidates...")
    
    top_3_controls = matches['Market'].head(3).tolist()
    top_3_data = {name: control_markets_data[name] for name in top_3_controls}
    
    # Build synthetic control
    synthetic, sc_metadata = matcher.build_synthetic_control(
        test_data,
        top_3_data,
        selected_controls=top_3_controls,
        alpha=1.0
    )
    
    # Level-align synthetic control to test market mean
    synthetic_mean = np.mean(synthetic)
    test_mean = np.mean(test_data)
    synthetic_aligned = synthetic * (test_mean / synthetic_mean) if synthetic_mean != 0 else synthetic
    
    # Update session state with aligned synthetic control
    st.session_state['pre_period_data']['control'] = synthetic_aligned
    
    st.session_state['synthetic_weights'] = sc_metadata
    
    # Display weights
    col1, col2 = st.columns(2)
    
    with col1:
        weights_df = pd.DataFrame([
            {'Market': name, 'Weight': weight}
            for name, weight in sc_metadata['normalized_weights'].items()
        ])
        st.dataframe(weights_df, use_container_width=True, hide_index=True)
    
    with col2:
        # Pie chart of weights
        fig = go.Figure(data=[go.Pie(
            labels=list(sc_metadata['normalized_weights'].keys()),
            values=[abs(w) for w in sc_metadata['normalized_weights'].values()],
            hole=0.3
        )])
        fig.update_layout(height=300, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    # Show fit quality
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("RMSE", f"{sc_metadata['rmse']:.2f}")
    with col2:
        st.metric("R-Squared", f"{sc_metadata['r_squared']:.3f}")
    with col3:
        st.metric("Correlation", f"{matcher.correlation(test_data, synthetic):.3f}")
    
    # User can lock or adjust
    allow_adjustment = st.checkbox("Allow manual weight adjustment", value=False)
    if allow_adjustment:
        st.warning("⚠️ Advanced mode: Manual weights not yet implemented in MVP")
else:
    st.info("Using single control market without synthetic combination.")

st.markdown("---")

# ==============================================================================
# SECTION C: Pre-Period Time Series Preview
# ==============================================================================

st.subheader("📈 Section 4: Pre-Period Trend Similarity")

# Determine which control series to plot: synthetic or single control
if use_synthetic and 'synthetic_weights' in st.session_state and st.session_state['synthetic_weights']:
    # Use the level-aligned synthetic control series from session state
    control_series = st.session_state['pre_period_data']['control']
    control_label = "Synthetic Control (Level-Aligned)"
else:
    # Use level-aligned single control
    control_series = st.session_state['pre_period_data']['control']
    control_label = "Control Market (Level-Aligned)"

pre_df = pd.DataFrame({
    'date': pd.date_range(start='2024-10-01', periods=len(test_data), freq='D'),
    'test_market': test_data,
    'control_market': control_series
})

fig_pre = go.Figure()
fig_pre.add_trace(go.Scatter(
    x=pre_df['date'],
    y=pre_df['test_market'],
    mode='lines',
    name='Test Market',
    line=dict(color='#1f77b4', width=2)
))
fig_pre.add_trace(go.Scatter(
    x=pre_df['date'],
    y=pre_df['control_market'],
    mode='lines',
    name=control_label,
    line=dict(color='#ff7f0e', width=2)
))
fig_pre.update_layout(
    title="Pre-Period Trend (90 Days)",
    xaxis_title="Date",
    yaxis_title="Metric Value",
    height=350,
    hovermode='x unified',
    template='plotly_white'
)
st.plotly_chart(fig_pre, use_container_width=True)

st.markdown("---")

# ==============================================================================
# SECTION D: Power Calculation
# ==============================================================================

st.subheader("📈 Section 4: Power & Duration Calculation")

# Get baseline statistics from pre-period data
test_pre = st.session_state['pre_period_data']['test']
baseline_stats = power_calc.estimate_sample_characteristics(test_pre)

st.info(f"""
**Pre-Period Statistics:**
- Mean: {baseline_stats['baseline_mean']:.0f}
- Std Dev: {baseline_stats['baseline_std']:.0f}
- Coefficient of Variation: {baseline_stats['baseline_cv']:.3f}
""")

# Input power parameters
col1, col2, col3 = st.columns(3)

with col1:
    alpha = st.select_slider(
        "Significance Level (α)",
        options=[0.01, 0.05, 0.10],
        value=0.05,
        help="Probability of Type I error (rejecting true null)"
    )

with col2:
    power = st.select_slider(
        "Statistical Power (1-β)",
        options=[0.70, 0.80, 0.90],
        value=0.80,
        help="Probability of detecting true effect"
    )

with col3:
    mde_pct = st.number_input(
        "MDE (%)",
        value=template['default_mde'],
        min_value=1,
        max_value=50,
        step=1,
        help="Minimum Detectable Effect as percentage"
    )

# Calculate required duration
calc_result = power_calc.calculate_required_duration(
    baseline_mean=baseline_stats['baseline_mean'],
    baseline_std=baseline_stats['baseline_std'],
    mde_pct=mde_pct / 100,
    alpha=alpha,
    power=power
)

required_days = calc_result['required_days']

# Show calculation breakdown
st.markdown("---")
st.subheader("📐 Sample Size Calculation")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("""
    **Formula (Two-Sample T-Test):**
    
    $$n = \\frac{2 \\times (Z_\\alpha + Z_\\beta)^2 \\times \\sigma^2}{\\Delta^2}$$
    
    Where:
    - n = required days
    - Z_α, Z_β = critical values
    - σ = baseline std dev
    - Δ = absolute effect size
    """)

with col2:
    st.markdown(f"""
    **Your Calculation:**
    
    - **Z_α** (α={alpha}) = {calc_result['z_alpha']:.3f}
    - **Z_β** (power={power:.0%}) = {calc_result['z_beta']:.3f}
    - **σ** (baseline std) = {baseline_stats['baseline_std']:.1f}
    - **Δ** (MDE) = {mde_pct}% × {baseline_stats['baseline_mean']:.0f} = {calc_result['delta_absolute']:.1f}
    
    ---
    
    $$n = \\frac{{2 \\times ({calc_result['z_alpha']:.3f} + {calc_result['z_beta']:.3f})^2 \\times {baseline_stats['baseline_std']:.1f}^2}}{{{calc_result['delta_absolute']:.1f}^2}}$$
    
    $$n = {required_days} \\text{{ days}}$$
    """)

st.success(f"**Required Duration: {required_days} days**")

# Duration slider for override
col1, col2 = st.columns([2, 1])

with col1:
    selected_days = st.slider(
        "Adjust Duration (Experiment Days)",
        min_value=7,
        max_value=90,
        value=required_days,
        step=7,
        help="Increase duration to achieve higher power, or decrease to run faster"
    )

with col2:
    # Calculate achieved power at selected duration
    power_result = power_calc.calculate_achieved_power(
        baseline_mean=baseline_stats['baseline_mean'],
        baseline_std=baseline_stats['baseline_std'],
        mde_pct=mde_pct / 100,
        duration_days=selected_days,
        alpha=alpha
    )
    achieved_power = power_result['achieved_power']
    status, msg = power_calc.get_power_status(achieved_power)
    st.metric("Achieved Power", f"{achieved_power:.1%}")

# Power vs Duration chart
durations = range(7, 91, 7)
powers = []
for d in durations:
    p_res = power_calc.calculate_achieved_power(
        baseline_mean=baseline_stats['baseline_mean'],
        baseline_std=baseline_stats['baseline_std'],
        mde_pct=mde_pct / 100,
        duration_days=d,
        alpha=alpha
    )
    powers.append(p_res['achieved_power'])

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=list(durations),
    y=powers,
    mode='lines+markers',
    name='Achieved Power',
    line=dict(color='#1f77b4', width=3),
    marker=dict(size=8)
))
fig.add_hline(y=0.80, line_dash="dash", line_color="green", annotation_text="Target Power (80%)")
fig.add_vline(x=selected_days, line_dash="dot", line_color="orange", annotation_text=f"Selected: {selected_days}d")
fig.update_layout(
    title="Power vs Duration",
    xaxis_title="Duration (days)",
    yaxis_title="Statistical Power",
    height=300,
    hovermode='x unified'
)
st.plotly_chart(fig, use_container_width=True)

# SQL query demonstration
with st.expander("🔍 SQL: View Power Calculation Query"):
    st.code("""
SELECT
    baseline_mean,
    baseline_std,
    mde_pct,
    alpha,
    power,
    required_days,
    selected_duration,
    achieved_power
FROM power_calculations
WHERE template_id = :template_id
ORDER BY created_at DESC
LIMIT 1
    """, language="sql")

st.markdown("---")

# ==============================================================================
# Navigation & Summary
# ==============================================================================

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Template", use_container_width=True):
        st.switch_page("pages/1_📋_SEO_Template.py")

with col2:
    st.info(f"**Duration:** {selected_days} days | **Power:** {achieved_power:.1%}")

with col3:
    if st.button("Next: Run Simulation →", use_container_width=True):
        # Save to session state
        st.session_state['experiment_duration'] = selected_days
        st.session_state['achieved_power'] = achieved_power
        st.session_state['mde_pct'] = mde_pct / 100
        st.session_state['alpha'] = alpha
        st.session_state['power'] = power
        
        st.switch_page("pages/3_⚡_Simulation_Engine.py")
