import duckdb
import pandas as pd
import os
from datetime import datetime


class DuckDBManager:
    """
    Manages DuckDB connection and schema for SEO experiment storage.
    """
    
    def __init__(self, db_path: str = 'data/simulation.duckdb'):
        """
        Initialize DuckDB manager.
        
        Args:
            db_path: Path to DuckDB file
        """
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = duckdb.connect(db_path)
    
    def initialize_schema(self):
        """Create all necessary tables if they don't exist."""
        
        # Experiments table - tracks all runs
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                run_id VARCHAR PRIMARY KEY,
                template_name VARCHAR,
                test_market VARCHAR,
                control_market VARCHAR,
                intervention_day INTEGER,
                pre_period_days INTEGER,
                post_period_days INTEGER,
                mde_requested DOUBLE,
                mde_applied DOUBLE,
                effect_shape VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR DEFAULT 'completed'
            )
        """)
        
        # Experiment metrics - daily metrics from simulation
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS experiment_metrics (
                run_id VARCHAR,
                date DATE,
                test_value DOUBLE,
                control_value DOUBLE,
                period VARCHAR,
                day_num INTEGER,
                FOREIGN KEY(run_id) REFERENCES experiments(run_id)
            )
        """)
        
        # CausalImpact results
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS causal_results (
                run_id VARCHAR PRIMARY KEY,
                point_estimate DOUBLE,
                ci_lower DOUBLE,
                ci_upper DOUBLE,
                cumulative_effect DOUBLE,
                probability_causal_effect DOUBLE,
                pre_trend_similarity DOUBLE,
                placebo_score DOUBLE,
                sensitivity_score DOUBLE,
                FOREIGN KEY(run_id) REFERENCES experiments(run_id)
            )
        """)
        
        # Batch results - for batch runner
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS batch_results (
                batch_id VARCHAR,
                run_id VARCHAR,
                template_name VARCHAR,
                est_lift DOUBLE,
                confidence DOUBLE,
                risk_score DOUBLE,
                priority_score DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Validity checks - diagnostic flags
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS validity_checks (
                run_id VARCHAR,
                check_name VARCHAR,
                status VARCHAR,
                value DOUBLE,
                threshold_green DOUBLE,
                threshold_yellow DOUBLE,
                explanation VARCHAR,
                FOREIGN KEY(run_id) REFERENCES experiments(run_id)
            )
        """)
    
    def save_experiment(self, run_id: str, experiment_data: dict, metrics_df: pd.DataFrame):
        """
        Save experiment run to database.
        
        Args:
            run_id: Unique experiment ID
            experiment_data: Dict with template_name, markets, parameters
            metrics_df: DataFrame with daily metrics
        """
        # Insert into experiments
        self.conn.execute(f"""
            INSERT INTO experiments 
            (run_id, template_name, test_market, control_market, 
             intervention_day, pre_period_days, post_period_days,
             mde_requested, mde_applied, effect_shape)
            VALUES 
            ('{run_id}', '{experiment_data['template_name']}', 
             '{experiment_data['test_market']}', '{experiment_data['control_market']}',
             {experiment_data['intervention_day']}, {experiment_data['pre_period_days']},
             {experiment_data['post_period_days']}, {experiment_data['mde_requested']},
             {experiment_data['mde_applied']}, '{experiment_data['effect_shape']}')
        """)
        
        # Insert metrics
        metrics_df['run_id'] = run_id
        self.conn.register('metrics_temp', metrics_df)
        self.conn.execute("""
            INSERT INTO experiment_metrics 
            SELECT run_id, date, test_value, control_value, period, day_num FROM metrics_temp
        """)
    
    def save_causal_results(self, run_id: str, results: dict):
        """Save CausalImpact results."""
        self.conn.execute(f"""
            INSERT INTO causal_results
            (run_id, point_estimate, ci_lower, ci_upper, cumulative_effect,
             probability_causal_effect, pre_trend_similarity, placebo_score, sensitivity_score)
            VALUES
            ({results['point_estimate']}, {results['ci_lower']}, {results['ci_upper']},
             {results['cumulative_effect']}, {results['probability_causal_effect']},
             {results['pre_trend_similarity']}, {results['placebo_score']},
             {results['sensitivity_score']})
        """)
    
    def query_experiment_history(self, limit: int = 10) -> pd.DataFrame:
        """Get recent experiment history."""
        return self.conn.execute(f"""
            SELECT 
                run_id,
                template_name,
                test_market,
                control_market,
                mde_applied,
                created_at
            FROM experiments
            ORDER BY created_at DESC
            LIMIT {limit}
        """).df()
    
    def save_simulation_run(self, run_id: str, metadata: dict, metrics_df: pd.DataFrame):
        """
        Save complete simulation run to DuckDB.
        
        Args:
            run_id: Unique experiment ID
            metadata: Dict with experiment parameters
            metrics_df: DataFrame with daily metrics
        """
        # Insert experiment metadata
        self.conn.execute(f"""
            INSERT INTO experiments 
            (run_id, template_name, test_market, control_market, 
             intervention_day, pre_period_days, post_period_days,
             mde_requested, mde_applied, effect_shape, status)
            VALUES 
            ('{run_id}', 
             '{metadata.get('template_name', 'Unknown')}', 
             '{metadata.get('test_market', 'Unknown')}', 
             '{metadata.get('control_market', 'Unknown')}',
             {metadata.get('intervention_day', 90)}, 
             {metadata.get('pre_period_days', 90)},
             {metadata.get('post_period_days', 42)}, 
             {metadata.get('mde_requested', 0.08)},
             {metadata.get('mde_applied', 0.08)}, 
             '{metadata.get('effect_shape', 'step')}',
             'completed')
        """)
        
        # Insert metrics
        metrics_df_copy = metrics_df.copy()
        metrics_df_copy['run_id'] = run_id
        self.conn.register('metrics_temp', metrics_df_copy)
        self.conn.execute("""
            INSERT INTO experiment_metrics 
            SELECT run_id, date, test_market_metric as test_value, 
                   control_market_metric as control_value, period, day_num 
            FROM metrics_temp
        """)
    
    def query_experiment_data(self, run_id: str) -> pd.DataFrame:
        """
        Retrieve experiment metrics by run_id.
        
        Args:
            run_id: Unique experiment ID
        
        Returns:
            DataFrame with experiment metrics
        """
        return self.conn.execute(f"""
            SELECT 
                em.date,
                em.test_value,
                em.control_value,
                em.period,
                em.day_num,
                e.template_name,
                e.test_market,
                e.control_market
            FROM experiment_metrics em
            JOIN experiments e ON em.run_id = e.run_id
            WHERE em.run_id = '{run_id}'
            ORDER BY em.date
        """).df()
    
    def close(self):
        """Close database connection."""
        self.conn.close()
