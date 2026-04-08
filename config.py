import os

# ── Anthropic ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── YOUR BASE RESUME ───────────────────────────────────────────────────────
RESUME_PDF_PATH = "my_resume.pdf"

def _load_resume(pdf_path: str) -> str:
    """Extract text from resume PDF automatically."""
    import os
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"Resume PDF not found: {pdf_path}\n"
            f"Drop your resume PDF into the project folder and update RESUME_PDF_PATH in config.py"
        )
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(pages).strip()
    except ImportError:
        raise ImportError("Run: pip install pdfplumber")

BASE_RESUME = _load_resume(RESUME_PDF_PATH)

# BASE_RESUME = """
# Navaneeta Padmakumar
# Richardson, Texas | +1 945-338-9465 | nxp230016@utdallas.edu
# linkedin.com/in/navaneetapk | github.com/nxp0999

# SUMMARY
# Data Scientist and ML Engineer with 2.5+ years of industry experience and an MS in Computer Science (Data Science) from UT Dallas (GPA 3.6). Skilled in the full ML lifecycle — from data engineering and statistical modeling to deep learning and deployment. Hands-on experience with PySpark, PyTorch, TensorFlow, HuggingFace, CNNs, RNNs, LSTMs, and big data pipelines (Hadoop, MapReduce). Databricks Certified Data Engineer Professional. Seeking data science, ML engineering, or data engineering roles in India.

# EDUCATION
# The University of Texas at Dallas — Expected May 2026
# M.S. Computer Science (Data Science Specialization) | GPA: 3.6 / 4.0
# Relevant Coursework: Machine Learning, Big Data Management & Analytics, Statistics for Data Science,
# Computer Vision, Robotics, Virtual Reality Interfaces, Database Design, Artificial Intelligence

# Government Engineering College, Trivandrum — July 2021
# B.Tech (Honors) in Electronics and Communication | GPA: 8.87 / 10
# Chairperson – IEEE WiE | Under Secretary General – MUN

# CERTIFICATIONS
# Databricks Certified Data Engineer Professional — January 2025 (Valid through January 2027)
# PG Advanced Program in Data Science & Machine Learning — IIT Madras — November 2024

# TECHNICAL SKILLS
# Languages:          Python, R, SQL, Java, C, Node.js, Shell Scripting
# ML & Deep Learning: PyTorch, TensorFlow, scikit-learn, HuggingFace Transformers, CNNs, RNNs, LSTMs,
#                     BERT, Feature Engineering, Hyperparameter Tuning, Transfer Learning
# Big Data:           Apache Spark, PySpark, Hadoop, MapReduce, Databricks
# Data Science:       Regression, Classification, Clustering, A/B Testing, Time Series (ARIMA),
#                     Hypothesis Testing, Statistical Modeling, NLP, Computer Vision
# Data Engineering:   MySQL, MongoDB, ETL Pipelines, Docker, Kubernetes, REST APIs
# Visualization:      Matplotlib, Seaborn, Pandas, NumPy, SciPy
# Tools & Platforms:  Git, Linux, MATLAB, VS Code, Databricks, Unity (VR), ROS2, R Studio

# PROFESSIONAL EXPERIENCE

# Datanimbus Technologies — Bangalore, India | July 2021 – January 2024
# Platform and DevOps Engineer (Python, Docker, Kubernetes, MongoDB, APIs)
# - Automated CI/CD analytics pipeline using Python and shell scripting to track deployment metrics,
#   test coverage, and build performance; reduced deployment time by 80% (hours to minutes)
# - Analyzed system performance data across 20+ deployments to maintain 100% uptime; identified
#   bottlenecks and failure patterns through log analysis and anomaly detection
# - Conducted exploratory data analysis on 300+ UI/UX issues across 25 modules; used statistical
#   methods to prioritize bug fixes by severity, resolving 50%+ client-reported defects
# - Streamlined onboarding via training metrics analysis, reducing ramp-up time by 50% (4 to 2 weeks);
#   acquired 3 clients through data-driven product presentations

# ThoughtLine Technologies Pvt. Ltd. — Trivandrum, India | June 2018
# Data Analytics Intern
# - Performed statistical analysis to identify high-margin product categories and seasonal demand trends;
#   built regression models to forecast inventory needs
# - Designed interactive analytics dashboards using Python visualization libraries; delivered real-time KPIs
#   on product performance and inventory turnover to stakeholders
# - Implemented data validation and quality checks, reducing customer complaints by 40%

# PROJECTS

# GlobalRides – Predictive Analytics & Database System | SQL, Python, MySQL | Jan 2025 – May 2025
# - Built predictive models using historical order data to forecast demand patterns across 12 restaurants
#   and 11 ride routes; improved resource allocation efficiency by 23% via time-series and regression analysis
# - Analyzed 260+ orders for customer segmentation; discovered power users (15+ orders) generated
#   $1,694 revenue at 4.2/5.0 satisfaction through statistical profiling
# - Designed relational database with 26 normalized tables; achieved 95%+ order fulfillment within SLA

# CSMC Mentoring Platform – Queuing Analysis & Optimization | C, Statistical Modeling | Sep 2024
# - Applied queuing theory to optimize tutor-student matching; reduced wait time variance to <800μs
#   through probability distribution modeling
# - Analyzed 100+ concurrent users via Monte Carlo simulation; achieved 200μs average response time
#   through O(1) thread-safe queue optimization
# - Designed A/B testing framework to evaluate scheduling algorithms using hypothesis testing

# Big Data Analytics – NLP Pipeline | PySpark, Hadoop, MapReduce | 2025
# - Built PySpark NLP pipeline with NER and TF-IDF for movie search on Carnegie Movie Summary Corpus
# - Implemented ALS collaborative filtering and Naive Bayes classifier from scratch using PySpark MLlib
# - Processed large-scale datasets using Hadoop and MapReduce on distributed compute clusters

# Computer Vision – Deep Learning Models | PyTorch, CNNs, RNNs | 2025
# - Implemented CNN architectures achieving 99.31% accuracy on MNIST and 70.79% on CIFAR-10
# - Built RNN and LSTM models for sequence modeling; applied transfer learning with HuggingFace models
# - Explored object detection, feature detection (SIFT, Harris), and image segmentation pipelines

# Satellite Cluster Optimization via ML | Python, MATLAB, NumPy | Aug 2020 – June 2021
# - Improved satellite formation efficiency by 50% via ML-based trajectory optimization using
#   Clohessy-Wiltshire equations; reduced fuel consumption through gradient descent
# - Developed numerical methods and visualization tools in Python/MATLAB for hyperparameter tuning;
#   validated predictive models achieving 92% accuracy in trajectory forecasting
# """



# ── Job search keywords and roles ──────────────────────────────────────────
JOB_SEARCH = {
    "keywords": [
        # Core roles — highest match to your background
        "data scientist",
        "machine learning engineer",
        "data engineer",
        # Secondary roles — strong overlap
        "ML engineer",
        "AI engineer",
        "NLP engineer",
        "deep learning engineer",
        "big data engineer",
        "analytics engineer",
        "business intelligence engineer",
        # Entry-friendly titles
        "associate data scientist",
        "junior data scientist",
        "data analyst",
        "python developer data science",
    ],
    "location": "India",
    "max_per_platform": 10,
} ##

# ── Thresholds ─────────────────────────────────────────────────────────────
FIT_SCORE_THRESHOLD   = 65   # Skip if Claude scores below this
RESUME_SIMILARITY_MIN = 70   # Skip if tailored resume quality drops below this

# ── Platforms ──────────────────────────────────────────────────────────────
PLATFORMS = {
    "indeed":      True,
    "naukri":      True,
    "linkedin":    True,
    "internshala": True,
}

# ── Auto-apply (keep False until we test everything) ───────────────────────
AUTO_APPLY = False
HEADLESS   = True

# ── Credentials ────────────────────────────────────────────────────────────
CREDENTIALS = {
    "resumeworded": {
        "email":    os.getenv("RESUMEWORDED_EMAIL", ""),
        "password": os.getenv("RESUMEWORDED_PASSWORD", ""),
    },
    "linkedin": {
        "email":    os.getenv("LINKEDIN_EMAIL", ""),
        "password": os.getenv("LINKEDIN_PASSWORD", ""),
    },
    "naukri": {
        "email":    os.getenv("NAUKRI_EMAIL", ""),
        "password": os.getenv("NAUKRI_PASSWORD", ""),
    },
    "indeed": {
        "email":    os.getenv("INDEED_EMAIL", ""),
        "password": os.getenv("INDEED_PASSWORD", ""),
    },
    "internshala": {
        "email":    os.getenv("INTERNSHALA_EMAIL", ""),
        "password": os.getenv("INTERNSHALA_PASSWORD", ""),
    },
}

# ── Output ─────────────────────────────────────────────────────────────────
DB_PATH    = "output/applications.db"
OUTPUT_DIR = "output/applications"
# AI mode: "groq" (API, rate limited) or "ollama" (local, unlimited)
AI_MODE = "ollama"

