import streamlit as st


def main():
    st.set_page_config(page_title="SEO Causal Engine", layout="wide", initial_sidebar_state="expanded")
    
    # Custom CSS
    st.markdown("""
    <style>
        .main-header {
            font-size: 3rem;
            font-weight: bold;
            color: #1f77b4;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            font-size: 1.3rem;
            color: #555;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        # 🔬 SEO Causal Engine
        ### Incrementality Testing Platform
        """)
    
    with col2:
        st.image("https://via.placeholder.com/150", width=150)
    
    st.markdown("---")
    
    # Introduction
    st.markdown("""
    ## Welcome to the SEO Causal Testing Simulator
    
    A simulation platform for designing, executing, and validating SEO incrementality tests
    using **synthetic control**, **matched markets**, and **causal inference** methodologies.
    
    ### What You Can Do
    
    - **🎯 Design experiments** using SEO-proven templates or custom hypotheses
    - **📊 Calculate sample sizes** with dynamic power analysis
    - **⚡ Run simulations** with realistic stochastic data generation
    - **📈 Analyze results** using CausalImpact and validity diagnostics
    - **🚀 Batch test** multiple initiatives simultaneously
    - **📋 Export reports** for stakeholder communication
    
    ---
    
    ## How It Works (5 Steps)
    
    """)
    
    # Step overview
    steps = [
        ("1️⃣", "Choose Template", "Select an SEO template or define custom hypothesis"),
        ("2️⃣", "Design Experiment", "Pick markets, method, and calculate required duration"),
        ("3️⃣", "Run Simulation", "Generate synthetic data with optional confounders"),
        ("4️⃣", "Analyze Results", "Apply CausalImpact and validity checks"),
        ("5️⃣", "Get Recommendations", "Receive decision framework and export report")
    ]
    
    for emoji, title, desc in steps:
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            st.markdown(emoji)
        with col2:
            st.markdown(f"**{title}:** {desc}")
    
    st.markdown("---")
    
    # Key Features
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        ### 🏆 Synthetic Control
        
        Ridge Regression-based weighted controls that minimize pre-period RMSE.
        """)
    
    with col2:
        st.success("""
        ### 📐 Power Analysis
        
        Automated sample size calculation based on alpha, beta, and MDE.
        """)
    
    with col3:
        st.warning("""
        ### 🔍 Validity Checks
        
        Traffic-light diagnostics: pre-trend similarity, placebo tests, sensitivity.
        """)
    
    st.markdown("---")
    
    # Getting Started
    st.subheader("🚀 Get Started")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button(
            "Start New Experiment",
            key="btn_new_exp",
            use_container_width=True,
            type="primary"
        ):
            st.switch_page("pages/1_📋_SEO_Template.py")
    
    with col2:
        if st.button(
            "View Experiment History",
            key="btn_history",
            use_container_width=True
        ):
            st.info("History feature coming soon!")
    
    with col3:
        if st.button(
            "Learn More",
            key="btn_learn",
            use_container_width=True
        ):
            st.info("Documentation coming soon!")
    
    st.markdown("---")
    
    # Footer
    st.markdown("""
    <div style="text-align: center; color: #999; margin-top: 2rem;">
        <p><strong>SEO Causal Engine v1.0</strong> | Built with Streamlit + CausalImpact</p>
        <p>Demonstrates causal inference expertise for SEO incrementality testing</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
