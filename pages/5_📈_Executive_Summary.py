import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

st.set_page_config(page_title="Executive Summary", layout="wide")

# Check if we have causal impact results
if 'causal_impact' not in st.session_state or 'simulation_data' not in st.session_state:
    st.error("No causal analysis results found. Please complete the analysis first.")
    if st.button("← Go Back to Analysis"):
        st.switch_page("pages/4_📊_Causal_Analysis.py")
    st.stop()

st.title("📈 Executive Summary")

# ==============================================================================
# RETRIEVE DATA FROM SESSION STATE
# ==============================================================================

ci = st.session_state['causal_impact']
data = st.session_state['simulation_data']
metadata = st.session_state['simulation_metadata']
template = st.session_state['selected_template']
test_market = st.session_state['test_market']
control_market = st.session_state['control_market']
use_synthetic = st.session_state.get('synthetic_weights') is not None
control_label = "Synthetic Control" if use_synthetic else control_market

# Extract metrics from CausalImpact
inferences = ci.inferences
post_start = 90
actual_post = data[data['period'] == 'post']['test_market'].values
predicted_post = inferences['preds'].iloc[post_start:].values
pointwise_effects = actual_post - predicted_post
point_est = np.nansum(pointwise_effects)
avg_daily_effect = np.nanmean(pointwise_effects)
post_mean = np.nanmean(actual_post)
post_sum = np.nansum(actual_post)  # FIXED: Use nansum to ignore nan values
pct_effect = (point_est / post_sum * 100) if post_sum != 0 else 0

# Statistical significance
pre_data = data[data['period'] == 'pre']
post_data = data[data['period'] == 'post']
pre_mean = data['test_market'].iloc[:90].mean()
effect_se = np.nanstd(pointwise_effects) / np.sqrt(len(pointwise_effects))
z_score = point_est / effect_se if effect_se > 0 else 0
# FIXED: Use proper normal CDF for p-value calculation
p_value = 2 * (1 - norm.cdf(abs(z_score)))

# Lightweight BI assumptions to show business-facing KPIs
assumed_conv_rate = 0.03  # 3% conversion rate
assumed_aov = 60  # $60 average order value
assumed_rps = assumed_conv_rate * assumed_aov

pre_sessions = pre_data['test_market'].sum()
post_sessions = post_sum

inc_sessions = np.nan_to_num(point_est, nan=0.0)
post_conversions = post_sessions * assumed_conv_rate
post_revenue = post_conversions * assumed_aov
inc_conversions = inc_sessions * assumed_conv_rate
inc_revenue = inc_conversions * assumed_aov

# Simple guardrail placeholder (bounce rate moves mildly with effect)
bounce_rate_pre = 0.45
bounce_rate_post = np.clip(bounce_rate_pre - (pct_effect / 100) * 0.10, 0.20, 0.80)

st.markdown(f"**Template:** {template['name']} | **Test:** {test_market} | **Control:** {control_label}")
st.markdown("---")

# Simple reader guide so non-analysts know what each block means
st.info(
    """
    **How to read this page (plain English):**
    - **Estimated Effect**: Total extra (or lost) sessions the change caused vs. what would have happened without it.
    - **Avg Daily Impact**: The effect per day; handy for thinking about daily run-rate.
    - **Statistical Sig. (z, p)**: Whether the lift is likely real vs. noise; smaller p is stronger evidence.
    - **Recommendation**: Quick go/no-go based on size of lift and p-value; negative + significant = don't ship.
    - **BI Snapshot**: Storytelling dollars from the lift using simple assumptions (3% CVR, $60 AOV); not finance-grade.
    - **Validity Checks**: Trust meter—if pre-period match is weak or RMSE is high, treat the result with caution.
    """
)

# ==============================================================================
# SECTION A: KEY METRICS SUMMARY
# ==============================================================================

st.subheader("📊 Key Results Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Estimated Effect",
        f"{point_est:+.0f}",
        f"{pct_effect:+.1f}%",
        help="Cumulative causal effect (units + percentage of post-period actuals)"
    )

with col2:
    st.metric(
        "Avg Daily Impact",
        f"{avg_daily_effect:+.0f}",
        f"{(avg_daily_effect/post_mean*100):+.1f}%",
        help="Average daily causal effect"
    )

with col3:
    st.metric(
        "Statistical Sig.",
        f"z={z_score:.2f}",
        f"p={p_value:.3f}",
        help="Z-score and p-value (2-sided)"
    )

with col4:
    # Decision based on effect size and significance
    # IMPORTANT: Negative effects that are significant should be "Don't Ship" (harmful)
    if pct_effect < 0 and p_value < 0.10:
        decision = "❌ Don't Ship"
        color = "red"
    elif pct_effect > 5 and p_value < 0.05:
        decision = "✅ Ship"
        color = "green"
    elif pct_effect > 2 and p_value < 0.10:
        decision = "🔄 Continue"
        color = "blue"
    else:
        decision = "❌ Don't Ship"
        color = "red"
    
    st.metric(
        "Recommendation",
        decision,
        help="Based on effect size and statistical significance"
    )

st.markdown("---")

# ==============================================================================
# DEBUG: SHOW DECISION LOGIC VALUES
# ==============================================================================

with st.expander("🔍 Debug: Decision Logic Breakdown", expanded=False):
    st.markdown("### Why did we get this recommendation?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Current Values:**")
        st.write(f"- Effect %: **{pct_effect:.2f}%** (abs: {abs(pct_effect):.2f}%)")
        st.write(f"- P-Value: **{p_value:.6f}**")
        st.write(f"- Z-Score: **{z_score:.2f}**")
        st.write(f"- Effect (sessions): **{point_est:+.0f}**")
        st.write(f"- Standard Error: **{effect_se:.2f}**")
    
    with col2:
        st.markdown("**Decision Thresholds:**")
        
        # Check if negative effect first
        if pct_effect < 0:
            st.write("**⚠️ Negative Effect Detected:**")
            st.write(f"  - Effect is negative? {pct_effect < 0} (yours: {pct_effect:.2f}%)")
            st.write(f"  - P-Value < 0.10? {p_value < 0.10} (yours: {p_value:.6f})")
            st.write("  → **Significant negative effect = Don't Ship**")
        else:
            st.write("**✅ Ship** requires:")
            st.write(f"  - Effect % > 5%? {pct_effect > 5} (yours: {pct_effect:.2f}%)")
            st.write(f"  - P-Value < 0.05? {p_value < 0.05} (yours: {p_value:.6f})")
            st.write("")
            st.write("**🔄 Continue** requires:")
            st.write(f"  - Effect % > 2%? {pct_effect > 2} (yours: {pct_effect:.2f}%)")
            st.write(f"  - P-Value < 0.10? {p_value < 0.10} (yours: {p_value:.6f})")
    
    st.markdown("---")
    st.markdown(f"**Final Decision: {decision}**")
    
    if decision == "❌ Don't Ship":
        if pct_effect < 0 and p_value < 0.10:
            st.error(f"""
            **Why "Don't Ship"? NEGATIVE IMPACT!**
            
            Your experiment shows a **statistically significant negative effect**:
            - Effect: **{pct_effect:.2f}%** (decrease in sessions)
            - P-value: **{p_value:.6f}** (highly significant)
            
            **This change is actively harming performance!**
            - The test is causing a measurable drop in traffic/conversions
            - The negative effect is statistically significant
            - Rolling this out would hurt your business
            
            **Recommendation:** Immediately stop the test and revert changes.
            """)
        else:
            st.warning(f"""
            **Why "Don't Ship"?**
            
            Your experiment didn't meet the minimum thresholds:
            - Either your effect size is too small (< 2%)
            - Or your p-value is too high (≥ 0.10)
            - This means there isn't enough statistical evidence or business impact to justify shipping.
            
            **What to do:**
            - If effect is very small: The change might not be worth implementing
            - If p-value is high: Try running the test longer for more data
            - Check the validity diagnostics on Page 4 for data quality issues
            """)
    elif decision == "🔄 Continue":
        st.info(f"""
        **Why "Continue"?**
        
        Your experiment shows promising results but needs more validation:
        - Effect: {abs(pct_effect):.2f}% (between 2-5%)
        - P-value: {p_value:.4f} (between 0.05-0.10)
        
        **Recommendation:** Run the test longer or expand to more markets for confirmation.
        """)
    else:
        st.success(f"""
        **Why "Ship"?**
        
        Your experiment meets both criteria:
        - Effect: {abs(pct_effect):.2f}% (> 5%) ✓
        - P-value: {p_value:.4f} (< 0.05) ✓
        
        **This is a clear winner!** Safe to implement.
        """)

st.markdown("---")


st.subheader("📊 BI Snapshot (Mock Assumptions)")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Post-Period Revenue",
        f"${post_revenue:,.0f}",
        f"${inc_revenue:,.0f} vs. counterfactual",
        help="Assumes 3% conv. rate and $60 AOV"
    )

with col2:
    st.metric(
        "Post Conversions",
        f"{post_conversions:,.0f}",
        f"{inc_conversions:,.0f} vs. counterfactual",
        help="Conversions derived from sessions with assumed 3% rate"
    )

with col3:
    st.metric(
        "Revenue / Session",
        f"${assumed_rps:.2f}",
        f"{pct_effect:+.1f}% lift proxy",
        help="RPS is assumption-driven for BI storytelling"
    )

st.caption("Note: These KPIs are mock conversions/revenue for BI storytelling. Assumptions: 3% CVR, $60 AOV.")

guardrail_df = pd.DataFrame({
    'Metric': ['Sessions (Post)', 'Incremental Sessions', 'Bounce Rate (Pre)', 'Bounce Rate (Post)'],
    'Value': [
        f"{post_sessions:,.0f}",
        f"{inc_sessions:+,.0f}",
        f"{bounce_rate_pre*100:.1f}%",
        f"{bounce_rate_post*100:.1f}%"
    ]
})

st.dataframe(guardrail_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ==============================================================================
# SECTION B: DETAILED METRICS TABLE
# ==============================================================================

st.subheader("📋 Detailed Metrics")

metrics_table = pd.DataFrame({
    'Metric': [
        'Pre-Period Mean (Test)',
        'Post-Period Mean (Test)',
        'Absolute Lift',
        'Relative Lift %',
        'Post-Period Total (Test)',
        'Post-Period Total (Predicted)',
        'Estimated Effect',
        'Effect %',
        'Avg Daily Effect',
        'Daily Effect %',
        'Post-Period Days',
        'P-Value (2-sided)',
        'Z-Score',
        'Effect Std Dev'
    ],
    'Value': [
        f"{pre_mean:.0f}",
        f"{post_mean:.0f}",
        f"{(post_mean - pre_mean):+.0f}",
                f"{((post_mean - pre_mean) / pre_mean * 100):+.1f}%",
                f"{post_sum:.0f}",
                f"{predicted_post.sum():.0f}",
                f"{point_est:+.0f}",
                f"{pct_effect:+.1f}%",
                f"{avg_daily_effect:+.0f}",
                f"{(avg_daily_effect / post_mean * 100):+.1f}%",
                f"{len(actual_post)}",
                f"{p_value:.4f}",
                f"{z_score:.4f}",
                f"{np.nanstd(pointwise_effects):.0f}"
            ]
})

st.dataframe(metrics_table, use_container_width=True, hide_index=True)

st.markdown("---")

# ==============================================================================
# SECTION C: DECISION FRAMEWORK
# ==============================================================================

st.subheader("🎯 Decision Framework")

st.markdown("""
| Scenario | Condition | Recommendation | Action |
|----------|-----------|-----------------|--------|
| **Strong Win** | Effect > 5% AND p < 0.05 | ✅ Ship | Implement change immediately |
| **Likely Win** | Effect > 2% AND p < 0.10 | 🔄 Continue Testing | Run longer or expand to more markets |
| **Inconclusive** | Effect 0-2% OR p ≥ 0.10 | 🤔 Investigate | Check for confounders or data quality |
| **Loss/Harm** | Effect < 0% AND p < 0.10 | ❌ Don't Ship | Revert and investigate causes |
""")

st.markdown("---")

# ==============================================================================
# SECTION D: BUSINESS IMPACT PROJECTION
# ==============================================================================

st.subheader("💰 Business Impact Projection")

st.markdown(f"""
**Assuming company-wide rollout:**

- **Current Daily Traffic:** ~{pre_mean:,.0f} sessions/day (est. from test market)
- **Estimated Daily Lift:** {avg_daily_effect:+,.0f} sessions ({(avg_daily_effect/post_mean*100):+.1f}%)
- **Monthly Impact (30 days):** {avg_daily_effect * 30:+,.0f} additional sessions
- **Annual Impact (365 days):** {avg_daily_effect * 365:+,.0f} additional sessions

**Typical Monetization Scenarios:**
- @ $2/session: ${avg_daily_effect * 365 * 2:+,.0f}/year
- @ $5/session: ${avg_daily_effect * 365 * 5:+,.0f}/year
- @ $10/session: ${avg_daily_effect * 365 * 10:+,.0f}/year
""")

st.markdown("---")

# ==============================================================================
# SECTION E: VALIDITY ASSESSMENT
# ==============================================================================

st.subheader("✓ Validity Checks")

# From the causal analysis results
pre_corr = metadata.get('control_correlation', 0.95)
pre_diff = abs((pre_data['test_market'].mean() - pre_data['control_market'].mean())) / pre_data['control_market'].mean()

col1, col2, col3 = st.columns(3)

with col1:
    if pre_corr > 0.90:
        st.success(f"✓ Pre-Period Correlation: {pre_corr:.3f} (Strong match)")
    elif pre_corr > 0.80:
        st.warning(f"⚠ Pre-Period Correlation: {pre_corr:.3f} (Adequate)")
    else:
        st.error(f"✗ Pre-Period Correlation: {pre_corr:.3f} (Weak match)")

with col2:
    if pre_diff < 0.05:
        st.success(f"✓ Pre-Period Diff: {pre_diff*100:.1f}% (Well-matched)")
    elif pre_diff < 0.10:
        st.warning(f"⚠ Pre-Period Diff: {pre_diff*100:.1f}% (Moderate)")
    else:
        st.error(f"✗ Pre-Period Diff: {pre_diff*100:.1f}% (Divergent)")

with col3:
    # Calculate RMSE of pre-period predictions
    pre_predict = inferences['preds'].iloc[:90].mean()
    pre_actual = data['test_market'].iloc[:90].mean()
    rmse_pct = abs(pre_predict - pre_actual) / pre_actual * 100
    
    if rmse_pct < 5:
        st.success(f"✓ Pre-Period RMSE: {rmse_pct:.1f}% (Accurate)")
    elif rmse_pct < 10:
        st.warning(f"⚠ Pre-Period RMSE: {rmse_pct:.1f}% (Fair)")
    else:
        st.error(f"✗ Pre-Period RMSE: {rmse_pct:.1f}% (Poor)")

st.markdown("---")

# ==============================================================================
# SECTION F: PDF EXPORT
# ==============================================================================

st.subheader("📄 Export Report")

def generate_pdf():
    """Generate a PDF report of the executive summary."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    elements = []
    
    # Title
    elements.append(Paragraph("SEO Causal Test Executive Summary", title_style))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", heading_style))
    summary_text = f"""
    This report documents the causal impact analysis of the {template['name']} experiment conducted on 
    the {test_market} market against the {control_label} control market over a {len(actual_post)}-day period.
    <br/><br/>
    <b>Key Finding:</b> The intervention resulted in an estimated <b>{point_est:+.0f}</b> sessions 
    ({pct_effect:+.1f}%) with a statistical significance of p={p_value:.4f}. 
    The recommendation is: <b>{decision}</b>
    """
    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    # Key Metrics Table
    elements.append(Paragraph("Key Results", heading_style))
    key_metrics_data = [
        ['Metric', 'Value'],
        ['Estimated Effect', f"{point_est:+.0f} sessions ({pct_effect:+.1f}%)"],
        ['Avg Daily Impact', f"{avg_daily_effect:+.0f} sessions ({(avg_daily_effect/post_mean*100):+.1f}%)"],
        ['P-Value', f"{p_value:.4f}"],
        ['Z-Score', f"{z_score:.2f}"],
        ['Post-Period Days', f"{len(actual_post)}"],
        ['Recommendation', decision]
    ]
    
    key_table = Table(key_metrics_data, colWidths=[3*inch, 3*inch])
    key_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(key_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Generate and offer download
if st.button("📥 Download PDF Report", use_container_width=True, type="primary"):
    pdf_buffer = generate_pdf()
    st.download_button(
        label="💾 Save PDF",
        data=pdf_buffer,
        file_name=f"Executive_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

st.markdown("---")

# ==============================================================================
# NAVIGATION
# ==============================================================================

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Analysis", use_container_width=True):
        st.switch_page("pages/4_📊_Causal_Analysis.py")

with col3:
    st.button("Forward to Batch Runner →", use_container_width=True, disabled=True, help="Batch Runner is currently unavailable")
