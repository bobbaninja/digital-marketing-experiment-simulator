import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import uuid
from src.data_generator import StochasticSEOGenerator
from src.db_manager import DuckDBManager

st.set_page_config(page_title="Simulation Engine", layout="wide")

# Check if we have the required session state from Page 2
required_keys = [
    'selected_template',
    'test_market',
    'control_market',
    'experiment_duration',
    'mde_pct',
    'achieved_power'
]

for key in required_keys:
    if key not in st.session_state:
        st.error(f"Missing {key}. Please complete Page 2 first.")
        if st.button("← Go Back to Experiment Design"):
            st.switch_page("pages/2_🎯_Experiment_Design.py")
        st.stop()

st.title("⚡ Simulation Engine")

# Get from session state
template = st.session_state['selected_template']
test_market = st.session_state['test_market']
control_market = st.session_state['control_market']
duration_days = st.session_state['experiment_duration']
mde_pct = st.session_state['mde_pct']
achieved_power = st.session_state['achieved_power']

st.markdown(f"""
**Template:** {template['name']}
**Test Market:** {test_market}  |  **Control Market:** {control_market}
**Duration:** {duration_days} days  |  **Achieved Power:** {achieved_power:.1%}  |  **MDE:** {mde_pct*100:.1f}%
""")

st.markdown("---")

# ==============================================================================
# SECTION A: Chaos Injectors
# ==============================================================================

st.subheader("🎲 Chaos Injectors (Optional Confounders)")

st.info("""
Inject realistic confounders to test model resilience. These events will disrupt both test and control 
markets to simulate real-world interference like algorithm updates or seasonal spikes.
""")

col1, col2, col3 = st.columns(3)

with col1:
    inject_algorithm_update = st.checkbox(
        "🔴 Google Core Update",
        value=False,
        help="Simulate a 15-25% traffic drop for 7 days on both markets"
    )

with col2:
    inject_seasonality_spike = st.checkbox(
        "📈 Seasonality Spike",
        value=False,
        help="Simulate a +20% holiday/promo spike for 5 days on both markets"
    )

with col3:
    inject_tracking_break = st.checkbox(
        "⚠️ Tracking Break",
        value=False,
        help="Simulate 30% data loss for 3 days on test market only"
    )

# Collect confounders
confounders_to_apply = []
if inject_algorithm_update:
    confounders_to_apply.append('algorithm_update')
if inject_seasonality_spike:
    confounders_to_apply.append('seasonality_spike')
if inject_tracking_break:
    confounders_to_apply.append('tracking_break')

st.markdown("---")

# ==============================================================================
# SECTION B: Run Simulation
# ==============================================================================

st.subheader("▶️ Run Simulation")

# Initialize data generator
data_gen = StochasticSEOGenerator(seed=int(datetime.now().timestamp()) % 10000)

if st.button("🚀 Generate & Run Simulation", use_container_width=True, type="primary"):
    with st.spinner("Generating experiment data..."):
        # Generate experiment data
        result = data_gen.generate_experiment_data(
            test_market=test_market,
            control_market=control_market,
            pre_period_days=90,
            post_period_days=duration_days,
            mde_pct=mde_pct,
            effect_shape='step',  # Default effect shape
            confounders=confounders_to_apply if confounders_to_apply else None
        )
        
        data = result['data']
        metadata = result['metadata']
        
        # Store in session state
        st.session_state['simulation_data'] = data
        st.session_state['simulation_metadata'] = metadata
        
        st.success("✅ Simulation complete!")
        st.rerun()

st.markdown("---")

# ==============================================================================
# SECTION C: Results & Visualization
# ==============================================================================

if 'simulation_data' in st.session_state:
    st.subheader("📊 Simulation Results")
    
    data = st.session_state['simulation_data']
    metadata = st.session_state['simulation_metadata']
    
    # Summary metrics
    pre_data = data[data['period'] == 'pre']
    post_data = data[data['period'] == 'post']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Pre-Period Correlation",
            f"{metadata['control_correlation']:.3f}",
            help="How well test and control tracked in pre-period"
        )
    
    with col2:
        pre_avg_diff = (pre_data['test_market'] - pre_data['control_market']).mean()
        st.metric(
            "Pre-Period Avg Difference",
            f"{pre_avg_diff:+.0f}",
            help="Raw difference between test and control"
        )
    
    with col3:
        post_avg_test = post_data['test_market'].mean()
        post_avg_control = post_data['control_market'].mean()
        post_lift_pct = ((post_avg_test - post_avg_control) / post_avg_control * 100)
        st.metric(
            "Post-Period Lift",
            f"{post_lift_pct:+.1f}%",
            help="Observed effect size in post-period"
        )
    
    with col4:
        applied_mde = metadata['effect_info']['mde_applied']
        st.metric(
            "Applied MDE",
            f"{applied_mde*100:+.1f}%",
            help="Actual effect injected (±20% randomness)"
        )
    
    st.markdown("---")
    
    # Interactive chart
    st.subheader("📈 Time Series: Test vs Control")
    
    fig = go.Figure()
    
    # Test market
    fig.add_trace(go.Scatter(
        x=data['date'],
        y=data['test_market'],
        mode='lines',
        name='Test Market',
        line=dict(color='#1f77b4', width=2),
        hovertemplate='<b>Test Market</b><br>Date: %{x}<br>Value: %{y:.0f}<extra></extra>'
    ))
    
    # Control market
    fig.add_trace(go.Scatter(
        x=data['date'],
        y=data['control_market'],
        mode='lines',
        name='Control Market',
        line=dict(color='#ff7f0e', width=2),
        hovertemplate='<b>Control Market</b><br>Date: %{x}<br>Value: %{y:.0f}<extra></extra>'
    ))
    
    # Intervention line
    intervention_date = data[data['period'] == 'post'].iloc[0]['date'] if len(post_data) > 0 else None
    if intervention_date:
        # Use add_shape instead of add_vline to avoid datetime arithmetic issues
        fig.add_shape(
            type="line",
            x0=intervention_date, x1=intervention_date,
            y0=0, y1=1,
            yref="paper",
            line=dict(color="red", width=2, dash="dash")
        )
        fig.add_annotation(
            x=intervention_date,
            text="Intervention",
            showarrow=False,
            yanchor="top"
        )
    
    # Confounder annotations
    confounder_info = metadata.get('confounders', [])
    for confounder in confounder_info:
        confounder_date = data[data['day_num'] == confounder.get('start_day', 100)]['date'].iloc[0] if confounder.get('start_day') else None
        if confounder_date:
            confounder_name = confounder['type'].replace('_', ' ').title()
            fig.add_shape(
                type="line",
                x0=confounder_date, x1=confounder_date,
                y0=0, y1=1,
                yref="paper",
                line=dict(color="orange", width=1, dash="dot")
            )
            fig.add_annotation(
                x=confounder_date,
                text=confounder_name,
                showarrow=False,
                yanchor="bottom"
            )
    
    fig.update_layout(
        title="Test Market vs Control Market Over Time",
        xaxis_title="Date",
        yaxis_title="Metric Value",
        height=500,
        hovermode='x unified',
        template='plotly_white'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Confounder summary
    if confounder_info:
        st.subheader("⚠️ Confounders Applied")
        
        confounders_df = pd.DataFrame([
            {
                'Type': c['type'].replace('_', ' ').title(),
                'Start Day': c.get('start_day', 'N/A'),
                'Duration': f"{c.get('magnitude', 0):.0%}" if 'magnitude' in c else f"{c.get('loss_fraction', 0):.0%}"
            }
            for c in confounder_info
        ])
        
        st.dataframe(confounders_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Data preview
    with st.expander("📋 Data Preview"):
        st.write("**First 10 rows (Pre-period):**")
        st.dataframe(data.head(10), use_container_width=True, hide_index=True)
        
        st.write("**Last 10 rows (Post-period):**")
        st.dataframe(data.tail(10), use_container_width=True, hide_index=True)
    
    # SQL query
    with st.expander("🔍 SQL: Query Simulation Results"):
        st.code("""
SELECT
    date,
    test_market,
    control_market,
    (test_market - control_market) as raw_diff,
    ((test_market - control_market) / control_market * 100) as pct_diff,
    period,
    day_num
FROM experiment_metrics
WHERE run_id = :run_id
ORDER BY date
        """, language="sql")
    
    # Navigation
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("← Back to Experiment Design", use_container_width=True):
            # Clear simulation state
            del st.session_state['simulation_data']
            del st.session_state['simulation_metadata']
            st.switch_page("pages/2_🎯_Experiment_Design.py")
    
    with col2:
        if st.button("Next: Analyze Results →", use_container_width=True):
            st.switch_page("pages/4_📊_Causal_Analysis.py")
else:
    st.info("👆 Click **'Generate & Run Simulation'** above to create synthetic data for your experiment.")
