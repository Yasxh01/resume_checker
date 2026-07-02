# ============================================================
# backend/data.py — Mock Dataset & Schema Definitions
# ============================================================

# ------------------------------------------------------------
# JOB DESCRIPTIONS — Multi-JD Mode Support
# ------------------------------------------------------------
# We now support multiple job descriptions so users can
# switch between roles and see how rankings shift dynamically.
# ------------------------------------------------------------

job_descriptions = {
    "Python Backend Engineer": {
        "text": (
            "We are looking for a skilled Python Backend Engineer to join our team. "
            "The ideal candidate will have strong experience with Django for building "
            "REST APIs, proficiency in AWS cloud services including EC2, S3, and Lambda, "
            "and a solid understanding of PostgreSQL database management. "
            "Experience with Docker and CI/CD pipelines is a strong plus. "
            "The role requires writing clean, well-tested Python code and collaborating "
            "in an agile environment."
        ),
        "required_skills": ["python", "django", "aws", "postgresql", "docker"],
        "required_years": 3,
    },

    "Full Stack JavaScript Engineer": {
        "text": (
            "We are hiring a Full Stack JavaScript Engineer with strong experience "
            "in React for frontend development and Node.js for backend services. "
            "The candidate should be proficient in TypeScript, MongoDB, and deploying "
            "applications on AWS or GCP. Experience with GraphQL and Docker is preferred. "
            "Must be comfortable working in an agile team with CI/CD workflows."
        ),
        "required_skills": ["javascript", "react", "nodejs", "typescript", "mongodb", "aws"],
        "required_years": 2,
    },

    "Machine Learning Engineer": {
        "text": (
            "Seeking a Machine Learning Engineer with hands-on experience building "
            "and deploying production ML models. Strong proficiency in Python, PyTorch "
            "or TensorFlow, and scikit-learn required. Experience with MLOps tools, "
            "Docker containerization, and AWS SageMaker is highly valued. "
            "Must understand data pipelines, feature engineering, and model evaluation."
        ),
        "required_skills": ["python", "pytorch", "tensorflow", "scikitlearn", "docker", "aws"],
        "required_years": 3,
    },
}

# Default job description key
DEFAULT_JD = "Python Backend Engineer"

# ------------------------------------------------------------
# CANDIDATE PROFILES
# ------------------------------------------------------------

candidate_profiles = [
    {
        "name": "Ananya Sharma",
        "resume_text": (
            "Recent computer science graduate with a passion for backend development. "
            "Proficient in Python and Django REST framework. Deployed personal projects "
            "on AWS EC2 and S3. Comfortable with PostgreSQL and Docker containers. "
            "Built a task management API during a 3-month internship. "
            "Active open-source contributor on GitHub."
        ),
        "skills": ["python", "django", "aws", "postgresql", "docker", "git"],
        "years_of_experience": 1,
        "projects_text": (
            "Task Management API: Built a RESTful API using Django and PostgreSQL. "
            "Hosted on AWS EC2 with S3 for file storage. Used Docker for containerization."
        ),
        "github_username": "Sheetal-cell",
    },
    {
        "name": "Rohan Mehta",
        "resume_text": (
            "Backend engineer with 2 years of professional experience. "
            "Worked extensively with Python and Django to build scalable microservices. "
            "Managed cloud infrastructure on Amazon Web Services including EC2, RDS, and CloudFront. "
            "Strong command of Postgres for relational data modeling. "
            "Familiar with containerization using Docker and orchestration with Kubernetes."
        ),
        "skills": ["python", "django", "amazon web services", "postgres", "docker", "kubernetes"],
        "years_of_experience": 2,
        "projects_text": (
            "E-Commerce Backend: Designed REST APIs in Django for a live e-commerce platform. "
            "Database managed via Postgres on Amazon Web Services RDS. "
            "CI/CD pipeline set up with GitHub Actions and Docker."
        ),
        "github_username": "Rishav07-05",
    },
    {
        "name": "Priya Iyer",
        "resume_text": (
            "Senior Python Backend Engineer with 5 years of industry experience. "
            "Led a team of 4 engineers building Django-based REST APIs serving 1M+ users. "
            "Deep expertise in AWS services: Lambda, EC2, S3, RDS, and CloudWatch. "
            "Designed and optimized PostgreSQL schemas for high-traffic applications. "
            "Championed Docker-based deployments and CI/CD automation with Jenkins and GitHub Actions. "
            "Passionate about clean code, TDD, and system design."
        ),
        "skills": ["python", "django", "aws", "postgresql", "docker", "jenkins", "redis", "celery"],
        "years_of_experience": 5,
        "projects_text": (
            "Payment Gateway Integration: Architected a Django microservice handling payments "
            "for 500K+ daily transactions. Used PostgreSQL for transactional integrity and "
            "deployed on AWS Lambda with Docker. "
            "Internal DevOps Dashboard: Built a real-time monitoring tool with Django Channels "
            "integrated with AWS CloudWatch metrics."
        ),
        "github_username": "torvalds",
    },
]
