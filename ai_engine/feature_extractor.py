<<<<<<< HEAD
def extract_features(project):
    return {
        "framework": project.framework,
        "scan_type": project.scan_type,
        "file_type": project.file.name.split('.')[-1],
        "issue_count": project.scan_results.count()
    }
=======
def extract_features(project):
    return {
        "framework": project.framework,
        "scan_type": project.scan_type,
        "file_type": project.file.name.split('.')[-1],
        "issue_count": project.scan_results.count()
    }
>>>>>>> db10e5ef20a7e0293aa4275ab1c6357019f9d8ee
