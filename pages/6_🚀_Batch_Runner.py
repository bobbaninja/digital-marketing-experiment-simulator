import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from causalimpact import CausalImpact
from src.data_generator import StochasticSEOGenerator
import time

st.set_page_config(page_title="Batch Runner", layout="wide")

st.title("🚀 Batch Runner - Multiple Experiments")

st.markdown("""
Run multiple independent experiments to test robustness and compare results across different 
test/control market pairs and configurations.
""")

st.markdown("---")

# ==============================================================================
# SECTION A: BATCH CONFIGURATION
# ==============================================================================

st.subheader("⚙️ Batch Configuration")

col1, col2 = st.columns(2)

with col1:
    num_experiments = st.slider(
        "Number of Experiments",
        min_value=2,
        max_value=10,
        value=3,
        step=1,
        help="Run multiple independent experiments with different market pairs"
    )
    
    experiment_duration = st.slider(
        "Experiment Duration (days)",
        min_value=14,
        max_value=90,
        value=42,
        step=7,
        help="Post-period duration for each experiment"
    )

with col2:
    include_confounders = st.checkbox(
        "Include Random Confounders",
        value=False,
        help="Randomly inject algorithm updates, seasonality spikes, or tracking breaks"
    )
    
    effect_sizes = st.multiselect(
        "Effect Sizes to Test",
        options=[2, 5, 10, 15],
        default=[5, 10],
        help="Run experiments with these different treatment effects"
    )

st.markdown("---")

# ==============================================================================
# SECTION B: RUN BATCH
# ==============================================================================

st.subheader("▶️ Run Batch Experiments")

if st.button("🚀 Start Batch Processing", use_container_width=True, type="primary"):
    with st.spinner("Running batch experiments..."):
        # Initialize results storage
        batch_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Get template from session (use first available or default)
        template = st.session_state.get('selected_template', {
            'name': 'Default',
            'markets': ['Market_A', 'Market_B', 'Market_C', 'Market_D']
        })
        
        data_gen = StochasticSEOGenerator(seed=42)
        total_runs = num_experiments * len(effect_sizes) if effect_sizes else num_experiments
        run_count = 0
        
        # Generate market pairs
        available_markets = template.get('markets', [
            'Market_A', 'Market_B', 'Market_C', 'Market_D',
            'Market_E', 'Market_F', 'Market_G', 'Market_H'
        ])
        
        for exp_idx in range(num_experiments):
            # Pick unique markets for this experiment
            market_idx_1 = (exp_idx * 2) % len(available_markets)
            market_idx_2 = (exp_idx * 2 + 1) % len(available_markets)
            test_mkt = available_markets[market_idx_1]
            control_mkt = available_markets[market_idx_2]
            
            # Test each effect size
            effect_list = effect_sizes if effect_sizes else [5]
            
            for effect_pct in effect_list:
                run_count += 1
                status_text.text(f"Running experiment {run_count}/{total_runs}: {test_mkt} vs {control_mkt}, effect={effect_pct}%")
                
                try:
                    # Generate data with independent random seed
                    seed = int(datetime.now().timestamp() * 1000) % 100000 + run_count
                    data_gen = StochasticSEOGenerator(seed=seed)
                    
                    # Randomly select confounders
                    confounders = None
                    if include_confounders and np.random.rand() > 0.5:
                        confounder_list = ['algorithm_update', 'seasonality_spike', 'tracking_break']
                        confounders = [np.random.choice(confounder_list)]
                    
                    result = data_gen.generate_experiment_data(
                        test_market=test_mkt,
                        control_market=control_mkt,
                        pre_period_days=90,
                        post_period_days=experiment_duration,
                        mde_pct=effect_pct / 100,
                        effect_shape='step',
                        confounders=confounders
                    )
                    
                    data = result['data']
                    metadata = result['metadata']
                    
                    # Prep data
                    ci_data = data[['test_market', 'control_market']].copy()
                    ci_data.columns = ['y', 'X']
                    ci_data = ci_data.reset_index(drop=True)
                    post_start = 90

                    # Run CausalImpact
                    ci = CausalImpact(
                        ci_data,
                        pre_period=[0, post_start - 1],
                        post_period=[post_start, len(ci_data) - 1]
                    )
                    inferences = ci.inferences
                    predicted_post = inferences['preds'].iloc[post_start:].values

                    actual_post = ci_data['y'].iloc[post_start:].values
                    pointwise_effects = actual_post - predicted_post
                    point_est = np.nansum(pointwise_effects)
                    avg_daily = np.nanmean(pointwise_effects)
                    post_sum = actual_post.sum()
                    pct_effect = (point_est / post_sum * 100) if post_sum != 0 else 0

                    # Statistical test
                    effect_se = np.nanstd(pointwise_effects) / np.sqrt(len(pointwise_effects))
                    z_score = point_est / effect_se if effect_se > 0 else 0
                    p_value = 2 * (1 - np.exp(-abs(z_score) / np.sqrt(2 * np.pi)))
                    
                    batch_results.append({
                        'experiment_id': f"EXP_{exp_idx + 1}_{effect_pct}pct",
                        'test_market': test_mkt,
                        'control_market': control_mkt,
                        'planned_effect': effect_pct,
                        'estimated_effect': point_est,
                        'effect_pct': pct_effect,
                        'avg_daily': avg_daily,
                        'p_value': p_value,
                        'z_score': z_score,
                        'days': len(actual_post),
                        'pre_corr': metadata.get('control_correlation', 0.95),
                        'confounders': ', '.join(confounders) if confounders else 'None'
                    })
                    
                except Exception as e:
                    batch_results.append({
                        'experiment_id': f"EXP_{exp_idx + 1}_{effect_pct}pct",
                        'test_market': test_mkt,
                        'control_market': control_mkt,
                        'planned_effect': effect_pct,
                        'estimated_effect': np.nan,
                        'effect_pct': np.nan,
                        'avg_daily': np.nan,
                        'p_value': np.nan,
                        'z_score': np.nan,
                        'days': experiment_duration,
                        'pre_corr': np.nan,
                        'confounders': f'Error: {str(e)[:30]}'
                    })
                
                # Update progress
                progress_bar.progress(run_count / total_runs)
        
        status_text.text("✅ Batch processing complete!")
        
        # Store results in session
        st.session_state['batch_results'] = pd.DataFrame(batch_results)
        
        time.sleep(0.5)
        st.rerun()

st.markdown("---")

# ==============================================================================
# SECTION C: RESULTS TABLE
# ==============================================================================

if 'batch_results' in st.session_state:
    st.subheader("📊 Batch Results")
    
    results_df = st.session_state['batch_results'].copy()
    
    # Format for display
    display_df = results_df.copy()
    display_df['Estimated Effect'] = display_df['estimated_effect'].apply(lambda x: f"{x:+.0f}" if pd.notna(x) else "N/A")
    display_df['Effect %'] = display_df['effect_pct'].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "N/A")
    display_df['Avg Daily'] = display_df['avg_daily'].apply(lambda x: f"{x:+.0f}" if pd.notna(x) else "N/A")
    display_df['P-Value'] = display_df['p_value'].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "N/A")
    display_df['Z-Score'] = display_df['z_score'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    display_df['Pre-Corr'] = display_df['pre_corr'].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
    
    show_cols = [
        'experiment_id', 'test_market', 'control_market', 'planned_effect',
        'Estimated Effect', 'Effect %', 'P-Value', 'Pre-Corr', 'confounders'
    ]
    
    st.dataframe(display_df[show_cols], use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ==============================================================================
    # SECTION D: WINNER ANALYSIS
    # ==============================================================================
    
    st.subheader("🏆 Winner Analysis")
    
    # Identify winning experiments
    results_df['winner'] = (results_df['effect_pct'] > 2) & (results_df['p_value'] < 0.10)
    winners = results_df[results_df['winner']]
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Experiments",
            len(results_df),
            help="Total number of experiments run"
        )
    
    with col2:
        win_rate = (len(winners) / len(results_df) * 100) if len(results_df) > 0 else 0
        st.metric(
            "Win Rate",
            f"{win_rate:.0f}%",
            help="Percentage of experiments with effect > 2% and p < 0.10"
        )
    
    with col3:
        avg_effect = results_df['effect_pct'].mean()
        st.metric(
            "Avg Effect %",
            f"{avg_effect:+.1f}%",
            help="Average effect size across all experiments"
        )
    
    if len(winners) > 0:
        st.markdown("**Winning Experiments:**")
        winners_display = winners[show_cols].copy()
        winners_display['Estimated Effect'] = winners_display['estimated_effect'].apply(lambda x: f"{x:+.0f}")
        winners_display['Effect %'] = winners_display['effect_pct'].apply(lambda x: f"{x:+.1f}%")
        winners_display['P-Value'] = winners_display['p_value'].apply(lambda x: f"{x:.4f}")
        st.dataframe(winners_display[show_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("No winning experiments in this batch.")
    
    st.markdown("---")
    
    # ==============================================================================
    # SECTION E: BATCH STATISTICS
    # ==============================================================================
    
    st.subheader("📈 Batch Statistics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Effect Size Distribution**")
        
        valid_effects = results_df['effect_pct'].dropna()
        stats_data = {
            'Statistic': ['Min', 'Q1 (25%)', 'Median', 'Q3 (75%)', 'Max', 'Mean', 'Std Dev'],
            'Value': [
                f"{valid_effects.min():+.1f}%",
                f"{valid_effects.quantile(0.25):+.1f}%",
                f"{valid_effects.median():+.1f}%",
                f"{valid_effects.quantile(0.75):+.1f}%",
                f"{valid_effects.max():+.1f}%",
                f"{valid_effects.mean():+.1f}%",
                f"{valid_effects.std():+.1f}%"
            ]
        }
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True, hide_index=True)
    
    with col2:
        st.markdown("**Statistical Significance Distribution**")
        
        sig_levels = {
            'p < 0.05 (Very Sig.)': len(results_df[results_df['p_value'] < 0.05]),
            'p < 0.10 (Sig.)': len(results_df[(results_df['p_value'] >= 0.05) & (results_df['p_value'] < 0.10)]),
            'p >= 0.10 (Not Sig.)': len(results_df[results_df['p_value'] >= 0.10]),
            'N/A (Error)': len(results_df[results_df['p_value'].isna()])
        }
        
        sig_df = pd.DataFrame({
            'Significance Level': list(sig_levels.keys()),
            'Count': list(sig_levels.values())
        })
        st.dataframe(sig_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ==============================================================================
    # SECTION F: DOWNLOAD RESULTS
    # ==============================================================================
    
    st.subheader("💾 Export Results")
    
    # Prepare CSV
    csv_buffer = results_df.to_csv(index=False)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 Download CSV",
            data=csv_buffer,
            file_name=f"Batch_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        if st.button("🗑️ Clear Results", use_container_width=True):
            del st.session_state['batch_results']
            st.rerun()

st.markdown("---")

# ==============================================================================
# NAVIGATION
# ==============================================================================

col1, col2 = st.columns(2)

with col1:
    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("Home.py")
