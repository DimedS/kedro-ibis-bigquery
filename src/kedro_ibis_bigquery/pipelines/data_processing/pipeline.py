"""
This is a boilerplate pipeline 'data_processing'
generated using Kedro 0.19.5
"""

from kedro.pipeline import Pipeline, pipeline, node

from .nodes import data_processing

def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([
            node(
                func=data_processing,
                inputs=["international_top_terms", "international_top_rising_terms"],
                outputs="preprocessed_data",
                name="preprocess_data",
            ),
    ])
