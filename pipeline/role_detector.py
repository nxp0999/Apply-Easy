"""
pipeline/role_detector.py

Scores the candidate's resume against a synthetic ideal JD for each
ROLE_CLUSTER to rank which roles they are most qualified for.
Used by --prep (Segment 1) to decide which resume variations to generate.
"""

from pipeline.rule_scorer import score_fit_rules

# Synthetic "ideal" JD per cluster — rich enough to exercise all scorer dimensions.
# Edit these to keep them aligned with what the market actually asks for.
CLUSTER_IDEAL_JDS: dict[str, dict] = {
    "ml_ai": {
        "title": "ML Engineer",
        "company": "",
        "location": "Bengaluru",
        "description": (
            "We are looking for an ML Engineer with 2-4 years of experience. "
            "Python PyTorch TensorFlow scikit-learn pandas numpy scipy statsmodels "
            "MLflow Airflow dbt LangChain RAG LLM HuggingFace transformers "
            "embeddings vector database machine learning deep learning NLP "
            "feature engineering model training inference deployment "
            "Docker Kubernetes AWS GCP Kafka Spark Databricks SQL git FastAPI. "
            "Master's degree preferred. Databricks certified professional a plus. "
            "Fintech payments team. Hybrid work from Bengaluru."
        ),
    },
    "data_engineering": {
        "title": "Data Engineer",
        "company": "",
        "location": "Bengaluru",
        "description": (
            "Build and maintain scalable data pipelines. "
            "Python PySpark Spark SQL Airflow dbt Kafka Databricks BigQuery "
            "Redshift Snowflake AWS GCP Azure Docker Kubernetes git ETL "
            "streaming batch processing data warehouse analytics engineering "
            "data platform infrastructure. 2-4 years experience. "
            "Master's degree preferred. Fintech domain. Hybrid Bengaluru."
        ),
    },
    "analytics_bi": {
        "title": "Analytics Engineer",
        "company": "",
        "location": "Bengaluru",
        "description": (
            "Analytics engineering and business intelligence role. "
            "SQL Python dbt Tableau Power BI Looker Spark BigQuery Redshift "
            "pandas numpy A/B testing statistics data visualization dashboards "
            "reporting business intelligence analytics. "
            "2-4 years experience. Master's preferred. Hybrid Bengaluru."
        ),
    },
    "mlops_platform": {
        "title": "MLOps Engineer",
        "company": "",
        "location": "Bengaluru",
        "description": (
            "Build and maintain the ML platform and model serving infrastructure. "
            "MLflow Airflow Kubeflow Docker Kubernetes AWS SageMaker GCP Vertex AI "
            "Python CI/CD model deployment monitoring feature store Kafka Spark "
            "Databricks data pipeline machine learning platform infrastructure. "
            "2-4 years experience. Master's preferred. Remote or Bengaluru."
        ),
    },
    "genai_llm": {
        "title": "GenAI Engineer",
        "company": "",
        "location": "Bengaluru",
        "description": (
            "Build LLM-powered products and RAG pipelines. "
            "LLM large language model RAG retrieval augmented generation LangChain "
            "HuggingFace transformers OpenAI embeddings vector database Pinecone "
            "Weaviate Python FastAPI Flask fine-tuning prompt engineering NLP "
            "Kafka Airflow Docker AWS. 2-4 years experience. "
            "Master's preferred. Fintech natural language processing. Remote."
        ),
    },
}


# Role-specific summary lines — written from actual resume content, no fabrication.
# These are injected at the top of each role variation during --prep.
# Edit these directly to tune how each version opens.
ROLE_SUMMARIES: dict[str, str] = {
    "ml_ai": (
        "ML Engineer with 2.5 years of industry experience and an MS in CS (Data Science, UT Dallas). "
        "Builds PyTorch/scikit-learn models, LLM/RAG pipelines, and real-time NLP systems using "
        "Kafka and Spark Structured Streaming. Databricks Certified Data Engineer Professional."
    ),
    "data_engineering": (
        "Data Engineer with production experience in Python, Docker, Kubernetes, and MongoDB at Datanimbus. "
        "Projects in Kafka, Spark Structured Streaming, Databricks ETL/ELT, and Elasticsearch. "
        "MS in CS (Data Science Track, UT Dallas). Databricks Certified Data Engineer Professional."
    ),
    "analytics_bi": (
        "Analytics Engineer with an MS in CS (Data Science, UT Dallas) and 2.5 years of industry experience "
        "in Python, SQL, and data product development. Built analytical views, loyalty-program reporting, "
        "and operational dashboards across fintech and relational database systems projects."
    ),
    "mlops_platform": (
        "MLOps / Platform Engineer with experience in Docker, Kubernetes, CI/CD pipelines, and Python-based "
        "automation at Datanimbus. Built AI/ML proof-of-concept applications and orchestrated distributed "
        "data workflows. MS in CS from UT Dallas. Databricks Certified Data Engineer Professional."
    ),
    "genai_llm": (
        "GenAI Engineer specializing in LLM applications, RAG pipelines, and NLP. "
        "Built Meridian (Anthropic Claude API, real-time financial analytics) and a Kafka + Spark "
        "Structured Streaming NER pipeline with spaCy. MS in CS (Data Science), UT Dallas, 2026."
    ),
}


def detect_top_roles(resume_text: str, n: int = 5) -> list[dict]:
    """
    Score the resume against each cluster's ideal JD.
    Returns top-n clusters sorted by fit score descending.
    Each entry: {cluster, label, score, strengths, gaps, missing, ideal_jd}
    """
    from config import ROLE_CLUSTERS

    results = []
    for cluster_key, cluster in ROLE_CLUSTERS.items():
        ideal = CLUSTER_IDEAL_JDS.get(cluster_key)
        if not ideal:
            continue
        fit = score_fit_rules(ideal, resume_text)
        results.append({
            "cluster":   cluster_key,
            "label":     cluster["label"],
            "score":     fit["score"],
            "strengths": fit["strengths"],
            "gaps":      fit["gaps"],
            "missing":   fit["missing_keywords"],
            "bonuses":   fit["bonuses"],
            "ideal_jd":  ideal,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:n]
