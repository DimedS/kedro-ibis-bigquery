# Streamlining SQL Data Processing in Kedro ML Pipelines with Ibis and Google BigQuery

In this post, I'd like to share how I'm using Kedro to manage Machine Learning (ML) pipelines while efficiently storing and executing SQL queries within my Python Kedro project. By integrating Ibis and IbisDataset, I'm able to keep all my SQL code within the Kedro project and execute it on the database side, specifically using Google BigQuery.

## The Challenge

When managing ML pipelines, especially with large datasets stored on Google BigQuery or other databases, it's crucial to have an efficient and scalable way to preprocess data before training your models. Often, the best approach is to perform preprocessing on a database engine using Structured Query Language (SQL). A common challenge in this process is deciding where to store and execute SQL queries. Traditionally, there are two options:
1. **Store SQL queries in the database**: This involves creating views or stored procedures. While this keeps the execution close to the data, it splits your pipeline code across different platforms.
2. **Store SQL queries in your project**: This centralizes all code within your project repository (e.g., Git), but requires a way to execute these queries on the database.

## The Solution: Kedro, Ibis, and IbisDataset

### Kedro

[Kedro](https://kedro.org/) is a platform-agnostic open-source Python framework for creating reproducible, maintainable, and modular data science code. It helps in managing the entire lifecycle of your ML projects, from data ingestion to model training and deployment.

### Ibis and IbisDataset

[Ibis](https://ibis-project.org/) is a Python library that provides a pandas-like interface for interacting with SQL-based databases. It allows you to write expressive queries using Python syntax and execute them on the database side, leveraging the performance and scalability of the database.

[IbisDataset](https://github.com/kedro-org/kedro-plugins/tree/main/kedro-datasets/kedro_datasets/ibis) is an integration of Ibis within Kedro that allows you to use Ibis expressions as part of your Kedro pipelines. This means you can define your SQL logic within your Kedro project and execute it on databases like Google BigQuery.

### Implementation Steps

Here's how I implemented this solution in my Kedro project using Google Trends data from Google public datasets:

1. I logged into my Google Cloud account and navigated to the BigQuery service, where I wanted to use data stored in two public tables: `bigquery-public-data.google_trends.international_top_terms` (containing the history of trend rankings) and `bigquery-public-data.google_trends.international_top_rising_terms` (containing additional information about rising trends). Both tables are quite large, with around 200 million rows each. I aim to use this data to build a model to predict future trends. However, before training the model, I decided to preprocess the data with several common steps: grouping with aggregates, filtering, transforming, and merging datasets. I wrote an SQL query to accomplish this::
```sql
SELECT 
  trends.country_name, 
  trends.month, 
  trends.term AS google_trend, 
  count_per_month, 
  avg_score, 
  avg_percent_gain
FROM (
  SELECT 
    country_name, 
    FORMAT_DATE('%Y-%m', week) AS month, 
    term, 
    COUNT(*) AS count_per_month, 
    AVG(score) AS avg_score  
  FROM 
    `bigquery-public-data.google_trends.international_top_terms` 
  WHERE 
    score IS NOT NULL
  GROUP BY 
    country_name, month, term
) AS trends
LEFT JOIN (
  SELECT 
    country_name, 
    FORMAT_DATE('%Y-%m', week) AS month, 
    term, 
    AVG(percent_gain) AS avg_percent_gain 
  FROM 
    `bigquery-public-data.google_trends.international_top_rising_terms` 
  GROUP BY 
    country_name, month, term
) AS rising_trends 
ON 
  trends.month = rising_trends.month 
  AND trends.term = rising_trends.term 
  AND trends.country_name = rising_trends.country_name
```
2. I could store that SQL query as a database view and use the view name in my Kedro Python project to access the preprocessed data. This approach allows you to preprocess data on the database engine, but it has a few drawbacks: you need permissions to create database objects, and you can't control the future of that view—meaning no version control with Git, and someone could change or accidentally remove it. Therefore, I decided to use Ibis and IbisDataset to replicate the same SQL query within my Kedro project.
3. I opened my Python code IDE and created a new Kedro project, along with installing the required packages:
```
pip install kedro
pip install ibis-framework[bigquery]
kedro new
```
I named my project `kedro-ibis-bigquery`, answered all the other questions with the default options, and received a `kedro-ibis-bigquery` folder containing an empty Kedro project.

4. I created a new empty Kedro pipeline using the following command:
```
kedro pipeline create data_processing
```
5. Then I navigated to folder `kedro-ibis-bigquery` and edited a few files:
#### `/conf/base/catalog.yml`
This is the Kedro Data Catalog where I need to set all my Dataset descriptions. I'm describing two BigQuery tables with the type `ibis.TableDataset` and connection backend specification. The `project_id: aesthetic-site-421415` is the name of my personal Google Cloud Project (where query execution will be performed), and `dataset_id` is the database and schema name.
```yaml
international_top_terms:
  type: ibis.TableDataset
  table_name: international_top_terms
  connection:
    backend: bigquery
    project_id: aesthetic-site-421415
    dataset_id: bigquery-public-data.google_trends

international_top_rising_terms:
  type: ibis.TableDataset
  table_name: international_top_rising_terms
  connection:
    backend: bigquery
    project_id: aesthetic-site-421415
    dataset_id: bigquery-public-data.google_trends

preprocessed_data:
  type: pandas.CSVDataset
  filepath: data/02_intermediate/preprocessed_data.csv
```
I want the preprocessed data to be stored in my local file system in CSV format, rather than being returned to the database. Therefore, I'm using `pandas.CSVDataset` for that.

#### `/src/kedro_ibis_bigquery/pipelines/data_processing/nodes.py`
Here I described my `data_processing` function, which contains Python code written using the Ibis library syntax (similar to Pandas). This function fully replicates the SQL query we saw earlier.
```python
import ibis

def data_processing(itt, itrt):
    trends = (
        itt.filter(itt.score.notnull())
           .mutate(month=itt.week.cast('string').left(7))
           .group_by([itt.country_name, 'month', itt.term])
           .aggregate(avg_score=itt.score.mean())
    )
    
    rising_trends = (
        itrt.mutate(month=itrt.week.cast('string').left(7))
            .group_by([itrt.country_name, 'month', itrt.term])
            .aggregate(avg_percent_gain=itrt.percent_gain.mean())
    )

    result = trends.left_join(
        rising_trends,
        [
            trends.country_name == rising_trends.country_name,
            trends.month == rising_trends.month,
            trends.term == rising_trends.term
        ]
    )[
        trends.country_name,
        trends.month,
        trends.term.name('google_trend'),
        trends.avg_score,
        rising_trends.avg_percent_gain
    ]

    return result.to_pandas()
```
The result object is an `ibis.TableDataset`. I want it to be saved as a CSV later, so I converted it to a pandas DataFrame.


#### `/src/kedro_ibis_bigquery/pipelines/data_processing/pipeline.py`
Here I created a Kedro pipeline consisting of one node, which includes the previously described `data_processing` function. The pipeline has two inputs from BigQuery and one output to a CSV, as described in the DataCatalog.
```python
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
```

5. Now I can run the `kedro run` command to execute my pipeline. This will preprocess the dataset, store it in my local directory, and allow me to continue developing my Kedro ML pipeline with the model training part. The data preprocessing is executed on the database engine, and all my SQL queries are saved within my Python pipeline.

### Benefits
- **Centralized Code Management**: All pipeline code, including SQL queries, is stored and managed within your Kedro project.
- **Scalability**: By executing SQL queries on Google BigQuery, you leverage its scalability and performance.
- **Reproducibility**: Kedro ensures that your ML pipelines are reproducible, making it easier to share and collaborate with others.

### Conclusion

By integrating Ibis with Kedro, I was able to create a scalable and maintainable solution for managing ML pipelines that include SQL query execution. This approach keeps all code centralized within the Kedro project, allowing for better version control and collaboration. If you're facing similar challenges, I highly recommend exploring the combination of Kedro, Ibis, and IbisDataset.

Feel free to reach out if you have any questions or need further details on the implementation!