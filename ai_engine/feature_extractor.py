def extract_features(project):
    return {
        "framework": project.framework,
        "scan_type": project.scan_type,
        "file_type": project.file.name.split('.')[-1],
        "issue_count": project.scan_results.count()
    }
