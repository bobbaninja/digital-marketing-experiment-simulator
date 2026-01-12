import streamlit as st
import yaml
import os


def load_templates():
    """Load SEO templates from config."""
    config_path = 'config/seo_templates.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config['templates']


def render_template_card(template: dict, col):
    """Render a single template card."""
    with col:
        with st.container(border=True):
            st.subheader(f"🎯 {template['name']}")
            st.write(template['description'])
            st.markdown("---")
            
            # Key metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Primary Metric", template['primary_metric'])
            with col2:
                st.metric("Typical MDE", f"{template['default_mde']}%")
            
            # Common confounders
            st.write("**Common Confounders:**")
            for confounder in template['common_confounders']:
                st.write(f"• {confounder}")
            
            # Select button
            if st.button(f"Select {template['name']}", key=f"btn_{template['id']}", use_container_width=True):
                st.session_state['selected_template'] = template
                st.session_state['page_state'] = 'template_selected'
                st.rerun()


def main():
    st.set_page_config(page_title="SEO Causal Engine", layout="wide")
    
    # Initialize session state
    if 'selected_template' not in st.session_state:
        st.session_state['selected_template'] = None
    if 'page_state' not in st.session_state:
        st.session_state['page_state'] = 'template_selection'
    
    st.title("📋 SEO Template Selector")
    st.markdown("""
    **Step 1: Choose an SEO Initiative**
    
    Select from proven SEO optimization templates, or create a custom hypothesis.
    Each template includes recommended metrics, effect size ranges, and common confounders.
    """)
    
    # State 1: Template Selection
    if st.session_state['page_state'] == 'template_selection':
        templates = load_templates()
        
        # Template grid (2 columns)
        cols = st.columns(2)
        for idx, template in enumerate(templates):
            col = cols[idx % 2]
            render_template_card(template, col)
        
        st.markdown("---")
        
        # Advanced: Custom Hypothesis
        with st.expander("🔧 Advanced: Custom Hypothesis", expanded=False):
            st.write("""
            For advanced users: define a custom hypothesis without a template.
            This requires manually specifying the metric, target, and MDE.
            """)
            
            custom_metric = st.text_input("Custom Primary Metric", placeholder="e.g., 'Custom KPI'")
            custom_mde = st.slider("Custom MDE (%)", 1, 50, 10)
            
            if st.button("Create Custom Hypothesis", use_container_width=True):
                custom_template = {
                    'id': 99,
                    'name': 'Custom Hypothesis',
                    'description': f'Custom metric: {custom_metric}',
                    'primary_metric': custom_metric,
                    'default_mde': custom_mde,
                    'recommended_method': 'synthetic_control',
                    'common_confounders': []
                }
                st.session_state['selected_template'] = custom_template
                st.session_state['page_state'] = 'template_selected'
                st.rerun()
    
    # State 2: Template Selected (confirmation)
    elif st.session_state['page_state'] == 'template_selected':
        template = st.session_state['selected_template']
        
        st.success(f"✅ Template Selected: **{template['name']}**")
        st.markdown(f"""
        **Primary Metric:** {template['primary_metric']}
        
        **Typical MDE Range:** {template.get('mde_min', 5)}-{template.get('mde_max', 20)}%
        
        **Recommended Method:** {template['recommended_method']}
        
        **Description:** {template['description']}
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back to Templates", use_container_width=True):
                st.session_state['page_state'] = 'template_selection'
                st.rerun()
        
        with col2:
            if st.button("Next: Experiment Design →", use_container_width=True):
                st.switch_page("pages/2_🎯_Experiment_Design.py")


if __name__ == "__main__":
    main()
