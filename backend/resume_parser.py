import re
import logging
from backend.layer_3_experience import extract_years_from_resume
from backend.layer_2_taxonomy import TAXONOMY_MAP

logger = logging.getLogger(__name__)

# Master list of skills for extraction
COMMON_SKILLS = [
    # Programming Languages
    "python", "javascript", "react", "node.js", "java", "c++", "c", "sql", 
    "go", "rust", "typescript", "html", "css", "c#", ".net", "php", "swift", 
    "kotlin", "ruby", "scala", "perl", "r", "dart", "objective-c", "lua", "matlab",
    
    # Frameworks & Libraries
    "ruby on rails", "angular", "vue.js", "spring", "django", "flask", "express",
    "next.js", "nuxt.js", "svelte", "tailwind css", "bootstrap", "jquery", 
    "fastapi", "nestjs", "laravel", "graphql", "apollo", "grpc", "redux", "rxjs",
    
    # Databases & Caching
    "mongodb", "postgresql", "redis", "mysql", "sqlite", "mariadb", "cassandra",
    "dynamodb", "elasticsearch", "neo4j", "couchbase", "oracle", "sql server",
    "supabase", "firebase", "memcached", "kafka", "rabbitmq",
    
    # Cloud & DevOps
    "docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "terraform",
    "jenkins", "github actions", "gitlab ci", "ansible", "chef", "puppet", 
    "nginx", "apache", "linux", "unix", "bash", "shell scripting", "prometheus", 
    "grafana", "splunk", "datadog", "vagrant",
    
    # AI, ML & Data Science
    "machine learning", "data analysis", "scikit-learn", "tensorflow", "pytorch",
    "keras", "pandas", "numpy", "matplotlib", "seaborn", "nltk", "spacy",
    "opencv", "deep learning", "nlp", "computer vision", "apache spark",
    "hadoop", "snowflake", "airflow", "tableau", "power bi", "bigquery",
    
    # Core Concepts & Software
    "git", "dsa", "data structures", "algorithms", "dynamic programming", 
    "greedy techniques", "time/space complexity analysis", "system design", 
    "microservices", "agile", "scrum", "kanban", "tdd", "bdd", "rest api", 
    "restful apis", "oop", "object oriented programming", "figma", "ui/ux", 
    "jira", "confluence", "davinci resolve", "photoshop", "illustrator",
    "blender", "unity", "unreal engine"
]

def _extract_name(text: str, filename: str) -> str:
    """Extract candidate name from the first few lines of the text, falling back to filename."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines[:3]:
        # Exclude common headers
        lower_line = line.lower()
        if any(bad in lower_line for bad in ["resume", "curriculum vitae", "profile", "summary", "contact"]):
            continue
        
        # Check if the line looks like a name (2-4 capitalized words)
        # Allows for middle initials and dots
        if re.match(r'^([A-Z][a-zA-Z\.\-]*\s+){1,3}[A-Z][a-zA-Z\.\-]*$', line):
            return line
            
    # Fallback to filename without extension
    return re.sub(r'\.[a-zA-Z0-9]+$', '', filename)

def _extract_github(text: str) -> str:
    """Extract github username."""
    match = re.search(r'(?:github\.com\/|github:?\s*)([a-zA-Z0-9-]+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def _extract_skills(text: str) -> list:
    """Extract skills using taxonomy map and predefined common skills."""
    found_skills = set()
    text_lower = text.lower()
    
    # Check taxonomy map keys and values
    all_skill_keywords = set(TAXONOMY_MAP.keys()) | set(TAXONOMY_MAP.values()) | set(COMMON_SKILLS)
    
    for skill in all_skill_keywords:
        # Escape special regex chars in skill
        escaped_skill = re.escape(skill)
        # Use (?:\b|\W) to match boundaries for special characters like C++, .NET
        if re.search(rf'(?:^|\W){escaped_skill}(?:$|\W)', text_lower):
            # If it's an alias, map to canonical
            canonical = TAXONOMY_MAP.get(skill, skill)
            # Find the original case from COMMON_SKILLS or title case it
            # For better display
            display_skill = next((s for s in COMMON_SKILLS if s.lower() == canonical), canonical.title())
            if display_skill.lower() == "c++": display_skill = "C++"
            elif display_skill.lower() == "sql": display_skill = "SQL"
            elif display_skill.lower() == "dsa": display_skill = "DSA"
            elif display_skill.lower() == "aws": display_skill = "AWS"
            elif display_skill.lower() == "gcp": display_skill = "GCP"
            elif display_skill.lower() == "html": display_skill = "HTML"
            elif display_skill.lower() == "css": display_skill = "CSS"
            elif display_skill.lower() == "php": display_skill = "PHP"
            elif display_skill.lower() == "ci/cd": display_skill = "CI/CD"
            
            found_skills.add(display_skill)
            
    return sorted(list(found_skills))

def _extract_projects(text: str) -> str:
    """Extract the projects section text."""
    heading_regex = re.compile(r'^[^a-zA-Z]*?(?:Personal\s+|Academic\s+|Key\s+)?Projects?(?:\s+Experience)?[^a-zA-Z]*?$', re.IGNORECASE | re.MULTILINE)
    heading_match = heading_regex.search(text)
    
    if heading_match:
        start_index = heading_match.end()
        stop_regex = re.compile(r'^[^a-zA-Z]*?(?:Professional\s+|Work\s+)?(?:Experience|Education|Skills|Languages|Certifications|Work History|Employment|Career|Summary|Technical Skills)[^a-zA-Z]*?$', re.IGNORECASE | re.MULTILINE)
        stop_match = stop_regex.search(text[start_index:])
        
        end_index = start_index + stop_match.start() if stop_match else len(text)
        
        p_text = text[start_index:end_index].strip()
        if len(p_text) > 800: p_text = p_text[:800] + '...'
        return p_text
    
    # Fallback heuristic: bullet points with keywords
    project_bullets = []
    bullet_regex = re.compile(r'(?:^|\n)[ \t]*(?:[-•*]|\d+\.)[ \t]+([^\n]*?(?:project|application|system|platform|developed|built|created|designed|architected)[^\n]*)', re.IGNORECASE)
    
    for match in bullet_regex.finditer(text):
        bullet_text = match.group(1).strip()
        if 30 < len(bullet_text) < 500:
            project_bullets.append("• " + bullet_text)
            
    if project_bullets:
        combined = '\n'.join(project_bullets)
        if len(combined) > 800: combined = combined[:800] + '...'
        return combined
        
    return ""

def _extract_email(text: str) -> str:
    """Extract email address."""
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    return match.group(0) if match else ""

def _extract_phone(text: str) -> str:
    """Extract phone number."""
    # Matches international and standard formats like +91-9876543210, (123) 456-7890
    match = re.search(r'(?:(?:\+|00)\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', text)
    return match.group(0).strip() if match else ""

def _extract_linkedin(text: str) -> str:
    """Extract linkedin username."""
    match = re.search(r'(?:linkedin\.com\/in\/|linkedin:\s*)([a-zA-Z0-9-]+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def _extract_portfolio(text: str) -> list:
    """Extract other URLs as portfolio links."""
    # simple url regex
    urls = re.findall(r'(https?://[^\s]+|www\.[^\s]+)', text)
    portfolio = []
    for url in urls:
        url_lower = url.lower()
        if 'github.com' not in url_lower and 'linkedin.com' not in url_lower:
            portfolio.append(url)
    return list(set(portfolio))

def _extract_education(text: str) -> str:
    """Extract highest degree."""
    degrees = []
    text_lower = text.lower()
    if re.search(r'\b(phd|ph\.d|doctorate)\b', text_lower): degrees.append("PhD")
    if re.search(r'\b(master|m\.s|msc|m\.tech|mtech|mba)\b', text_lower): degrees.append("Master's")
    if re.search(r'\b(bachelor|b\.s|bsc|b\.tech|btech|b\.e|b\.a)\b', text_lower): degrees.append("Bachelor's")
    
    if "PhD" in degrees: return "PhD"
    if "Master's" in degrees: return "Master's"
    if "Bachelor's" in degrees: return "Bachelor's"
    return ""

def parse_resume_data(text: str, filename: str) -> dict:
    """Parses resume text into structured data using heuristics and NLP."""
    
    # 1. Name
    name = _extract_name(text, filename)
    
    # 2. GitHub Username
    github = _extract_github(text)
    
    # 3. Years of Experience using layer_3 NLP extraction
    extraction = extract_years_from_resume(text)
    years_of_experience = extraction.get("total_years", 0.0)
    
    # 4. Skills
    skills = _extract_skills(text)
    
    # 5. Projects
    projects_text = _extract_projects(text)
    
    return {
        "name": name,
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "linkedin": _extract_linkedin(text),
        "portfolio": _extract_portfolio(text),
        "education": _extract_education(text),
        "years_of_experience": int(years_of_experience),
        "skills": skills,
        "github_username": github,
        "projects_text": projects_text
    }
