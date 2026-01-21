import os
import sys
import json
import re

# Library checks: Agar ML libraries nahi hain toh crash na ho
try:
    import joblib
    import numpy as np
    HAS_ML = True
except ImportError:
    HAS_ML = False

# Path Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

def scan_file_for_issues(file_path):
    """
    File ke andar patterns dhoond kar real issues nikalna
    """
    critical = 0
    high = 0
    medium = 0
    loc = 0
    
    try:
        # File path normalizer (Windows/Linux compatibility)
        file_path = os.path.normpath(file_path)
        
        if not os.path.exists(file_path):
            return 0, 0, 0, 0

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.splitlines()
            loc = len(lines)

            # 1. CRITICAL: Hardcoded Secrets & Dangerous Functions
            # Pattern for: api_key = "...", password: '...'
            if re.search(r'(password|passwd|secret|api_key|token|auth_key)\s*[:=]\s*["\']', content, re.I):
                critical += 2
            if any(func in content for func in ["eval(", "exec(", "os.system(", "subprocess.Popen("]):
                critical += 3
            
            # 2. HIGH: Insecure Protocols & Data Leakage
            if "http://" in content and "localhost" not in content and "127.0.0.1" not in content:
                high += 2
            # Simple Email Regex
            if re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content):
                high += 1
                
            # 3. MEDIUM: Coding Standards
            medium += content.count("console.log")
            medium += content.count("TODO")
            if loc > 1000: # Very large files are a maintenance risk
                medium += 1

    except Exception as e:
        # Debug error for manual testing
        # print(f"DEBUG ERROR: {str(e)}", file=sys.stderr)
        pass
        
    return critical, high, medium, loc

def run_analysis(file_path):
    # 1. Real Static Analysis
    critical, high, medium, loc = scan_file_for_issues(file_path)
    total_issues = critical + high + medium
    
    # 2. Score Calculation (Logic based on your dataset)
    base_score = 100
    penalty = (critical * 15) + (high * 8) + (medium * 3)
    final_score = max(30, base_score - penalty)

    # 3. ML Prediction (Only if libraries and model exist)
    if HAS_ML and os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
            # Feature mapping to match your dataset.csv [framework, scan_type, file_count]
            # Mapping: GDPR=2, deep=1, count=1
            X = np.array([[2, 1, 1]]) 
            ml_pred = int(model.predict(X)[0])
            # Merge ML logic with Real Scan logic
            final_score = int((final_score + ml_pred) / 2)
        except:
            pass # Use the final_score from static analysis

    # Final JSON structure for Django
    return {
        "ethical_score": final_score, 
        "security_score": max(5, final_score - 5),
        "details": {
            "total_issues": total_issues,
            "critical": critical,
            "high": high,
            "medium": medium,
            "lines_analyzed": loc,
            "status": "Non-Compliant" if critical > 0 else "Compliant",
            "vulnerabilities": [
                {"severity": "Critical", "count": critical},
                {"severity": "High", "count": high},
                {"severity": "Medium", "count": medium}
            ]
        }
    }

if __name__ == "__main__":
    # Ensure subprocess communication works via JSON
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        try:
            results = run_analysis(target_file)
            print(json.dumps(results))
        except Exception as e:
            # Last resort error reporting
            print(json.dumps({
                "ethical_score": 0,
                "security_score": 0,
                "details": {"error": str(e)},
                "status": "Failed"
            }))
    else:
        print(json.dumps({"error": "No file path provided"}))